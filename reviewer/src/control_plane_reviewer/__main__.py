from __future__ import annotations

import argparse
from pathlib import Path

from control_plane_reviewer.review import CHECKS, ReviewError, review


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(description="Review a bounded worker job without modifying its workspace.")
    value.add_argument("--job-record", required=True, type=Path)
    value.add_argument("--workspace", required=True, type=Path)
    value.add_argument("--allow-path", required=True, action="append")
    value.add_argument("--check", action="append", default=[])
    value.add_argument("--output", required=True, type=Path)
    return value


def main() -> None:
    args = parser().parse_args()
    try:
        artifact = review(args.job_record, args.workspace, args.allow_path, args.check, args.output)
    except ReviewError as exc:
        print(f"review error: {exc}")
        raise SystemExit(2) from exc
    print(f"verdict: {artifact['verdict']} artifact: {args.output.resolve()}")
    raise SystemExit(0 if artifact["verdict"] == "approve" else 1)


if __name__ == "__main__":
    main()
