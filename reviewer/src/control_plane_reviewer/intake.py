from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Sequence

from control_plane_reviewer.review import ReviewError, _now, canonical_patch, load_job, review


INTAKE_CHECKS = ("git_diff_check", "python_unittest", "python_compileall")


def _command(argv: Sequence[str], cwd: Path) -> str:
    try:
        result = subprocess.run(list(argv), cwd=cwd, text=True, capture_output=True,
                                stdin=subprocess.DEVNULL, check=False, shell=False, timeout=300)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ReviewError(f"intake command failed: {type(exc).__name__}") from exc
    if result.returncode:
        raise ReviewError(f"intake command failed: {result.stderr.strip()}")
    return result.stdout


def intake(job_path: Path, bundle_path: Path, patch_path: Path, sandbox_root: Path,
           allow_paths: Sequence[str]) -> dict[str, Any]:
    job = load_job(job_path)
    try:
        supplied_patch = patch_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ReviewError(f"invalid patch input: {type(exc).__name__}") from exc
    if supplied_patch != job["diff"]:
        raise ReviewError("exported patch differs from worker job evidence")
    destination = sandbox_root.resolve() / job["id"]
    if destination.exists():
        raise ReviewError("job sandbox already exists")
    worktree = destination / "worktree"
    destination.mkdir(parents=True)
    try:
        _command(("git", "clone", "--quiet", str(bundle_path.resolve()), str(worktree)), destination)
        patch_copy = destination / "submission.patch"
        patch_copy.write_text(supplied_patch, encoding="utf-8", newline="")
        job_copy = destination / "job.json"
        shutil.copyfile(job_path, job_copy)
        _command(("git", "apply", "--binary", "--whitespace=nowarn", str(patch_copy)), worktree)
        if canonical_patch(worktree) != job["diff"]:
            raise ReviewError("reconstructed sandbox differs from worker evidence")
        review_path = destination / "review.json"
        result = review(job_copy, worktree, allow_paths, INTAKE_CHECKS, review_path)
        artifact = {"schema_version": 1, "intake_id": uuid.uuid4().hex, "worker_job_id": job["id"],
                    "created_at": _now(), "base_revision": _command(("git", "rev-parse", "HEAD"), worktree).strip(),
                    "workspace": str(worktree), "review_artifact": str(review_path), "verdict": result["verdict"]}
        with (destination / "intake.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(artifact, stream, indent=2)
            stream.write("\n")
        return artifact
    except Exception:
        # Keep a reconstructed/rejected sandbox for CI diagnosis; it is ignored and never promoted implicitly.
        raise


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="Reconstruct and review an Orin worker submission locally.")
    parser.add_argument("--job-record", required=True, type=Path)
    parser.add_argument("--bundle", required=True, type=Path)
    parser.add_argument("--patch", required=True, type=Path)
    parser.add_argument("--sandbox-root", required=True, type=Path)
    parser.add_argument("--allow-path", required=True, action="append")
    args = parser.parse_args()
    try:
        artifact = intake(args.job_record, args.bundle, args.patch, args.sandbox_root, args.allow_path)
    except ReviewError as exc:
        print(f"intake rejected: {exc}")
        raise SystemExit(2) from exc
    print(json.dumps(artifact, indent=2))
    raise SystemExit(0 if artifact["verdict"] == "approve" else 1)


if __name__ == "__main__":
    main()
