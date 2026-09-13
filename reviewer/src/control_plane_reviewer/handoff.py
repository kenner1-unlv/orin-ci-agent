from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

from control_plane_reviewer.review import ReviewError, _now, validate_workspace


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ("git", *args), cwd=root, text=True, encoding="utf-8", errors="surrogateescape", capture_output=True,
            stdin=subprocess.DEVNULL, check=False, shell=False, timeout=300,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewError(f"handoff Git operation failed: {type(exc).__name__}") from exc
    if result.returncode:
        raise ReviewError(f"handoff Git operation failed: {result.stderr.strip()}")
    return result.stdout


def _load_promotion(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReviewError(f"invalid promotion artifact: {type(exc).__name__}") from exc
    required = {
        "schema_version", "promotion_id", "outcome", "worker_job_id",
        "review_id", "parent_commit", "commit_id", "checks",
    }
    if not isinstance(value, dict) or required - value.keys() or value.get("schema_version") != 1:
        raise ReviewError("promotion artifact has an unsupported schema")
    if value.get("outcome") != "committed":
        raise ReviewError("promotion artifact does not authorize a chained handoff")
    for key in ("promotion_id", "worker_job_id", "review_id"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{32}", value[key]):
            raise ReviewError(f"promotion artifact has an invalid {key}")
    for key in ("parent_commit", "commit_id"):
        if not isinstance(value.get(key), str) or not re.fullmatch(r"[0-9a-f]{40,64}", value[key]):
            raise ReviewError(f"promotion artifact has an invalid {key}")
    if not isinstance(value["checks"], list) or not value["checks"]:
        raise ReviewError("promotion artifact has no CI check evidence")
    if any(check.get("status") != "passed" for check in value["checks"] if isinstance(check, dict)):
        raise ReviewError("promotion artifact contains a failed CI check")
    return value


def prepare_handoff(promotion_path: Path, workspace: Path, bundle_path: Path) -> dict[str, Any]:
    root = validate_workspace(workspace)
    promotion = _load_promotion(promotion_path)
    bundle = bundle_path.resolve()
    if bundle == root or root in bundle.parents or bundle.exists():
        raise ReviewError("handoff bundle must be new and outside the workspace")
    head = _git(root, "rev-parse", "HEAD").strip()
    if head != promotion["commit_id"]:
        raise ReviewError("workspace HEAD does not match the promoted commit")
    if _git(root, "status", "--porcelain=v1", "--untracked-files=all"):
        raise ReviewError("promoted workspace must be clean before handoff")
    bundle.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "bundle", "create", str(bundle), "HEAD")
    verify = _git(root, "bundle", "verify", str(bundle))
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    return {
        "schema_version": 1,
        "handoff_id": hashlib.sha256(
            f"{promotion['promotion_id']}:{head}:{digest}".encode("ascii")
        ).hexdigest()[:32],
        "outcome": "prepared",
        "created_at": _now(),
        "promotion_id": promotion["promotion_id"],
        "worker_job_id": promotion["worker_job_id"],
        "review_id": promotion["review_id"],
        "parent_commit": promotion["parent_commit"],
        "commit_id": head,
        "bundle_sha256": digest,
        "bundle_bytes": bundle.stat().st_size,
        "bundle_verify": verify.strip(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare an exact CI-promoted commit for a chained Orin worker job."
    )
    parser.add_argument("--promotion-artifact", required=True, type=Path)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    args = parser.parse_args()
    try:
        artifact = prepare_handoff(args.promotion_artifact, args.workspace, args.bundle)
    except ReviewError as exc:
        print(f"handoff rejected: {exc}")
        raise SystemExit(2) from exc
    print(json.dumps(artifact, separators=(",", ":")))


if __name__ == "__main__":
    main()
