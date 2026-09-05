from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
import subprocess
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from orin_worker.app import WorkerServer  # noqa: E402
from orin_worker.editor import EditorSettings, JobRejected, JobRunner, OllamaClient, Workspace, parse_text_tool_calls  # noqa: E402


class FakeModel:
    def __init__(self, messages: list[dict[str, object]]):
        self.messages = iter(messages)

    def chat(self, _messages: object, _tools: object) -> dict[str, object]:
        return next(self.messages)


class OllamaClientTest(unittest.TestCase):
    def test_sampling_defaults_are_deterministic(self) -> None:
        client = OllamaClient("http://127.0.0.1:11434", "model", 30)
        self.assertEqual(client.temperature, 0.0)
        self.assertEqual(client.seed, 0)
        self.assertFalse(client.think)
        self.assertEqual(client.context_tokens, 32_768)


class BlockingModel:
    def __init__(self) -> None:
        self.entered = threading.Event()
        self.release = threading.Event()

    def chat(self, _messages: object, _tools: object) -> dict[str, object]:
        self.entered.set()
        self.release.wait(timeout=2)
        return {"role": "assistant", "tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "done"}}}]}


def init_repo(root: Path, name: str = "fixture") -> Path:
    repo = root / "worktrees" / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Worker Test"], cwd=repo, check=True)
    (repo / "hello.txt").write_text("hello world\n", encoding="utf-8")
    subprocess.run(["git", "add", "hello.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    return repo


class WorkerApiTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        init_repo(root)
        config = EditorSettings(root / "worktrees", root / "state", root / "artifacts")
        model = FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "replace_text", "arguments": {"path": "hello.txt", "old": "hello", "new": "goodbye"}}}]},
            {"role": "assistant", "tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "Changed greeting."}}}]},
        ])
        self.server = WorkerServer(("127.0.0.1", 0), config, model)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()

    def get_json(self, path: str) -> tuple[int, dict[str, str]]:
        with urlopen(self.base_url + path, timeout=2) as response:
            return response.status, json.load(response)

    def post(self, payload: object) -> tuple[int, dict[str, object]]:
        body = json.dumps(payload).encode()
        request = Request(self.base_url + "/v1/jobs", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)

    def test_health(self) -> None:
        status, payload = self.get_json("/health")
        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ok")

    def test_ready_creates_probe(self) -> None:
        status, payload = self.get_json("/ready")
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"status": "ready"})
        self.assertTrue((Path(self.temp_dir.name) / "state" / ".ready").exists())

    def test_edit_job_and_persisted_lookup(self) -> None:
        body = json.dumps({"kind": "edit", "workspace": "fixture", "instruction": "Change hello to goodbye."}).encode()
        request = Request(self.base_url + "/v1/jobs", data=body, headers={"Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=5) as response:
            self.assertEqual(response.status, 201)
            result = json.load(response)
        self.assertEqual(result["status"], "completed")
        self.assertIn("-hello world", result["diff"])
        self.assertIn("+goodbye world", result["diff"])
        status, stored = self.get_json(f"/v1/jobs/{result['id']}")
        self.assertEqual(status, 200)
        self.assertEqual(stored["id"], result["id"])

    def test_rejects_unknown_request_fields(self) -> None:
        body = json.dumps({"kind": "edit", "workspace": "fixture", "instruction": "x", "command": "sh"}).encode()
        request = Request(self.base_url + "/v1/jobs", data=body, method="POST")
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=2)
        self.assertEqual(raised.exception.code, 400)
        self.assertEqual(json.load(raised.exception)["error"], "job_rejected")

    def test_rejects_request_body_over_limit(self) -> None:
        request = Request(self.base_url + "/v1/jobs", data=b"x" * 16_385, method="POST")
        with self.assertRaises(HTTPError) as raised:
            urlopen(request, timeout=2)
        self.assertEqual(raised.exception.code, 400)

    def test_unknown_job_ids_return_not_found(self) -> None:
        for job_id in ("not-an-id", "0" * 32):
            with self.subTest(job_id=job_id), self.assertRaises(HTTPError) as raised:
                urlopen(self.base_url + f"/v1/jobs/{job_id}", timeout=2)
            self.assertEqual(raised.exception.code, 404)

    def test_empty_diff_is_persisted(self) -> None:
        self.server.jobs.model = FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "No change needed."}}}]},
        ])
        status, result = self.post({"kind": "edit", "workspace": "fixture", "instruction": "Leave it unchanged."})
        self.assertEqual(status, 201)
        self.assertEqual(result["status"], "no_change")
        self.assertEqual(result["diff"], "")
        self.assertEqual(result["git_status"], "")

    def test_failed_check_retains_diff_and_check_evidence(self) -> None:
        self.server.jobs.model = FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "write_file", "arguments": {"path": "bad.py", "content": "def broken(:\n    pass\n"}}}]},
            {"role": "assistant", "tool_calls": [{"function": {"name": "finish", "arguments": {"summary": "added file"}}}]},
        ])
        _, result = self.post({"kind": "edit", "workspace": "fixture", "instruction": "Add bad file.", "checks": ["python_compileall"]})
        self.assertEqual(result["status"], "failed")
        self.assertNotEqual(result["checks"][0]["exit_code"], 0)
        self.assertIn("bad.py", result["git_status"])
        self.assertIn("def broken", result["diff"])

    def test_malformed_model_tool_arguments_produce_retrievable_failure(self) -> None:
        self.server.jobs.model = FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "write_file", "arguments": "{bad json"}}]},
        ])
        _, result = self.post({"kind": "edit", "workspace": "fixture", "instruction": "Change a file."})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "JSONDecodeError")
        _, stored = self.get_json(f"/v1/jobs/{result['id']}")
        self.assertEqual(stored, result)

    def test_job_is_retrievable_after_server_restart(self) -> None:
        _, result = self.post({"kind": "edit", "workspace": "fixture", "instruction": "Change hello."})
        port = self.server.server_port
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        root = Path(self.temp_dir.name)
        config = EditorSettings(root / "worktrees", root / "state", root / "artifacts")
        self.server = WorkerServer(("127.0.0.1", port), config, FakeModel([]))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        _, stored = self.get_json(f"/v1/jobs/{result['id']}")
        self.assertEqual(stored["id"], result["id"])
        self.assertEqual(stored["diff"], result["diff"])


class WorkspaceSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.repo = init_repo(self.root)
        self.workspace = Workspace(self.root / "worktrees", "fixture", 1_000_000, 65_536)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rejects_workspace_traversal(self) -> None:
        with self.assertRaises(JobRejected):
            Workspace(self.root / "worktrees", "../fixture", 1000, 1000)

    def test_rejects_file_traversal_and_absolute_path(self) -> None:
        for path in ("../secret", str((self.root / "secret").resolve())):
            with self.subTest(path=path), self.assertRaises(JobRejected):
                self.workspace.read_file(path)

    def test_rejects_symlink_escape_for_reads_and_writes(self) -> None:
        outside = self.root / "secret.txt"
        outside.write_text("secret\n", encoding="utf-8")
        link = self.repo / "escape.txt"
        try:
            link.symlink_to(outside)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        for operation in (lambda: self.workspace.read_file("escape.txt"), lambda: self.workspace.write_file("escape.txt", "changed")):
            with self.subTest(operation=operation), self.assertRaises(JobRejected):
                operation()
        self.assertEqual(outside.read_text(encoding="utf-8"), "secret\n")

    def test_rejects_binary_and_oversize_files(self) -> None:
        (self.repo / "binary.dat").write_bytes(b"a\x00b")
        (self.repo / "large.txt").write_bytes(b"x" * (self.workspace.max_file_bytes + 1))
        for path in ("binary.dat", "large.txt"):
            with self.subTest(path=path), self.assertRaises(JobRejected):
                self.workspace.read_file(path)

    def test_read_file_returns_bounded_line_ranges(self) -> None:
        (self.repo / "lines.txt").write_text(
            "".join(f"line {number}\n" for number in range(1, 501)), encoding="utf-8"
        )
        excerpt = self.workspace.read_file("lines.txt", 120, 125)
        self.assertTrue(excerpt.startswith("[lines 120-125 of 500]\n"))
        self.assertIn("line 120", excerpt)
        self.assertIn("line 125", excerpt)
        self.assertNotIn("line 119", excerpt)
        with self.assertRaisesRegex(JobRejected, "exceeds 400 lines"):
            self.workspace.read_file("lines.txt", 1, 401)

    def test_requires_clean_repository(self) -> None:
        (self.repo / "hello.txt").write_text("dirty\n", encoding="utf-8")
        with self.assertRaises(JobRejected):
            self.workspace.require_clean()

    def test_rejects_unapproved_check(self) -> None:
        with self.assertRaises(JobRejected):
            self.workspace.run_check("shell", {"git_diff_check"})

    def test_rejects_oversize_write(self) -> None:
        with self.assertRaises(JobRejected):
            self.workspace.write_file("large.txt", "x" * (self.workspace.max_file_bytes + 1))

    def test_python_checks_do_not_create_bytecode_artifacts(self) -> None:
        tests = self.repo / "tests"
        tests.mkdir()
        (tests / "test_clean.py").write_text(
            "import unittest\nclass CleanTest(unittest.TestCase):\n    def test_ok(self): self.assertTrue(True)\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "add test"], cwd=self.repo, check=True)
        for check in ("python_unittest", "python_compileall"):
            with self.subTest(check=check):
                result = self.workspace.run_check(check, {check})
                self.assertEqual(result["exit_code"], 0, result["output"])
                self.assertFalse(list(self.repo.rglob("__pycache__")))

    def test_unittest_check_rejects_zero_discovered_tests(self) -> None:
        tests = self.repo / "tests"
        tests.mkdir()
        result = self.workspace.run_check("python_unittest", {"python_unittest"})
        self.assertEqual(result["exit_code"], 1)
        self.assertIn("found zero tests", result["output"])

    def test_exact_replacement_requires_one_match(self) -> None:
        with self.assertRaises(JobRejected):
            self.workspace.replace_text("hello.txt", "missing", "new")

    def test_line_range_replacement_uses_recent_line_coordinates(self) -> None:
        (self.repo / "hello.txt").write_text("one\ntwo\nthree\n", encoding="utf-8")
        result = self.workspace.replace_lines("hello.txt", 2, 2, "changed\n")
        self.assertEqual(result, "updated hello.txt lines 2-2")
        self.assertEqual(
            (self.repo / "hello.txt").read_text(encoding="utf-8"),
            "one\nchanged\nthree\n",
        )
        with self.assertRaisesRegex(JobRejected, "range is invalid"):
            self.workspace.replace_lines("hello.txt", 4, 4, "nope\n")

    def test_structured_insert_uses_unique_anchor_and_literal_lines(self) -> None:
        (self.repo / "hello.txt").write_text("alpha\nanchor here\nomega\n", encoding="utf-8")
        result = self.workspace.insert_after(
            "hello.txt", "anchor here", ["    first()", "    second()"]
        )
        self.assertEqual(result, "inserted 2 lines after line 2 in hello.txt")
        self.assertEqual(
            (self.repo / "hello.txt").read_text(encoding="utf-8"),
            "alpha\nanchor here\n    first()\n    second()\nomega\n",
        )
        with self.assertRaisesRegex(JobRejected, "exactly once"):
            self.workspace.insert_after("hello.txt", "missing", ["line"])
        with self.assertRaisesRegex(JobRejected, "without newline"):
            self.workspace.insert_after("hello.txt", "anchor here", ["bad\nline"])

    def test_qwen_text_tool_markup_is_strictly_adapted(self) -> None:
        calls = parse_text_tool_calls(
            "<function=replace_text><parameter=path>hello.txt</parameter>"
            "<parameter=old>hello</parameter><parameter=new>goodbye</parameter></function>"
        )
        self.assertEqual(calls[0]["function"]["name"], "replace_text")
        self.assertEqual(calls[0]["function"]["arguments"]["path"], "hello.txt")
        self.assertEqual(parse_text_tool_calls("please run a shell"), [])

    def test_qwen_json_tool_envelope_is_strictly_adapted(self) -> None:
        calls = parse_text_tool_calls(
            '{"name":"read_file","arguments":{"path":"hello.txt","start_line":1}}'
        )
        self.assertEqual(calls[0]["function"]["name"], "read_file")
        self.assertEqual(calls[0]["function"]["arguments"]["path"], "hello.txt")
        self.assertTrue(calls[0]["text_fallback"])
        self.assertEqual(
            parse_text_tool_calls(
                '{"name":"read_file","arguments":{"path":"hello.txt"},"extra":true}'
            ),
            [],
        )
        wrapped = parse_text_tool_calls(
            '<tool_call>\n{"name":"read_file","arguments":{"path":"hello.txt"}}\n</tool_call>'
        )
        self.assertEqual(wrapped[0]["function"]["name"], "read_file")
        multiple = parse_text_tool_calls(
            '{"name":"read_file","arguments":{"path":"one.py"}}\n'
            '{"name":"read_file","arguments":{"path":"two.py"}}'
        )
        self.assertEqual([call["function"]["arguments"]["path"] for call in multiple], ["one.py", "two.py"])


class JobRunnerSafetyTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        init_repo(self.root)
        self.config = EditorSettings(self.root / "worktrees", self.root / "state", self.root / "artifacts")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rejects_unsupported_checks_and_request_limits(self) -> None:
        runner = JobRunner(self.config, FakeModel([]))
        invalid = [
            {"kind": "edit", "workspace": "fixture", "instruction": "x", "checks": ["shell"]},
            {"kind": "edit", "workspace": "fixture", "instruction": "x", "checks": ["git_diff_check"] * 6},
            {"kind": "edit", "workspace": "fixture", "instruction": "x" * 8001},
        ]
        for request in invalid:
            with self.subTest(request=request), self.assertRaises(JobRejected):
                runner.run(request)

    def test_rejects_concurrent_job(self) -> None:
        model = BlockingModel()
        runner = JobRunner(self.config, model)
        thread = threading.Thread(target=runner.run, args=({"kind": "edit", "workspace": "fixture", "instruction": "first"},))
        thread.start()
        self.assertTrue(model.entered.wait(timeout=1))
        try:
            with self.assertRaisesRegex(JobRejected, "already running"):
                runner.run({"kind": "edit", "workspace": "fixture", "instruction": "second"})
        finally:
            model.release.set()
            thread.join(timeout=2)

    def test_unknown_model_tool_fails_with_evidence(self) -> None:
        runner = JobRunner(self.config, FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "shell", "arguments": {}}}]},
        ]))
        result = runner.run({"kind": "edit", "workspace": "fixture", "instruction": "Run something."})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error"], "JobRejected")
        self.assertEqual(result["diff"], "")

    def test_failed_exact_replace_can_recover_with_line_range(self) -> None:
        runner = JobRunner(self.config, FakeModel([
            {"role": "assistant", "tool_calls": [{"function": {"name": "replace_text", "arguments": {
                "path": "hello.txt", "old": "missing", "new": "goodbye"
            }}}]},
            {"role": "assistant", "tool_calls": [{"function": {"name": "replace_lines", "arguments": {
                "path": "hello.txt", "start_line": 1, "end_line": 1, "new": "goodbye world\n"
            }}}]},
            {"role": "assistant", "tool_calls": [{"function": {
                "name": "finish", "arguments": {"summary": "Recovered."}
            }}]},
        ]))
        result = runner.run({"kind": "edit", "workspace": "fixture", "instruction": "Change it."})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["tool_calls"][0]["result"]["accepted"], False)
        self.assertIn("+goodbye world", result["diff"])

    def test_repeated_identical_call_fails_boundedly(self) -> None:
        call = {"role": "assistant", "tool_calls": [{"function": {
            "name": "read_file", "arguments": {"path": "hello.txt"}
        }}]}
        runner = JobRunner(self.config, FakeModel([call] * 5))
        result = runner.run({"kind": "edit", "workspace": "fixture", "instruction": "Change it."})
        self.assertEqual(result["status"], "failed")
        self.assertIn("repeated the same read_file call", result["message"])
        self.assertEqual(len(result["tool_calls"]), 4)

    def test_model_must_explicitly_finish(self) -> None:
        runner = JobRunner(self.config, FakeModel([
            {"role": "assistant", "content": "done"},
        ]))
        result = runner.run({"kind": "edit", "workspace": "fixture", "instruction": "Change it."})
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["message"], "model stopped without calling finish")

    def test_old_tool_results_are_compacted(self) -> None:
        messages = [
            {"role": "tool", "tool_name": "read_file", "content": "a" * 100},
            {"role": "tool", "tool_name": "search", "content": "b" * 100},
            {"role": "tool", "tool_name": "read_file", "content": "latest"},
        ]
        JobRunner._compact_tool_results(messages, keep=1)
        self.assertIn('"compacted": true', messages[0]["content"])
        self.assertIn('"compacted": true', messages[1]["content"])
        self.assertEqual(messages[2]["content"], "latest")


if __name__ == "__main__":
    unittest.main()
