# Jetson Worker Implementation Brief

## Mission

The worker is a persistent, supervised execution service on the Jetson. It accepts only supported, versioned job contracts; executes them within declared boundaries; and produces observable status and durable artifacts.

This repository is the editable source of truth. The copy on the Jetson is an immutable deployed release, not a development workspace.

## Existing Baseline

- Target alias: `sauce-bot`
- Target user: `sauce`
- Service: `persistent-worker.service`
- Health and readiness are local to the target.
- Releases live under `~/.local/share/persistent-worker/releases`.
- Durable data lives under `/data/persistent-worker`.
- The service runs without unrestricted administrative access.
- ROS 2 Humble is installed but must remain inactive unless a job contract requires it.
- Docker is installed; container control is optional and treated as root-equivalent capability.

## Must Preserve

- Health, readiness, graceful shutdown, restart-on-failure, and boot persistence.
- Versioned release deployment and rollback.
- Separation of release files from state, models, cache, and artifacts.
- Local-only control exposure until authentication and network policy are specified.
- No implicit package installation or executable downloads during a job.
- No secrets in repository files, logs, artifacts, or job status.

## Required Job Lifecycle

An enabled job moves through explicit states such as accepted, preparing, running, succeeded, failed, cancelling, and cancelled. Every terminal job records a reason, timestamps, its contract version, release identity, and declared artifacts.

The first implementation must not create a generic shell-execution endpoint. Each job type receives a bounded schema and an allowlisted executor.

## Failure Rules

- Reject unsupported or malformed work before side effects begin.
- Do not run when `/data` or a declared capability is unavailable.
- Bound execution time, concurrency, CPU, memory, storage, and output volume per contract.
- Preserve useful diagnostics and partial artifacts according to the contract.
- Make retry behavior explicit and avoid duplicate side effects.
- Honor graceful cancellation before forced termination.

## Coding-Agent Handoff

Before changing this worker, the coding agent must receive:

- One approved work package.
- The exact job contract or infrastructure outcome.
- Required and prohibited capabilities.
- Acceptance commands and expected observable evidence.
- Deployment and rollback scope.

The coding agent should implement the smallest independently testable slice, update tests and operator documentation, run repository checks, deploy only when authorized, and return evidence rather than a narrative claim.

## Still Needed Before Useful Agentic Work

1. Select the first representative job and its success artifact.
2. Choose the model/provider and decide whether inference is local, remote, or hybrid.
3. Define the operator-to-worker transport and authentication boundary.
4. Define job persistence, concurrency, retry, timeout, and retention policies.
5. Define allowed tools, filesystem roots, network destinations, and escalation rules.
6. Define observability and notification requirements.
7. Define model and artifact preparation, checksums, quotas, and cleanup.
8. Add threat-model and failure-injection checks before granting broader autonomy.
