# Orin Model Benchmarks

## Final hardware decision

These results establish that the Orin 64 GB can host useful local coding models:
the Qwen baseline reached 90.24% HumanEval pass@1, 94.4% across the improved
three-run repository evaluation, and passed the final bounded-worker acceptance
gate. They also show why it should not remain the primary machine for this
repository-coding workflow. Generation speed, end-to-end tool-loop latency, and
semantic variability still impose too much waiting and supervision for regular
engineering work.

Continue this workload on a substantially more powerful workstation or
server-class accelerator. Retain the Orin for robotics, sensor processing, and
bounded edge inference, where its compact form factor and low power draw are
valuable. The benchmark artifacts below remain the evidence for that decision;
they should not be interpreted as a general rejection of the device.

## 2026-09-03 baseline

Target configuration:

- Jetson Orin 64 GB
- `qwen3-coder:30b-a3b-q4_K_M`
- Ollama `0.32.15`
- 32,768-token configured context
- Temperature 0, one request at a time, warm model

Results:

| Measurement | Result |
|---|---:|
| Median generation throughput (3 runs) | 28.03 tokens/s |
| Individual generation runs | 28.12, 28.03, 27.99 tokens/s |
| Long-prompt ingestion | 737.42 tokens/s |
| Long-prompt size | 5,060 tokens |
| Long-prompt end-to-end latency | 7.116 s |
| Micro coding questions | 6/6 passed |
| Available memory before | 38.54 GiB |
| Available memory after | 38.24 GiB |
| CPU temperature before/after | 47.0 / 49.6 C |
| GPU temperature before/after | 44.8 / 45.9 C |

The three generation requests produced 159-162 tokens in 5.73-6.00 seconds of
client-observed wall time. The long-prompt test generated only three tokens after
ingesting 5,060 tokens, so its result primarily measures prompt processing.

The six-question coding check covers deterministic Python and algorithms basics.
It is useful as a deployment regression test, but it is not evidence of repository-
level coding ability and must not be compared with HumanEval or SWE-bench scores.

Thermal readings were sampled immediately before and after the suite rather than
continuously, so they do not establish peak temperature or sustained-load behavior.

## Reproduction

Run the standard-library-only benchmark on the model host:

```bash
python3 scripts/benchmark-model.py
```

The script prints machine-readable JSON containing per-run Ollama token counts,
durations, answers, and pass/fail results. Ollama's token rates exclude HTTP
overhead; `client_seconds` includes it.

## 2026-09-03 HumanEval baseline

The model completed OpenAI's canonical 164-problem HumanEval set with one
deterministic sample per problem:

| Measurement | Result |
|---|---:|
| Passed | 148/164 |
| pass@1 | 90.24% |
| Failed assertions | 15 |
| Syntax failures | 1 |
| Timeouts | 0 |
| Total generation wall time | 506.078 s |
| Mean generation wall time | 3.086 s/problem |
| Prompt tokens | 29,229 |
| Generated tokens | 11,487 |

Generation used temperature 0, an 8,192-token context, and a 512-token output
cap. Tests ran in a `python:3.11-slim` container with no network, a read-only
root filesystem, all Linux capabilities dropped, no-new-privileges, a 512 MiB
memory limit, a 64-process limit, and a five-second per-problem timeout. The
official HumanEval dataset was pinned at commit
`6d43fb980f9fee3c892a914eda09951f772ad10d`.

Raw outputs are in
[`benchmarks/humaneval-samples-20260903.jsonl`](../benchmarks/humaneval-samples-20260903.jsonl)
and
[`benchmarks/humaneval-results-20260903.json`](../benchmarks/humaneval-results-20260903.json).
The generator and isolated evaluator are
[`scripts/generate-humaneval.py`](../scripts/generate-humaneval.py) and
[`scripts/evaluate-humaneval.py`](../scripts/evaluate-humaneval.py).

HumanEval measures self-contained Python function synthesis. It does not measure
repository navigation, tool selection, patch hygiene, or autonomous debugging;
the golden-worktree evaluation in the feature plan covers that next layer.

## 2026-09-03 golden-worktree baseline

The deployed bounded editor was evaluated through its real `/v1/jobs` API using
12 calibrated disposable repositories, hidden external oracles, and isolated
test execution. An initial calibration run exposed that the approved Python
checks wrote `__pycache__` files into worktrees. The worker checks were corrected
to suppress bytecode artifacts, covered by a regression test, and redeployed
before the scored runs below.

| Measurement | Result |
|---|---:|
| Valid first-attempt resolutions | 9/12 (75.0%) |
| Three-run resolutions | 30/36 (83.3%) |
| Scope violations | 0/36 |
| Retrieval failures | 0/36 |
| Evidence mismatches | 0/36 |
| Combined p95 job latency | 58.15 s |
| Combined mean job latency | 32.81 s |
| Live API admission rejections | 8/8 |
| Worker tests after correction | 23/23 |
| Harness tests | 7/7 |

Ten cases met the per-case stability requirement. `config_alias` resolved once
in three attempts, and `add_regression_test` resolved zero times. The aggregate
rate exceeds the 80% target, but the planned requirement that every basic case
resolve at least twice was not met. The repeatability promotion gate is therefore
**failed**, and expansion to held-out repositories or SWE-bench is paused.

The next iteration should focus on inspection and test-placement behavior in the
tool scaffold, rerun only the frozen failing cases as diagnostics, and then rerun
the full 36-attempt suite without changing its scoring policy. Raw reports are in
`benchmarks/repo-eval-*.json`; the combined record is
[`benchmarks/repo-eval-repeatability-36-20260903.json`](../benchmarks/repo-eval-repeatability-36-20260903.json).

## 2026-09-03 behavior improvement

Failure traces drove four general scaffold corrections without exposing hidden
answers to the model:

- Python checks no longer leave bytecode artifacts in worktrees.
- `unittest` discovery finding zero tests now returns a failed check.
- The editor is instructed to follow existing test layout, preserve precedence
  when adding aliases, and avoid scratch verification files.
- Ollama agent calls now use temperature 0 and seed 0.

The original test-addition oracle was also corrected: it had required the
irrelevant literal `Ada`. It now semantically requires an unchanged production
file, a discovered passing test, and a test input containing surrounding
whitespace.

| Stage | Result |
|---|---:|
| Original repeatability baseline | 30/36 (83.3%) |
| Weak-case diagnostic after scaffold changes | 5/6 (83.3%) |
| First improved full run | 12/12 (100%) |
| Three improved deterministic runs | 34/36 (94.4%) |
| Cache patch-hygiene diagnostic after final prompt refinement | 3/3 (100%) |
| Final full-suite acceptance | 10/12 (83.3%) |

The three-run improvement is **+4 resolved tasks** and **+11.1 percentage
points** over the original 36-attempt baseline. All 36 improved hidden oracles
passed; two attempts were rejected only for unnecessary verification files. The
final prompt refinement eliminated that repeated pattern in 3/3 targeted runs.

The final acceptance passed all promotion gates: 10/12 resolutions, 100% safety,
scope, retrieval, and evidence consistency, 48.19-second p95, and 31.00-second
mean latency. Its misses were semantic failures on `slug_whitespace` and
`config_alias`, showing that temperature/seed reduce but do not eliminate runtime
variation in the complete tool loop.

The final report is
[`benchmarks/repo-eval-final-acceptance-20260903.json`](../benchmarks/repo-eval-final-acceptance-20260903.json).
