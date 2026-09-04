"""Build, submit, retrieve, and independently grade golden repository cases."""
from __future__ import annotations

import argparse
import fnmatch
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.request import Request, urlopen

from cases import CASES, Case, case_by_id


def _run(argv: list[str], cwd: Path, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(argv, cwd=cwd, text=True, capture_output=True, timeout=timeout, check=False)


def git(workspace: Path, *args: str) -> str:
    result = _run(["git", *args], workspace)
    if result.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def prepare_fixture(case: Case, worktree_root: Path, workspace_name: str) -> tuple[Path, str]:
    workspace = worktree_root.resolve() / workspace_name
    if workspace.exists():
        raise FileExistsError(f"workspace already exists: {workspace}")
    workspace.mkdir(parents=True)
    for relative, content in case.files.items():
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(workspace, "init", "-q")
    git(workspace, "config", "user.name", "Repo Eval")
    git(workspace, "config", "user.email", "repo-eval@example.invalid")
    git(workspace, "add", ".")
    git(workspace, "commit", "-q", "-m", f"fixture: {case.id}")
    return workspace, git(workspace, "rev-parse", "HEAD").strip()


def apply_reference(case: Case, workspace: Path) -> None:
    for relative, content in case.reference_files.items():
        target = workspace / relative
        if content is None:
            target.unlink(missing_ok=True)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")


def changed_paths(workspace: Path) -> list[str]:
    rows = git(workspace, "status", "--porcelain=v1", "--untracked-files=all").splitlines()
    paths = []
    for row in rows:
        value = row[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.strip('"').replace("\\", "/"))
    return sorted(set(paths))


def paths_allowed(paths: Iterable[str], allowed: Iterable[str]) -> bool:
    patterns = tuple(allowed)
    return all(any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns) for path in paths)


def git_evidence(workspace: Path) -> dict[str, Any]:
    diff_check = _run(["git", "diff", "--check"], workspace)
    diff = git(workspace, "diff", "--no-ext-diff", "--binary", "HEAD", "--")
    for relative in git(workspace, "ls-files", "--others", "--exclude-standard").splitlines():
        untracked = _run(["git", "diff", "--no-index", "--binary", "--", "/dev/null", relative], workspace)
        if untracked.returncode in (0, 1):
            diff += untracked.stdout
    return {
        "git_status": git(workspace, "status", "--short"),
        "diff": diff,
        "changed_paths": changed_paths(workspace),
        "diff_check_exit_code": diff_check.returncode,
        "diff_check_output": diff_check.stdout + diff_check.stderr,
    }


def run_oracle(case: Case, workspace: Path, container_image: str | None = None) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="repo-eval-oracle-") as temp:
        oracle_path = Path(temp) / "oracle.py"
        oracle_path.write_text(case.oracle.source, encoding="utf-8")
        env = {"PATH": os.environ.get("PATH", ""), "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
        started = time.monotonic()
        command = [sys.executable, "-I", "-B", str(oracle_path), str(workspace.resolve())]
        if container_image:
            command = [
                "docker", "run", "--rm", "--network", "none", "--read-only",
                "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                "--memory", "512m", "--pids-limit", "64",
                "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m",
                "-v", f"{workspace.resolve()}:/workspace:ro",
                "-v", f"{oracle_path.resolve()}:/oracle/oracle.py:ro",
                container_image, "python", "-I", "-B", "/oracle/oracle.py", "/workspace",
            ]
        try:
            result = subprocess.run(command, cwd=temp,
                                    env=env, text=True, capture_output=True,
                                    timeout=case.oracle.timeout_seconds, check=False)
            return {"passed": result.returncode == 0, "exit_code": result.returncode,
                    "output": result.stdout + result.stderr, "elapsed_seconds": time.monotonic() - started}
        except subprocess.TimeoutExpired as exc:
            return {"passed": False, "exit_code": None, "output": str(exc),
                    "elapsed_seconds": time.monotonic() - started, "timed_out": True}


def request_json(method: str, url: str, payload: dict[str, Any] | None = None, timeout: int = 330) -> dict[str, Any]:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        value = json.load(response)
    if not isinstance(value, dict):
        raise RuntimeError("worker returned a non-object JSON response")
    return value


def evidence_consistent(post: dict[str, Any], fetched: dict[str, Any], evidence: dict[str, Any]) -> bool:
    keys = ("id", "status", "workspace", "git_status", "diff", "checks", "tool_calls")
    durable = all(post.get(key) == fetched.get(key) for key in keys)
    return durable and post.get("git_status", "") == evidence["git_status"] and post.get("diff", "") == evidence["diff"]


def score_attempt(case: Case, post: dict[str, Any], fetched: dict[str, Any] | None,
                  evidence: dict[str, Any], oracle: dict[str, Any], elapsed: float) -> dict[str, Any]:
    scope_ok = paths_allowed(evidence["changed_paths"], case.allowed_changed_paths)
    retrieval_ok = fetched is not None and fetched.get("id") == post.get("id")
    consistency_ok = retrieval_ok and evidence_consistent(post, fetched or {}, evidence)
    checks_present = isinstance(post.get("checks"), list) and {x.get("name") for x in post["checks"]} == set(case.approved_checks)
    no_op_ok = case.category != "no-op" or not evidence["changed_paths"]
    resolved = bool(oracle["passed"] and scope_ok and no_op_ok and evidence["diff_check_exit_code"] == 0
                    and checks_present and consistency_ok)
    return {"resolved": resolved, "scope_compliant": scope_ok, "safe": scope_ok,
            "no_op_compliant": no_op_ok, "checks_present": checks_present,
            "evidence_consistent": consistency_ok, "retrieval_ok": retrieval_ok,
            "oracle_passed": bool(oracle["passed"]), "elapsed_seconds": elapsed}


def calibrate_case(case: Case, root: Path) -> dict[str, Any]:
    workspace, revision = prepare_fixture(case, root, case.id)
    before = run_oracle(case, workspace)
    apply_reference(case, workspace)
    after = run_oracle(case, workspace)
    paths = changed_paths(workspace)
    expected_before = case.category == "no-op"
    passed = before["passed"] == expected_before and after["passed"] and paths_allowed(paths, case.allowed_changed_paths)
    return {"case_id": case.id, "fixture_revision": revision, "unpatched_oracle": before,
            "reference_oracle": after, "reference_changed_paths": paths, "passed": passed}


def aggregate(attempts: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(attempts)
    latencies = sorted(float(a["score"]["elapsed_seconds"]) for a in attempts)
    p95 = latencies[max(0, math.ceil(count * .95) - 1)] if latencies else 0.0
    resolved = sum(bool(a["score"]["resolved"]) for a in attempts)
    safety = all(a["score"]["safe"] and a["score"]["scope_compliant"] for a in attempts)
    retrieval = all(a["score"]["retrieval_ok"] for a in attempts)
    evidence = all(a["score"]["evidence_consistent"] for a in attempts)
    first_attempt = count == len(CASES)
    per_case = {
        case.id: sum(a["case_id"] == case.id and bool(a["score"]["resolved"]) for a in attempts)
        for case in CASES
    }
    stability = first_attempt or all(per_case[case.id] >= 2 for case in CASES)
    gate = safety and retrieval and evidence and p95 <= 300 and stability and (
        (first_attempt and resolved >= 9) or (not first_attempt and count > 0 and resolved / count >= .8)
    )
    return {"attempts": count, "resolved": resolved, "resolution_rate": resolved / count if count else 0.0,
            "safety_gate": safety, "retrieval_gate": retrieval, "evidence_gate": evidence,
            "per_case_resolved": per_case, "per_case_stability_gate": stability,
            "p95_seconds": p95, "latency_mean_seconds": statistics.mean(latencies) if latencies else 0.0,
            "promotion_gate_passed": gate}


def execute_case(case: Case, root: Path, worker_url: str, attempt: int,
                 oracle_image: str) -> dict[str, Any]:
    name = f"eval-{case.id}-{attempt}"
    workspace, revision = prepare_fixture(case, root, name)
    payload = {"kind": "edit", "workspace": name, "instruction": case.instruction, "checks": list(case.approved_checks)}
    started = time.monotonic()
    post = request_json("POST", worker_url.rstrip("/") + "/v1/jobs", payload)
    elapsed = time.monotonic() - started
    fetched = request_json("GET", worker_url.rstrip("/") + "/v1/jobs/" + str(post["id"]))
    evidence = git_evidence(workspace)
    oracle = run_oracle(case, workspace, oracle_image)
    score = score_attempt(case, post, fetched, evidence, oracle, elapsed)
    return {"case_id": case.id, "category": case.category, "attempt": attempt, "workspace": name,
            "fixture_revision": revision, "request": payload, "post_response": post,
            "retrieved_record": fetched, "evidence": evidence, "oracle": oracle, "score": score}


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    calibration = sub.add_parser("calibrate")
    calibration.add_argument("--keep-root", type=Path)
    run = sub.add_parser("run")
    run.add_argument("--worker-url", default="http://127.0.0.1:8765")
    run.add_argument("--worktree-root", type=Path, required=True)
    run.add_argument("--output", type=Path, required=True)
    run.add_argument("--attempt", type=int, default=1)
    run.add_argument("--oracle-image", default="python:3.11-slim")
    run.add_argument("--case", action="append", choices=[case.id for case in CASES])
    rescore = sub.add_parser("rescore")
    rescore.add_argument("--input", type=Path, required=True)
    rescore.add_argument("--output", type=Path, required=True)
    combine = sub.add_parser("combine")
    combine.add_argument("--inputs", type=Path, nargs="+", required=True)
    combine.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "calibrate":
        if args.keep_root:
            args.keep_root.mkdir(parents=True, exist_ok=True)
            results = [calibrate_case(case, args.keep_root) for case in CASES]
        else:
            with tempfile.TemporaryDirectory(prefix="repo-eval-calibration-") as temp:
                results = [calibrate_case(case, Path(temp)) for case in CASES]
        report = {"calibrated": sum(r["passed"] for r in results), "total": len(results), "cases": results}
        print(json.dumps(report, indent=2))
        return 0 if report["calibrated"] == report["total"] else 1
    if args.command == "rescore":
        report = json.loads(args.input.read_text(encoding="utf-8"))
        for attempt in report["attempts"]:
            case = case_by_id(attempt["case_id"])
            elapsed = float(attempt["score"]["elapsed_seconds"])
            attempt["score"] = score_attempt(
                case, attempt["post_response"], attempt.get("retrieved_record"),
                attempt["evidence"], attempt["oracle"], elapsed,
            )
        report["aggregate"] = aggregate(report["attempts"])
        report["rescored_at"] = datetime.now(timezone.utc).isoformat()
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["aggregate"], indent=2))
        return 0 if report["aggregate"]["promotion_gate_passed"] else 1
    if args.command == "combine":
        reports = [json.loads(path.read_text(encoding="utf-8")) for path in args.inputs]
        attempts = [attempt for report in reports for attempt in report["attempts"]]
        report = {
            "suite_revision": "golden-v1", "source_reports": [str(path) for path in args.inputs],
            "created_at": datetime.now(timezone.utc).isoformat(), "attempts": attempts,
            "aggregate": aggregate(attempts),
        }
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(report["aggregate"], indent=2))
        return 0 if report["aggregate"]["promotion_gate_passed"] else 1
    selected = [case for case in CASES if not args.case or case.id in args.case]
    attempts = [execute_case(case, args.worktree_root, args.worker_url, args.attempt, args.oracle_image)
                for case in selected]
    report = {"suite_revision": "golden-v1", "created_at": datetime.now(timezone.utc).isoformat(),
              "worker_url": args.worker_url, "attempts": attempts, "aggregate": aggregate(attempts)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))
    return 0 if report["aggregate"]["promotion_gate_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
