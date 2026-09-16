from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Sequence

from control_plane_reviewer.review import ReviewError, _now, _run, _trim, canonical_patch, changed_paths, check_command, state_fingerprint, validate_workspace


PROMOTION_CHECKS = ("git_diff_check", "python_unittest", "python_compileall")


def _git(root: Path, *args: str) -> str:
    process = _run(root, ("git", *args))
    if process.returncode:
        raise ReviewError(f"promotion Git operation failed: {_trim(process.stderr).strip()}")
    return process.stdout


def _load_review(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"invalid review artifact: {type(exc).__name__}") from exc
    required = {"review_id", "worker_job_id", "patch_sha256", "changed_paths", "verdict", "state_before", "state_after"}
    if not isinstance(value, dict) or required - value.keys() or value.get("schema_version") != 1:
        raise ReviewError("review artifact has an unsupported schema")
    if value["verdict"] != "approve" or value["state_before"] != value["state_after"]:
        raise ReviewError("review artifact is not an unchanged approval")
    if not re.fullmatch(r"[0-9a-f]{64}", value["patch_sha256"]):
        raise ReviewError("review artifact has an invalid patch identity")
    if not isinstance(value["changed_paths"], list) or not value["changed_paths"]:
        raise ReviewError("review artifact must contain changed paths")
    return value


def _run_ci_checks(root: Path) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for check_id in PROMOTION_CHECKS:
        began = time.monotonic()
        try:
            process = _run(root, check_command(root, check_id))
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ReviewError(f"mandatory CI check {check_id} unavailable: {type(exc).__name__}") from exc
        output = process.stdout + process.stderr
        passed = process.returncode == 0
        if check_id == "python_unittest" and re.search(r"Ran 0 tests?", output):
            passed = False
        results.append({"id": check_id, "status": "passed" if passed else "failed",
                        "exit_code": process.returncode, "duration_ms": round((time.monotonic() - began) * 1000),
                        "output": _trim(output)})
        if not passed:
            raise ReviewError(f"mandatory CI check failed: {check_id}")
    return results


def promote(review_path: Path, workspace: Path, message: str, output: Path) -> dict[str, Any]:
    root = validate_workspace(workspace)
    review = _load_review(review_path)
    if not message.strip() or "\n" in message or len(message) > 120:
        raise ReviewError("commit message must be a 1 to 120 character subject")
    destination = output.resolve()
    if destination == root or root in destination.parents or destination.exists():
        raise ReviewError("promotion output must be new and outside the workspace")
    cached = _run(root, ("git", "diff", "--cached", "--quiet", "HEAD", "--"))
    if cached.returncode != 0:
        raise ReviewError("index is not clean")
    patch = canonical_patch(root)
    patch_id = hashlib.sha256(patch.encode("utf-8", errors="surrogateescape")).hexdigest()
    paths = changed_paths(root)
    if patch_id != review["patch_sha256"] or paths != review["changed_paths"]:
        raise ReviewError("current submission does not match the approved review")
    attributes = _run(root, ("git", "check-attr", "-z", "filter", "--", *paths), binary=True)
    if attributes.returncode:
        raise ReviewError("unable to inspect content filters")
    attribute_tokens = [item.decode("utf-8", errors="replace") for item in attributes.stdout.split(b"\0") if item]
    if any(attribute_tokens[index] not in {"unspecified", "unset"} for index in range(2, len(attribute_tokens), 3)):
        raise ReviewError("reviewed paths use an executable Git content filter")
    before = state_fingerprint(root)
    checks = _run_ci_checks(root)
    if state_fingerprint(root) != before:
        raise ReviewError("a mandatory CI check changed repository state")
    parent = _git(root, "rev-parse", "HEAD").strip()
    stage = _run(root, ("git", "add", "--all", "--", *paths))
    if stage.returncode:
        raise ReviewError(f"unable to stage reviewed paths: {_trim(stage.stderr).strip()}")
    staged = _git(root, "diff", "--cached", "--binary", "HEAD", "--")
    staged_id = hashlib.sha256(staged.encode("utf-8", errors="surrogateescape")).hexdigest()
    if staged_id != patch_id:
        _run(root, ("git", "reset", "--quiet", "HEAD", "--", *paths))
        raise ReviewError("staged patch identity differs from approved review")
    full_message = f"{message.strip()}\n\nWorker-Job: {review['worker_job_id']}\nReview-ID: {review['review_id']}"
    hooks_path = str(root / ".git" / "ci-hooks-disabled")
    commit = _run(root, ("git", "-c", f"core.hooksPath={hooks_path}", "-c", "commit.gpgSign=false", "commit", "--no-verify", "-m", full_message))
    if commit.returncode:
        _run(root, ("git", "reset", "--quiet", "HEAD", "--", *paths))
        raise ReviewError(f"commit failed: {_trim(commit.stderr).strip()}")
    commit_id = _git(root, "rev-parse", "HEAD").strip()
    artifact = {"schema_version": 1, "promotion_id": uuid.uuid4().hex, "outcome": "committed",
                "worker_job_id": review["worker_job_id"], "review_id": review["review_id"],
                "patch_sha256": patch_id, "parent_commit": parent, "commit_id": commit_id,
                "checks": checks, "started_at": _now(), "finished_at": _now()}
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(artifact, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    return artifact


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="CI-only local promotion commit for an approved worker submission.")
    parser.add_argument("--review-artifact", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--message", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        artifact = promote(args.review_artifact, args.workspace, args.message, args.output)
    except ReviewError as exc:
        print(f"promotion rejected: {exc}")
        raise SystemExit(2) from exc
    print(f"committed: {artifact['commit_id']} artifact: {args.output.resolve()}")


if __name__ == "__main__":
    main()
