#!/usr/bin/env python3
"""Benchmark an Ollama model using only the Python standard library."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import time
import urllib.request
from datetime import datetime, timezone


CODING_QUESTIONS = [
    ("In Python, what does list(range(2, 10, 3)) evaluate to?", "[2, 5, 8]"),
    ("What is the time complexity of binary search on a sorted array?", "O(log n)"),
    ("In Python, what does {'a': 1}.get('b', 7) return?", "7"),
    ("What single Python operator performs integer floor division?", "//"),
    ("A zero-based array has length 12. What is its final valid index?", "11"),
    ("What exception does Python raise for int('abc')?", "ValueError"),
]


def request(endpoint: str, payload: dict, timeout: int = 600) -> dict:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{endpoint.rstrip('/')}/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    with urllib.request.urlopen(req, timeout=timeout) as response:
        result = json.load(response)
    result["client_seconds"] = time.perf_counter() - started
    return result


def rate(count: int, duration_ns: int) -> float | None:
    return count / (duration_ns / 1e9) if count and duration_ns else None


def metrics(result: dict) -> dict:
    return {
        "client_seconds": round(result["client_seconds"], 3),
        "load_seconds": round(result.get("load_duration", 0) / 1e9, 3),
        "prompt_tokens": result.get("prompt_eval_count", 0),
        "prompt_tokens_per_second": round(
            rate(result.get("prompt_eval_count", 0), result.get("prompt_eval_duration", 0)) or 0, 2
        ),
        "generated_tokens": result.get("eval_count", 0),
        "generation_tokens_per_second": round(
            rate(result.get("eval_count", 0), result.get("eval_duration", 0)) or 0, 2
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--model", default="qwen3-coder:30b-a3b-q4_K_M")
    parser.add_argument("--context", type=int, default=32768)
    args = parser.parse_args()
    options = {"temperature": 0, "num_ctx": args.context}

    request(args.endpoint, {"model": args.model, "prompt": "Reply only: READY", "stream": False, "options": options})

    generation_runs = []
    for _ in range(3):
        result = request(args.endpoint, {
            "model": args.model,
            "prompt": "Write exactly 120 words explaining why unit tests help maintain software. Do not use a heading.",
            "stream": False,
            "options": {**options, "num_predict": 180},
        })
        generation_runs.append(metrics(result))

    long_prompt = ("alpha beta gamma delta epsilon zeta eta theta iota kappa\n" * 420)
    prompt_result = request(args.endpoint, {
        "model": args.model,
        "prompt": long_prompt + "Reply only with the number of distinct Greek names used above.",
        "stream": False,
        "options": {**options, "num_predict": 8},
    })

    coding_results = []
    for question, expected in CODING_QUESTIONS:
        result = request(args.endpoint, {
            "model": args.model,
            "prompt": f"Answer this programming question with only the answer, no explanation.\n{question}",
            "stream": False,
            "options": {**options, "num_predict": 32},
        })
        actual = result.get("response", "").strip()
        coding_results.append({
            "question": question,
            "expected": expected,
            "actual": actual,
            "passed": actual.casefold() == expected.casefold(),
            "metrics": metrics(result),
        })

    generation_rates = [run["generation_tokens_per_second"] for run in generation_runs]
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "host": platform.node(),
        "model": args.model,
        "context_tokens": args.context,
        "generation": {
            "runs": generation_runs,
            "median_tokens_per_second": round(statistics.median(generation_rates), 2),
        },
        "long_prompt": metrics(prompt_result),
        "micro_coding_eval": {
            "passed": sum(item["passed"] for item in coding_results),
            "total": len(coding_results),
            "results": coding_results,
        },
        "notes": [
            "Ollama durations exclude network overhead; client_seconds includes it.",
            "The micro coding evaluation is a regression smoke suite, not HumanEval or SWE-bench.",
        ],
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
