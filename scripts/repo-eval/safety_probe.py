#!/usr/bin/env python3
"""Exercise deployed API admission rejections without invoking the model."""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def post(url: str, payload: dict) -> tuple[int, dict]:
    request = Request(url, data=json.dumps(payload).encode(), method="POST",
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker-url", default="http://127.0.0.1:8765")
    parser.add_argument("--worktree-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    name = f"eval-rejection-dirty-{int(time.time())}"
    repo = args.worktree_root / name
    repo.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "probe@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Safety Probe"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("clean\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "fixture"], cwd=repo, check=True)
    (repo / "tracked.txt").write_text("dirty\n", encoding="utf-8")

    base = {"kind": "edit", "workspace": name, "instruction": "No operation."}
    probes = {
        "workspace_traversal": {**base, "workspace": "../escape"},
        "absolute_workspace": {**base, "workspace": "/tmp"},
        "missing_workspace": {**base, "workspace": "does-not-exist"},
        "dirty_workspace": base,
        "unsupported_check": {**base, "checks": ["shell"]},
        "unknown_field": {**base, "command": "sh"},
        "wrong_kind": {**base, "kind": "shell"},
        "oversize_instruction": {**base, "instruction": "x" * 8001},
    }
    results = []
    for probe_id, payload in probes.items():
        status, body = post(args.worker_url.rstrip("/") + "/v1/jobs", payload)
        results.append({"id": probe_id, "status": status, "body": body,
                        "passed": status == 400 and body.get("error") == "job_rejected"})
    report = {"passed": sum(item["passed"] for item in results),
              "total": len(results), "workspace": name, "results": results}
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "total": report["total"]}, indent=2))
    return 0 if report["passed"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
