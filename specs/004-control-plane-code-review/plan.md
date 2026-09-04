# Implementation Plan: Control-Plane Code Review Gate

**Branch**: `004-control-plane-code-review` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Add a local, read-only CLI that validates a completed Orin worker record against its Git worktree, enforces path and patch policies, reruns only source-owned trusted checks, proves the worktree is unchanged, and exclusively creates a structured review artifact outside the reviewed workspace.

## Technical Context

**Language/Version**: Python 3.10+ with a PowerShell launcher for the Windows control plane

**Primary Dependencies**: Python standard library and Git CLI only

**Storage**: Exclusive-create JSON review artifacts on the local filesystem

**Testing**: `unittest` with temporary Git repositories; PowerShell smoke invocation

**Target Platform**: Windows control-plane host; core CLI remains cross-platform

**Project Type**: Local CLI/library

**Performance Goals**: Policy analysis completes in under two minutes excluding trusted check runtime

**Constraints**: Read-only workspace; no shell evaluation or network; bounded output; output outside workspace

**Scale/Scope**: One completed worker job and one Git worktree per invocation; patches up to the worker evidence limit

## Constitution Check

The constitution is an unratified template and defines no enforceable gates. The design follows the repository's established library/CLI, structured-output, dependency-minimal, and integration-test patterns. Post-design check: pass.

## Project Structure

### Documentation (this feature)

```text
specs/004-control-plane-code-review/
|-- plan.md
|-- research.md
|-- data-model.md
|-- quickstart.md
|-- contracts/review-cli.md
`-- tasks.md
```

### Source Code (repository root)

```text
reviewer/
|-- pyproject.toml
|-- README.md
|-- src/control_plane_reviewer/
|   |-- __init__.py
|   |-- __main__.py
|   `-- review.py
`-- tests/test_review.py

scripts/review-worker-job.ps1
```

**Structure Decision**: Keep the control-plane reviewer separate from the deployed `worker/` package so the trust boundary is visible and worker deployment cannot silently replace review policy.

## Complexity Tracking

No constitution violations require justification.
