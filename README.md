# Orin CI Agent

A local-first coding-agent pipeline built around a Jetson Orin 64 GB running a bounded coding model, with an independent Windows control plane responsible for review, CI, and promotion.

Generated code is treated as an untrusted submission. The Orin worker can inspect and edit an assigned repository, but cannot run arbitrary shell commands, commit, push, merge, or deploy. Completed jobs are reconstructed in a disposable local IDE sandbox, checked independently, and may only become a local Git commit through the CI-controlled promotion gate.

> This is an experimental engineering project, not a production security boundary. Review the current controls before using it on sensitive repositories.

## Workflow

<!-- Replace this block with docs/images/workflow-overview.png when available. -->

```text
Task + accepted specification
          |
          v
Jetson Orin bounded worker
  Configured local model via Ollama
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

The September 12, 2026 live audit found `devstral-small-2:24b-instruct-2512-q4_K_M` configured and loaded on Orin. All four deployed worker source files matched this checkout. The results below are the earlier **Qwen3-Coder 30B baseline**, not Devstral benchmark results.

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

Chain an approved promotion into a new clean Orin workspace for the next bounded job:

```powershell
./scripts/handoff-promoted-worker-base.ps1 `
  -PromotionArtifact '.ci-artifacts/<job-id>-promotion.json' `
  -Workspace '.ci-sandboxes/<job-id>/worktree' `
  -RemoteWorkspace '<new-clean-workspace-name>' `
  -Target sauce-bot `
  -Output '.ci-artifacts/<job-id>-handoff.json'
```

The handoff accepts only the exact clean commit named by a successful CI promotion
artifact. Orin verifies the bundle digest and commit, creates a new detached worktree
without a Git remote, and records a durable handoff marker. Existing remote workspaces
are never overwritten.

## Project status

The bounded worker, model runtime, repository evaluation harness, local sandbox intake, independent review gate, and CI-only local promotion are implemented. The Windows gate suite passed 26 tests on September 12, 2026, including UTF-8 and binary-output regression coverage.

The pipeline has delivered bounded Beverage Ops Control Tower changes. Direct case costs and performance instrumentation are merged in that repository. Rejected-import deletion (issue #51, PR #52) still needs its evidence-recovery review finding resolved and browser approval. Loader consolidation (#43) is a separate Windows-authored local candidate, not an Orin delivery. Further progressive-rendering work follows those checkpoints. See [the current runtime audit](docs/MODEL_RUNTIME.md) for the distinction between deployed configuration and historical benchmark results.

## Documentation

- [Project specification](docs/PROJECT_SPEC.md)
- [Model runtime](docs/MODEL_RUNTIME.md)
- [Model benchmarks](docs/MODEL_BENCHMARKS.md)
- [Dependency policy](docs/DEPENDENCY_POLICY.md)
- [Operating contract](docs/OPERATING_CONTRACT.md)
- [Golden repository evaluation](scripts/repo-eval/README.md)

## License

No license has been selected yet. Until one is added, the repository is publicly viewable but standard copyright restrictions apply.
