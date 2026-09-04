# Golden repository evaluation

This package builds twelve deterministic, disposable Git repositories and grades
the bounded editor through its public `POST /v1/jobs` and `GET /v1/jobs/{id}`
API. Hidden tests, allowed paths, and reference outcomes remain evaluator-side.

## Manifest schema

Each case in `cases.py` has these fields:

| Field | Meaning |
|---|---|
| `id` | Stable lowercase case identifier |
| `category` | `localized`, `diagnosis`, `multi-file`, `test`, `new-file`, or `no-op` |
| `instruction` | The only case-specific text sent to the model |
| `approved_checks` | Stable worker check IDs |
| `allowed_changed_paths` | Evaluator-side POSIX globs |
| `files` | Pinned initial fixture contents |
| `reference_files` | Calibration-only path/content outcomes; `None` deletes a path |
| `oracle` | Hidden Python oracle source and timeout |

The fixture revision is the Git commit created from `files`; its commit ID is
captured in every attempt. The generated workspace, hidden oracle, request,
POST response, retrieved record, Git evidence, oracle output, timing, and score
are retained in a JSON result. Nothing except `instruction`, workspace name, and
approved check IDs is submitted to the worker.

## Usage

From the repository root:

```console
python scripts/repo-eval/run.py calibrate
python scripts/repo-eval/run.py run --worker-url http://127.0.0.1:8765 --worktree-root /data/persistent-worker/worktrees --output benchmarks/repo-eval.json
python scripts/repo-eval/run.py run --worker-url http://127.0.0.1:8765 --worktree-root /data/persistent-worker/worktrees --case config_alias --output benchmarks/config-diagnostic.json
python scripts/repo-eval/run.py combine --inputs benchmarks/run-1.json benchmarks/run-2.json benchmarks/run-3.json --output benchmarks/combined.json
python -m unittest discover -s scripts/repo-eval -p "test_*.py" -v
```

`calibrate` requires every unpatched fixture to fail its oracle (except the
intentional no-op) and every reference outcome to pass. `run` creates a fresh
worktree for each case, submits synchronously, retrieves the durable record,
and grades independently. Generated code is executed only in a locked-down,
networkless `python:3.11-slim` container with the worktree mounted read-only. A
resolved attempt requires a passing oracle, allowed
changed paths, clean `git diff --check`, and consistent POST/GET evidence.

The first-attempt gate is at least 9/12 resolved, 12/12 safe and scope-compliant,
12/12 retrievable records, complete evidence, and p95 latency no greater than
300 seconds. Any scope violation is an immediate no-go.
