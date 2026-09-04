# Orin CI Agent

A local-first coding-agent pipeline built around a Jetson Orin 64 GB running a bounded 30B coding model, with an independent Windows control plane responsible for review, CI, and promotion.

Generated code is treated as an untrusted submission. The Orin worker can inspect and edit an assigned repository, but cannot run arbitrary shell commands, commit, push, merge, or deploy. Completed jobs are reconstructed in a disposable local IDE sandbox, checked independently, and may only become a local Git commit through the CI-controlled promotion gate.

> This is an experimental engineering project, not a production security boundary. Review the current controls before using it on sensitive repositories.

## Workflow

<!-- Replace this block with docs/images/workflow-overview.png when available. -->

```text
Task + accepted specification
          |
          v
Jetson Orin bounded worker
  Qwen3-Coder 30B via Ollama
          |
          | completed job record + base Git bundle + patch
          v
Disposable local IDE sandbox
          |
          v
Independent review gate
  patch identity | path scope | secrets | trusted checks
          |
          v
CI-only promotion gate
  rerun fixed checks | stage reviewed paths | verify staged hash
          |
          v
One local commit

Push, merge, tag, and deployment remain separately authorized actions.
```

Planned diagrams belong in [`docs/images/`](docs/images/README.md). Suggested assets are `workflow-overview.png`, `trust-boundaries.png`, and `job-lifecycle.png`.

## Current results

The deployed model is `qwen3-coder:30b-a3b-q4_K_M`, served locally on the Orin with deterministic sampling.

| Evaluation | Result |
|---|---:|
| Generation throughput | 28.03 tokens/s median |
| HumanEval | 148/164, 90.24% pass@1 |
| Improved repository evaluation | 34/36, 94.4% |
| Final repository acceptance | 10/12, all promotion gates passed |
| Worker regression suite | 25/25 passing |
| Local intake/review/promotion suite | 18/18 passing |

See [the complete benchmark report](docs/MODEL_BENCHMARKS.md) for methodology, limitations, raw artifacts, and earlier baselines.

## Safety model

- The worker receives one named Git worktree and begins from a clean state.
- Its tools are limited to listing, reading, literal search, bounded text edits, approved checks, and finish.
- It has no general shell, network, credential, Git mutation, or deployment tool.
- Every job has a durable JSON record and binary-capable patch artifact.
- CI imports base history and the recorded patch rather than trusting a copied live worktree.
- Review blocks evidence mismatches, scope drift, likely credentials, binaries, failed checks, and review-time mutations.
- Only CI promotion may stage reviewed paths and create one local commit.
- Promotion cannot push, merge, tag, deploy, select weaker checks, or execute repository hooks.

Detailed policy lives in the [operating contract](docs/OPERATING_CONTRACT.md), [CI role brief](docs/roles/CI_SPEC.md), and [worker brief](docs/roles/WORKER_BRIEF.md).

## Repository map

| Path | Purpose |
|---|---|
| `worker/` | Bounded Orin worker service, editor tools, tests, and service units |
| `reviewer/` | Local intake, deterministic review, and CI-only promotion gates |
| `scripts/` | Deployment, diagnostics, benchmarks, intake, review, and promotion commands |
| `scripts/repo-eval/` | Golden-worktree evaluation harness and cases |
| `specs/` | Feature specifications, plans, contracts, and completed task lists |
| `benchmarks/` | Reproducible raw evaluation artifacts |
| `docs/` | Architecture, operating policy, runtime, and benchmark documentation |

## Key commands

Run the local gate tests:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.tools/uv-cache')
$env:UV_PYTHON_INSTALL_DIR = (Join-Path (Resolve-Path '.tools') 'python')
uv run --project reviewer --python 3.12 python -m unittest discover -s reviewer/tests -v
```

Import a completed Orin job into an ignored IDE sandbox and run CI review:

```powershell
./scripts/import-worker-submission.ps1 `
  -JobId '<32-character-job-id>' `
  -Target sauce-bot `
  -AllowPath 'src/**','tests/**'
```

After inspecting an approved artifact, the CI agent can create a local commit:

```powershell
./scripts/promote-worker-job.ps1 `
  -ReviewArtifact '.ci-sandboxes/<job-id>/review.json' `
  -Workspace '.ci-sandboxes/<job-id>/worktree' `
  -Message 'Implement the accepted change' `
  -Output '.ci-artifacts/<job-id>-promotion.json'
```

Promotion is intentionally local. Publication and deployment are separate decisions.

## Project status

The bounded worker, model runtime, repository evaluation harness, local sandbox intake, independent review gate, and CI-only local promotion are implemented and tested. The next validation is a real medium-sized coding task in a clean external repository, followed by human review of its CI-approved patch.

## Documentation

- [Project specification](docs/PROJECT_SPEC.md)
- [Model runtime](docs/MODEL_RUNTIME.md)
- [Model benchmarks](docs/MODEL_BENCHMARKS.md)
- [Dependency policy](docs/DEPENDENCY_POLICY.md)
- [Operating contract](docs/OPERATING_CONTRACT.md)
- [Golden repository evaluation](scripts/repo-eval/README.md)

## License

No license has been selected yet. Until one is added, the repository is publicly viewable but standard copyright restrictions apply.
