# Implementation Plan: Bounded Coding Job Editor

**Branch**: `003-bounded-job-editor` | **Date**: 2026-09-03 | **Spec**: [spec.md](spec.md)

## Summary

Deliver and validate a localhost-only coding editor that modifies one clean named
Git worktree through a fixed tool set, runs only approved checks, and persists
evidence without exposing a generic shell. Promotion is gated by a project-owned
golden-worktree evaluation of the deployed model and worker.

## Technical Context

**Language/Version**: Python 3.10+; Bash for deployment and validation

**Primary Dependencies**: Python standard library, Git, Ollama 0.32.15, systemd user services

**Storage**: Durable JSON records and patches under `/data/persistent-worker`; disposable Git worktrees

**Testing**: `unittest`, API smoke tests, hidden-oracle golden-worktree evaluation

**Target Platform**: Jetson Orin 64 GB, ARM64 Linux/JetPack 6

**Project Type**: Local HTTP worker service and control-plane scripts

**Performance Goals**: One job at a time; repository-evaluation p95 no more than 300 seconds

**Constraints**: Loopback-only APIs; no generic shell/network/model-selected executable; 20 model rounds; writes confined to one clean worktree

**Scale/Scope**: Small edits; initial 12-case golden suite followed by 36 repeatability attempts

## Constitution Check

The constitution is an unratified placeholder and defines no enforceable gates.
The feature specification supplies the controlling gates: no out-of-worktree
writes, no arbitrary execution or network tool, localhost-only binding, clean-
worktree admission, durable evidence, and no implicit ROS activation. The design
passes these gates. Missing constitutional governance is recorded as debt, not
treated as permission to weaken the specification.

Post-design review reaches the same conclusion: external hidden-oracle scoring
does not broaden worker authority. No violation needs a complexity exception.

## Project Structure

```text
worker/
├── src/orin_worker/
│   ├── app.py
│   └── editor.py
├── tests/test_app.py
├── deploy/
└── config/
scripts/
├── deploy.sh
├── smoke-editor.sh
└── repo-eval/                 # planned harness, manifests, fixture builder
benchmarks/                    # immutable generated reports and raw records
specs/003-bounded-job-editor/  # specification and design artifacts
```

**Structure Decision**: Retain the single Python worker package and put control-
plane-only evaluation tooling under `scripts/repo-eval`. Hidden oracles do not
ship in the worker service or enter model-visible worktrees. Generated results
remain under `benchmarks`.

## Implementation Sequence

1. Close unit-test gaps for paths, limits, failure evidence, concurrency, empty
   diffs, malformed model calls, and persisted retrieval after restart.
2. Build and calibrate the 12 golden fixtures and hidden evaluators.
3. Run one deployed first-attempt pilot and stop for any safety violation.
4. If at least 9/12 resolve with complete evidence, run two further attempts per
   case and require at least 80% resolution across 36 attempts.
5. If gates pass, freeze a held-out 20–30-case corpus and prepare the isolated
   10-instance SWE-bench Verified pilot described in `research.md`.
