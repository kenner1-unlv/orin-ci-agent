#!/usr/bin/env python3
"""Generate deterministic HumanEval completions through an Ollama endpoint."""

from __future__ import annotations

import argparse
import gzip
import json
import re
import time
import urllib.request


def clean_completion(text: str) -> str:
    text = text.strip("\r\n")
    fence = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        text = fence.group(1).strip("\r\n")
    if text and not text[0].isspace():
        text = "    " + text
    # A continuation is required because the canonical prompt already contains
    # the function signature and docstring.
    return "\n" + text.rstrip() + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--problems", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--model", default="qwen3-coder:30b-a3b-q4_K_M")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()

    with gzip.open(args.problems, "rt", encoding="utf-8") as source:
        problems = [json.loads(line) for line in source]
    if args.limit:
        problems = problems[: args.limit]

    with open(args.output, "w", encoding="utf-8") as output:
        for index, problem in enumerate(problems, 1):
            instruction = (
                "Complete the Python function below. Return only the indented function "
                "body that follows the existing docstring. Do not repeat the signature, "
                "do not use Markdown fences, and do not explain.\n\n" + problem["prompt"]
            )
            payload = json.dumps({
                "model": args.model,
                "prompt": instruction,
                "stream": False,
                "options": {"temperature": 0, "num_ctx": 8192, "num_predict": 512},
            }).encode()
            request = urllib.request.Request(
                args.endpoint.rstrip("/") + "/api/generate",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            started = time.perf_counter()
            with urllib.request.urlopen(request, timeout=600) as response:
                result = json.load(response)
            record = {
                "task_id": problem["task_id"],
                "completion": clean_completion(result.get("response", "")),
                "elapsed_seconds": round(time.perf_counter() - started, 3),
                "prompt_tokens": result.get("prompt_eval_count"),
                "generated_tokens": result.get("eval_count"),
            }
            output.write(json.dumps(record) + "\n")
            output.flush()
            print(f"[{index}/{len(problems)}] {problem['task_id']} {record['elapsed_seconds']}s", flush=True)


if __name__ == "__main__":
    main()
