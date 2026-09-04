#!/usr/bin/env python3
"""Evaluate HumanEval samples; intended to run inside a locked-down container."""

from __future__ import annotations

import argparse
import gzip
import json
import subprocess
import sys


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problems", required=True)
    parser.add_argument("--samples", required=True)
    parser.add_argument("--timeout", type=float, default=5)
    parser.add_argument("--output")
    args = parser.parse_args()

    with gzip.open(args.problems, "rt", encoding="utf-8") as source:
        problems = {item["task_id"]: item for item in map(json.loads, source)}
    with open(args.samples, encoding="utf-8") as source:
        samples = list(map(json.loads, source))

    results = []
    for sample in samples:
        problem = problems[sample["task_id"]]
        program = (
            problem["prompt"] + sample["completion"] + "\n" +
            problem["test"] + "\n" + f"check({problem['entry_point']})\n"
        )
        try:
            run = subprocess.run(
                [sys.executable, "-I", "-c", program],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                timeout=args.timeout,
            )
            passed = run.returncode == 0
            detail = "passed" if passed else run.stderr.strip().splitlines()[-1][-300:]
        except subprocess.TimeoutExpired:
            passed, detail = False, "timed out"
        results.append({"task_id": sample["task_id"], "passed": passed, "result": detail})

    passed = sum(item["passed"] for item in results)
    report = {
        "passed": passed,
        "total": len(results),
        "pass_at_1": passed / len(results) if results else 0,
        "results": results,
    }
    if args.output:
        with open(args.output, "w", encoding="utf-8") as output:
            json.dump(report, output, indent=2)
            output.write("\n")
    print(json.dumps({key: report[key] for key in ("passed", "total", "pass_at_1")}, indent=2))


if __name__ == "__main__":
    main()
