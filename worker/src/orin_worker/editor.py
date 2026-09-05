from __future__ import annotations

import json
import html
import os
import re
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


class JobRejected(ValueError):
    pass


class JobFailed(RuntimeError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _trim(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated {len(value) - limit} characters]"


@dataclass(frozen=True)
class EditorSettings:
    worktree_root: Path
    state_dir: Path
    artifact_dir: Path
    model_url: str = "http://127.0.0.1:11434"
    model: str = "qwen3-coder:30b-a3b-q4_K_M"
    max_iterations: int = 30
    max_file_bytes: int = 1_000_000
    max_output_chars: int = 65_536
    max_read_lines: int = 400
    timeout_seconds: int = 300
    think: bool = False
    context_tokens: int = 32_768


CHECKS: dict[str, list[str]] = {
    "git_diff_check": ["git", "diff", "--check"],
    "python_unittest": [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"],
    "python_compileall": [
        sys.executable, "-B", "-c",
        "import pathlib; [compile(p.read_bytes(), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py') if '.git' not in p.parts]",
    ],
}


class Workspace:
    def __init__(
        self, root: Path, name: str, max_file_bytes: int, max_output_chars: int,
        max_read_lines: int = 400,
    ):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
            raise JobRejected("workspace must be a simple name")
        base = root.resolve()
        path = (base / name).resolve()
        if path.parent != base or not path.is_dir():
            raise JobRejected("workspace does not exist")
        self.root = path
        self.max_file_bytes = max_file_bytes
        self.max_output_chars = max_output_chars
        self.max_read_lines = max_read_lines
        self.max_observation_chars = min(max_output_chars, 16_384)
        probe = self._run(["git", "rev-parse", "--show-toplevel"])
        if probe.returncode or Path(probe.stdout.strip()).resolve() != self.root:
            raise JobRejected("workspace must be the root of a Git worktree")

    def _path(self, relative: str, *, may_create: bool = False) -> Path:
        candidate = Path(relative)
        if candidate.is_absolute() or not relative or "\x00" in relative:
            raise JobRejected("path must be relative to the workspace")
        target = self.root / candidate
        resolved = target.parent.resolve() / target.name if may_create else target.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise JobRejected("path escapes the workspace")
        return resolved

    def _run(self, argv: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                argv, cwd=self.root, text=True, capture_output=True, timeout=timeout,
                stdin=subprocess.DEVNULL, check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise JobFailed(f"approved command failed to start: {type(exc).__name__}") from exc

    def require_clean(self) -> None:
        result = self._run(["git", "status", "--porcelain=v1", "--untracked-files=all"])
        if result.returncode:
            raise JobRejected("unable to inspect workspace status")
        if result.stdout:
            raise JobRejected("workspace is not clean")

    def list_files(self, path: str = ".") -> str:
        base = self._path(path)
        if not base.is_dir():
            raise JobRejected("list path is not a directory")
        entries: list[str] = []
        for item in sorted(base.rglob("*")):
            if ".git" in item.relative_to(self.root).parts or item.is_symlink() or not item.is_file():
                continue
            entries.append(item.relative_to(self.root).as_posix())
            if len(entries) >= 1000:
                entries.append("...[file limit reached]")
                break
        return _trim("\n".join(entries), self.max_observation_chars)

    def read_file(
        self, path: str, start_line: int | None = None, end_line: int | None = None
    ) -> str:
        target = self._path(path)
        content = self._read_text(target)
        lines = content.splitlines(keepends=True)
        if start_line is None:
            start_line = 1
        if end_line is None:
            end_line = min(len(lines), start_line + self.max_read_lines - 1)
        if start_line < 1 or end_line < start_line:
            raise JobRejected("read line range is invalid")
        if end_line - start_line + 1 > self.max_read_lines:
            raise JobRejected(f"read range exceeds {self.max_read_lines} lines")
        if start_line > max(1, len(lines)):
            raise JobRejected("read start line exceeds file length")
        selected = "".join(lines[start_line - 1:end_line])
        header = f"[lines {start_line}-{min(end_line, len(lines))} of {len(lines)}]\n"
        return header + _trim(selected, self.max_observation_chars)

    def _read_text(self, target: Path) -> str:
        if not target.is_file() or target.is_symlink():
            raise JobRejected("file does not exist or is a symlink")
        if target.stat().st_size > self.max_file_bytes:
            raise JobRejected("file exceeds size limit")
        data = target.read_bytes()
        if b"\x00" in data:
            raise JobRejected("binary files are not supported")
        return data.decode("utf-8")

    def search(self, query: str, path: str = ".") -> str:
        if not query or len(query) > 256 or "\n" in query:
            raise JobRejected("search query is invalid")
        base = self._path(path)
        matches: list[str] = []
        files = [base] if base.is_file() else sorted(base.rglob("*"))
        for item in files:
            if len(matches) >= 200:
                break
            if not item.is_file() or item.is_symlink() or ".git" in item.relative_to(self.root).parts:
                continue
            if item.stat().st_size > self.max_file_bytes:
                continue
            data = item.read_bytes()
            if b"\x00" in data:
                continue
            for number, line in enumerate(data.decode("utf-8", errors="replace").splitlines(), 1):
                if query in line:
                    matches.append(f"{item.relative_to(self.root).as_posix()}:{number}:{line}")
                    if len(matches) >= 200:
                        break
        return _trim("\n".join(matches), self.max_observation_chars)

    def replace_text(self, path: str, old: str, new: str) -> str:
        if not old:
            raise JobRejected("old text cannot be empty")
        target = self._path(path)
        content = self._read_text(target)
        count = content.count(old)
        if count != 1:
            raise JobRejected(f"old text must occur exactly once; found {count}")
        updated = content.replace(old, new, 1)
        self._write(target, updated)
        return f"updated {path}"

    def replace_lines(self, path: str, start_line: int, end_line: int, new: str) -> str:
        """Replace an inclusive, previously-read line range without matching a large text block."""
        target = self._path(path)
        content = self._read_text(target)
        lines = content.splitlines(keepends=True)
        if start_line < 1 or end_line < start_line or end_line > len(lines):
            raise JobRejected("replacement line range is invalid")
        if end_line - start_line + 1 > self.max_read_lines:
            raise JobRejected(f"replacement range exceeds {self.max_read_lines} lines")
        updated = "".join(lines[:start_line - 1]) + new + "".join(lines[end_line:])
        self._write(target, updated)
        return f"updated {path} lines {start_line}-{end_line}"

    def insert_after(self, path: str, anchor: str, lines: list[str]) -> str:
        """Insert literal lines after one unique existing line, avoiding multiline escaping."""
        if not anchor or "\n" in anchor or "\r" in anchor:
            raise JobRejected("anchor must be one nonempty line fragment")
        if not isinstance(lines, list) or not lines or len(lines) > self.max_read_lines:
            raise JobRejected("insert lines must be a nonempty bounded list")
        if any(not isinstance(line, str) or "\n" in line or "\r" in line for line in lines):
            raise JobRejected("each inserted line must be a string without newline characters")
        target = self._path(path)
        content = self._read_text(target)
        source = content.splitlines(keepends=True)
        matches = [index for index, line in enumerate(source) if anchor in line.rstrip("\r\n")]
        if len(matches) != 1:
            raise JobRejected(f"anchor line must occur exactly once; found {len(matches)}")
        newline = "\r\n" if "\r\n" in content else "\n"
        insertion = "".join(line + newline for line in lines)
        offset = matches[0] + 1
        updated = "".join(source[:offset]) + insertion + "".join(source[offset:])
        self._write(target, updated)
        return f"inserted {len(lines)} lines after line {offset} in {path}"

    def write_file(self, path: str, content: str) -> str:
        target = self._path(path, may_create=True)
        self._write(target, content)
        return f"wrote {path}"

    def _write(self, target: Path, content: str) -> None:
        encoded = content.encode("utf-8")
        if len(encoded) > self.max_file_bytes:
            raise JobRejected("new file content exceeds size limit")
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.is_symlink():
            raise JobRejected("cannot write through a symlink")
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_bytes(encoded)
        os.replace(temporary, target)

    def run_check(self, name: str, allowed: set[str]) -> dict[str, Any]:
        if name not in allowed or name not in CHECKS:
            raise JobRejected("check is not approved for this job")
        result = self._run(CHECKS[name])
        exit_code = result.returncode
        output = result.stdout + result.stderr
        if name == "python_unittest" and re.search(r"Ran 0 tests?", output):
            exit_code = 1
            output += "\nCheck failed: unittest discovery found zero tests.\n"
        return {
            "name": name,
            "exit_code": exit_code,
            "output": _trim(output, self.max_output_chars),
        }

    def evidence(self) -> tuple[str, str]:
        status = self._run(["git", "status", "--short"]).stdout
        diff = self._run(["git", "diff", "--no-ext-diff", "--binary", "HEAD", "--"]).stdout
        untracked = self._run(["git", "ls-files", "--others", "--exclude-standard"]).stdout.splitlines()
        for relative in untracked:
            result = self._run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative])
            if result.returncode in (0, 1):
                diff += result.stdout
        return _trim(status, self.max_output_chars), _trim(diff, self.max_output_chars * 4)


class OllamaClient:
    def __init__(self, base_url: str, model: str, timeout: int,
                 temperature: float = 0.0, seed: int = 0, *, think: bool = False,
                 context_tokens: int = 32_768):
        self.url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.timeout = timeout
        self.temperature = temperature
        self.seed = seed
        self.think = think
        self.context_tokens = context_tokens
        self.last_metrics: dict[str, Any] = {}

    def chat(
        self, messages: list[dict[str, Any]], tools: list[dict[str, Any]],
        timeout_seconds: float | None = None,
    ) -> dict[str, Any]:
        body = json.dumps({
            "model": self.model, "messages": messages, "tools": tools, "stream": False,
            "think": self.think,
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_ctx": self.context_tokens,
            },
        }).encode()
        request = Request(self.url, data=body, headers={"Content-Type": "application/json"})
        try:
            request_timeout = self.timeout if timeout_seconds is None else min(
                self.timeout, max(0.1, timeout_seconds)
            )
            with urlopen(request, timeout=request_timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            detail = _trim(exc.read().decode("utf-8", errors="replace"), 2000)
            raise JobFailed(f"model API returned HTTP {exc.code}: {detail}") from exc
        message = payload.get("message")
        if not isinstance(message, dict):
            raise JobFailed("model returned an invalid response")
        self.last_metrics = {
            key: payload.get(key)
            for key in (
                "total_duration", "load_duration", "prompt_eval_count",
                "prompt_eval_duration", "eval_count", "eval_duration",
            )
            if payload.get(key) is not None
        }
        return message


TOOLS = [
    {"type": "function", "function": {"name": "list_files", "description": "List text-file candidates in the assigned repository.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "read_file", "description": "Read a bounded line range from one UTF-8 text file. Defaults to its first 400 lines; use search to locate content and request a narrow range.", "parameters": {"type": "object", "required": ["path"], "properties": {"path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1}}}}},
    {"type": "function", "function": {"name": "search", "description": "Literal text search in repository files.", "parameters": {"type": "object", "required": ["query"], "properties": {"query": {"type": "string"}, "path": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "replace_text", "description": "Replace text that occurs exactly once in a file.", "parameters": {"type": "object", "required": ["path", "old", "new"], "properties": {"path": {"type": "string"}, "old": {"type": "string"}, "new": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "replace_lines", "description": "Replace an inclusive line range from a recent read_file result. Prefer this when an exact text replacement is fragile. Include any required trailing newline in new.", "parameters": {"type": "object", "required": ["path", "start_line", "end_line", "new"], "properties": {"path": {"type": "string"}, "start_line": {"type": "integer", "minimum": 1}, "end_line": {"type": "integer", "minimum": 1}, "new": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "insert_after", "description": "Insert new source lines after a unique existing line fragment. Pass each new line as a separate string without newline escapes. Prefer this for additive multiline edits.", "parameters": {"type": "object", "required": ["path", "anchor", "lines"], "properties": {"path": {"type": "string"}, "anchor": {"type": "string"}, "lines": {"type": "array", "minItems": 1, "maxItems": 400, "items": {"type": "string"}}}}}},
    {"type": "function", "function": {"name": "write_file", "description": "Write a required product or test file inside the repository. Never create scratch, demo, manual verification, or duplicate test files.", "parameters": {"type": "object", "required": ["path", "content"], "properties": {"path": {"type": "string"}, "content": {"type": "string"}}}}},
    {"type": "function", "function": {"name": "finish", "description": "Finish after edits and checks are complete.", "parameters": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}}}},
]


def parse_text_tool_calls(content: str) -> list[dict[str, Any]]:
    """Adapt strict Qwen textual tool envelopes when Ollama does not parse them."""
    calls: list[dict[str, Any]] = []
    stripped = content.strip()
    wrapped = re.fullmatch(r"<tool_call>\s*(.*?)\s*</tool_call>", stripped, re.DOTALL)
    if wrapped:
        stripped = wrapped.group(1)
    envelopes: list[Any] = []
    decoder = json.JSONDecoder()
    offset = 0
    try:
        while offset < len(stripped):
            envelope, offset = decoder.raw_decode(stripped, offset)
            envelopes.append(envelope)
            while offset < len(stripped) and stripped[offset].isspace():
                offset += 1
    except (json.JSONDecodeError, TypeError):
        envelopes = []
    if envelopes and all(
        isinstance(envelope, dict)
        and isinstance(envelope.get("name"), str)
        and isinstance(envelope.get("arguments"), dict)
        and set(envelope) == {"name", "arguments"}
        for envelope in envelopes
    ):
        return [
            {
                "function": {"name": envelope["name"], "arguments": envelope["arguments"]},
                "text_fallback": True,
            }
            for envelope in envelopes
        ]
    pattern = re.compile(r"<function=([A-Za-z_][A-Za-z0-9_]*)>(.*?)</function>", re.DOTALL)
    parameter = re.compile(r"<parameter=([A-Za-z_][A-Za-z0-9_]*)>(.*?)</parameter>", re.DOTALL)
    for match in pattern.finditer(content):
        arguments = {key: html.unescape(value.strip()) for key, value in parameter.findall(match.group(2))}
        calls.append({"function": {"name": match.group(1), "arguments": arguments}, "text_fallback": True})
    return calls


class JobRunner:
    def __init__(self, config: EditorSettings, model_client: Any | None = None):
        self.config = config
        self.model = model_client or OllamaClient(
            config.model_url, config.model, config.timeout_seconds,
            think=config.think, context_tokens=config.context_tokens,
        )
        self._lock = threading.Lock()

    @property
    def jobs_dir(self) -> Path:
        return self.config.state_dir / "jobs"

    def load(self, job_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"[0-9a-f]{32}", job_id):
            return None
        path = self.jobs_dir / f"{job_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None

    def _save(self, record: dict[str, Any]) -> None:
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        path = self.jobs_dir / f"{record['id']}.json"
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, path)

    def run(self, request: dict[str, Any]) -> dict[str, Any]:
        if not self._lock.acquire(blocking=False):
            raise JobRejected("another edit job is already running")
        try:
            return self._run(request)
        finally:
            self._lock.release()

    def _run(self, request: dict[str, Any]) -> dict[str, Any]:
        if set(request) - {"kind", "workspace", "instruction", "checks"}:
            raise JobRejected("request contains unsupported fields")
        if request.get("kind") != "edit":
            raise JobRejected("kind must be edit")
        instruction = request.get("instruction")
        if not isinstance(instruction, str) or not instruction.strip() or len(instruction) > 8000:
            raise JobRejected("instruction must contain 1 to 8000 characters")
        checks = request.get("checks", ["git_diff_check"])
        if not isinstance(checks, list) or len(checks) > 5 or any(x not in CHECKS for x in checks):
            raise JobRejected("checks must contain only approved check IDs")
        workspace = Workspace(
            self.config.worktree_root, request.get("workspace", ""),
            self.config.max_file_bytes, self.config.max_output_chars,
            self.config.max_read_lines,
        )
        workspace.require_clean()
        job_id = uuid.uuid4().hex
        record: dict[str, Any] = {
            "id": job_id, "kind": "edit", "workspace": request["workspace"],
            "instruction": instruction, "checks_requested": checks, "status": "running",
            "created_at": _now(), "tool_calls": [], "model_turns": [],
        }
        self._save(record)
        started = time.monotonic()
        messages: list[dict[str, Any]] = [{
            "role": "system",
            "content": (
                "You are a bounded coding editor. Work only through the provided tools. "
                "Inspect before editing, make the smallest change satisfying the instruction, "
                "Use insert_after with an array of literal lines for additive multiline edits. Use replace_lines on a recently read narrow range only when existing lines must change. "
                "follow the repository's existing file and test layout, and avoid ad-hoc verification scripts. "
                "If the instruction does not require a new file or new tests, do not create any new file; use approved checks for verification. "
                "When adding an alias or fallback, preserve existing behavior and precedence and check overlap cases. "
                "A test check that discovers zero tests is a failure; place tests where the approved check finds them. "
                "Checks run automatically after finish; do not request or simulate check tools. "
                "Call finish only after the required edits are complete. Do not ask for shell, network, "
                "commits, credentials, or paths outside the assigned repository."
            ),
        }, {"role": "user", "content": f"Instruction: {instruction}\nApproved checks: {', '.join(checks)}"}]
        summary = "Model completed without a summary."
        repeated_calls: dict[str, int] = {}
        try:
            for ordinal in range(1, self.config.max_iterations + 1):
                if time.monotonic() - started > self.config.timeout_seconds:
                    raise JobFailed("job time limit exceeded")
                remaining = self.config.timeout_seconds - (time.monotonic() - started)
                if remaining <= 0:
                    raise JobFailed("job time limit exceeded")
                request_chars = len(json.dumps(messages, separators=(",", ":")))
                turn_started = time.monotonic()
                try:
                    message = self.model.chat(messages, TOOLS, timeout_seconds=remaining)
                except TypeError as exc:
                    if "timeout_seconds" not in str(exc):
                        raise
                    message = self.model.chat(messages, TOOLS)
                turn = {
                    "ordinal": ordinal,
                    "wall_seconds": round(time.monotonic() - turn_started, 3),
                    "request_chars": request_chars,
                    "response_content": _trim(str(message.get("content") or ""), 2000),
                    "native_tool_call_count": len(message.get("tool_calls") or []),
                }
                metrics = getattr(self.model, "last_metrics", None)
                if metrics:
                    turn["ollama"] = metrics
                record["model_turns"].append(turn)
                messages.append(message)
                calls = message.get("tool_calls") or parse_text_tool_calls(str(message.get("content") or ""))
                if not calls:
                    raise JobFailed("model stopped without calling finish")
                finished = False
                for call in calls:
                    function = call.get("function", {})
                    name = function.get("name")
                    arguments = function.get("arguments", {})
                    if isinstance(arguments, str):
                        arguments = json.loads(arguments)
                    signature = json.dumps(
                        {"name": name, "arguments": arguments}, sort_keys=True, separators=(",", ":")
                    )
                    repeated_calls[signature] = repeated_calls.get(signature, 0) + 1
                    repeat_count = repeated_calls[signature]
                    if repeat_count >= 5:
                        raise JobFailed(f"model repeated the same {name} call without progress")
                    try:
                        result = self._invoke(workspace, name, arguments, set(checks))
                    except JobRejected as exc:
                        if name not in {"replace_text", "replace_lines", "insert_after"}:
                            raise
                        result = {"accepted": False, "error": str(exc)}
                    if name in {"replace_text", "replace_lines", "insert_after", "write_file"} and not (
                        isinstance(result, dict) and result.get("accepted") is False
                    ):
                        repeated_calls.clear()
                    record["tool_calls"].append({"ordinal": ordinal, "name": name, "result": result})
                    if name == "finish":
                        summary = arguments["summary"]
                        finished = True
                    if call.get("text_fallback"):
                        messages.append({"role": "user", "content": f"Tool result for {name}:\n{json.dumps(result)}\nContinue using a tool call."})
                    else:
                        messages.append({"role": "tool", "tool_name": name, "content": json.dumps(result)})
                    if repeat_count == 3:
                        messages.append({
                            "role": "user",
                            "content": (
                                "Recovery required: this identical tool call has made no progress three times. "
                                "Do not repeat it. Re-read a narrow current range, then use replace_lines or choose a different edit."
                            ),
                        })
                self._save(record)
                if finished:
                    break
                self._compact_tool_results(messages)
            else:
                raise JobFailed("model tool-iteration limit exceeded")
            check_results = [workspace.run_check(name, set(checks)) for name in checks]
            status, diff = workspace.evidence()
            record.update({
                "status": (
                    "completed" if diff and all(x["exit_code"] == 0 for x in check_results)
                    else "no_change" if not diff and all(x["exit_code"] == 0 for x in check_results)
                    else "failed"
                ),
                "summary": _trim(summary, 4000), "checks": check_results,
                "git_status": status, "diff": diff, "finished_at": _now(),
            })
        except Exception as exc:
            status, diff = workspace.evidence()
            record.update({"status": "failed", "error": type(exc).__name__, "message": str(exc),
                           "git_status": status, "diff": diff, "finished_at": _now()})
        self._save(record)
        artifact = self.config.artifact_dir / "jobs" / job_id
        artifact.mkdir(parents=True, exist_ok=True)
        (artifact / "diff.patch").write_text(record.get("diff", ""), encoding="utf-8")
        return record

    @staticmethod
    def _compact_tool_results(messages: list[dict[str, Any]], keep: int = 2) -> None:
        tool_indexes = [
            index for index, message in enumerate(messages) if message.get("role") == "tool"
        ]
        for index in tool_indexes[:-keep]:
            message = messages[index]
            content = str(message.get("content", ""))
            message["content"] = json.dumps({
                "compacted": True,
                "tool_name": message.get("tool_name"),
                "original_chars": len(content),
            })

    def _invoke(self, workspace: Workspace, name: str, args: dict[str, Any], allowed: set[str]) -> Any:
        if not isinstance(args, dict):
            raise JobRejected("tool arguments must be an object")
        if name == "list_files":
            return workspace.list_files(args.get("path", "."))
        if name == "read_file":
            return workspace.read_file(
                args["path"], args.get("start_line"), args.get("end_line")
            )
        if name == "search":
            return workspace.search(args["query"], args.get("path", "."))
        if name == "replace_text":
            return workspace.replace_text(args["path"], args["old"], args["new"])
        if name == "replace_lines":
            return workspace.replace_lines(
                args["path"], args["start_line"], args["end_line"], args["new"]
            )
        if name == "insert_after":
            return workspace.insert_after(args["path"], args["anchor"], args["lines"])
        if name == "write_file":
            return workspace.write_file(args["path"], args["content"])
        if name == "run_check":
            return workspace.run_check(args["name"], allowed)
        if name == "finish":
            return {"accepted": True}
        raise JobRejected("model requested an unknown tool")
