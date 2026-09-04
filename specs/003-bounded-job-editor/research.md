# Research: Bounded Coding Job Editor

## Evaluation strategy

**Decision**: Use a project-owned, hermetic golden-worktree suite against the
deployed `/v1/jobs` API before adopting a public repository benchmark.

**Rationale**: HumanEval pass@1 of 148/164 (90.24%) establishes strong isolated
Python synthesis, but not repository inspection, tool use, editing, checks,
evidence, or persistence. Twelve deterministic fixtures measure the product
contract without giving the model hidden tests or new host authority.

**Alternatives considered**: Full SWE-bench Verified is deferred because its
500-task container harness, historical dependencies, disk requirements, and x86-
oriented images are a poor fit for the ARM64 worker and fixed check IDs. HumanEval+
remains function-level. Valuable live repositories are excluded until gates pass.

## Scoring and corpus

**Decision**: Resolution means external hidden tests pass without regression or
path-scope violation. Worker `status=completed` never implies benchmark resolution.
Use 12 fixtures: three localized fixes, three diagnosis/search fixes, two multi-
file changes, two test additions or repairs, one new-file task, and one no-op.
After a sound pilot, run three total attempts per case.

**Rationale**: The matrix exercises the seven-tool surface within 20 rounds and a
300-second budget. External scoring detects misleading summaries and incomplete
evidence; repetition exposes tool-call instability.

**Alternatives considered**: Model self-report and public checks are insufficient
oracles. Exact expected patches reject valid alternative solutions. One smoke task
has inadequate coverage.

## Promotion gates

**Decision**: Require 12/12 fixture calibration, 100% safety/refusal and changed-
path compliance, at least 9/12 first-attempt resolutions, 12/12 retrievable terminal
records, and at least 80% exact resolution across 36 attempts. Each basic P1 case
must resolve at least twice; p95 must not exceed 300 seconds. Any escape or
undeclared host mutation is an immediate no-go.

**Rationale**: Safety is non-negotiable. The functional threshold demonstrates
usefulness without conflating repository work with the 90.24% HumanEval score.

## Isolation and evidence

**Decision**: Build each attempt from a pinned clean commit, keep hidden tests
outside the worktree, and retain manifest, runtime identity, prompt, job record,
tool calls, patch, oracle output, and timing. Evaluator commands remain outside the
worker contract.

**Rationale**: Fresh fixtures prevent contamination and immutable evidence permits
failure replay. Adding caller-supplied commands would violate the bounded contract.

## Step after the golden suite

If gates pass, freeze a 20–30-case held-out regression corpus and schedule
comparative runs. Then run a 10-instance SWE-bench Verified pilot: patch generation
on the Orin, official evaluation on a disposable x86 Docker host. Require gold-
patch calibration of 10/10, no isolation incident, and at most 10% infrastructure
failures before expanding to 50 instances.

