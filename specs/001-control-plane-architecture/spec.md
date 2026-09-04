# Feature Specification: Persistent Worker Control Plane

**Feature Branch**: `[001-control-plane-architecture]`

**Created**: 2026-09-02

**Status**: Draft

**Input**: User description: "Define the CI, PM/spec-agent, and Jetson worker responsibilities so another coding agent can implement the worker from explicit instructions while this repository remains the source of truth."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Specify Work Before Execution (Priority: P1)

As the operator, I can describe a desired outcome and receive a bounded, reviewable specification with acceptance criteria before the Jetson worker is changed.

**Why this priority**: The worker will run persistently on physical hardware. Clear intent and boundaries are the primary defense against unsafe or wasted work.

**Independent Test**: Give the PM/spec agent an example outcome and verify that it produces a complete work package containing scope, constraints, risks, acceptance checks, and rollback expectations without deploying anything.

**Acceptance Scenarios**:

1. **Given** an informal operator request, **When** the PM/spec agent prepares it for implementation, **Then** the resulting work package states the outcome, exclusions, assumptions, dependencies, acceptance evidence, and unresolved decisions.
2. **Given** a request with a safety-critical or materially ambiguous choice, **When** the work package is prepared, **Then** implementation remains blocked until that choice is resolved.

---

### User Story 2 - Validate and Deploy a Reviewable Release (Priority: P2)

As the operator, I can validate a worker change locally where possible, deploy a versioned release to the Jetson, confirm its health, and roll back without making the Jetson the only source of code.

**Why this priority**: Repeatable deployment and recovery are required before the worker performs useful jobs.

**Independent Test**: Starting from this repository, deploy a release, verify its version and readiness on the target, and return to the preceding release using documented commands.

**Acceptance Scenarios**:

1. **Given** a candidate release whose checks pass, **When** CI deploys it, **Then** the Jetson runs an identifiable immutable release and retains durable state separately.
2. **Given** a failed health or readiness check, **When** deployment validation completes, **Then** the release is reported unsuccessful and an operator can restore the preceding known release.
3. **Given** unavailable target hardware, **When** ordinary CI runs, **Then** checks that do not require the Jetson still complete without target credentials.

---

### User Story 3 - Execute a Bounded Worker Job (Priority: P3)

As the operator, I can submit a job that conforms to an approved versioned contract and observe its acceptance, progress, completion, failure, cancellation, and artifacts.

**Why this priority**: Useful autonomous execution depends on a stable control and evidence boundary, but its first concrete job must be selected before implementation.

**Independent Test**: Submit a representative approved job and verify its full lifecycle, resource bounds, final status, and output artifact without direct intervention on the Jetson.

**Acceptance Scenarios**:

1. **Given** a valid job matching a supported contract, **When** it is submitted, **Then** the worker assigns an identity and exposes an observable lifecycle.
2. **Given** an invalid or unsupported job, **When** it is submitted, **Then** the worker rejects it without executing partial work.
3. **Given** a running job receives a stop request, **When** its grace period expires, **Then** it has either stopped cleanly or failed with an explicit termination reason.

### Edge Cases

- The Jetson is offline, changes IP address, or loses network access during deployment.
- `/data` is absent, read-only, full, or replaced by a directory on the root filesystem.
- A release starts but its readiness check fails.
- A deployment is interrupted after upload but before activation.
- The worker restarts while a job is running or while an artifact is being written.
- A requested dependency conflicts with the installed JetPack, CUDA, Python, or ROS versions.
- An instruction requests undeclared privilege, network access, package installation, or ROS activation.
- CI logs or generated artifacts accidentally contain credentials or private machine data.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The repository MUST remain the authoritative location for specifications, worker source, tests, deployment definitions, and operating documentation.
- **FR-002**: The PM/spec function MUST translate operator intent into a versioned work package before implementation begins.
- **FR-003**: Every work package MUST define scope, exclusions, assumptions, dependencies, risks, acceptance evidence, and recovery expectations.
- **FR-004**: CI MUST provide checks that run without the physical Jetson and MAY provide separately invoked target smoke tests.
- **FR-005**: CI MUST prevent secrets and private keys from entering tracked files or routine logs.
- **FR-006**: Deployment MUST create identifiable immutable releases and preserve durable state independently of release files.
- **FR-007**: Deployment MUST verify service health and readiness before reporting success.
- **FR-008**: The operator MUST be able to restore a preceding release without reconstructing it on the Jetson.
- **FR-009**: The worker MUST restart after process failure and device reboot while providing a graceful shutdown path.
- **FR-010**: The worker MUST refuse useful job execution until a versioned job contract has been approved.
- **FR-011**: Each enabled job contract MUST define inputs, outputs, lifecycle states, time and resource limits, permissions, dependencies, artifact handling, and cancellation behavior.
- **FR-012**: The worker MUST report health, readiness, job state, completion, and failure in a form that automated checks can verify.
- **FR-013**: The worker MUST use dedicated durable storage and MUST NOT silently fall back to the smaller system filesystem when that storage is unavailable.
- **FR-014**: Runtime jobs MUST NOT silently install packages or download executable code.
- **FR-015**: Dependencies and model artifacts MUST be declared, versioned, prepared before execution, and validated before accepting a dependent job.
- **FR-016**: Elevated access MUST be limited to the capability required by an approved job; unrestricted passwordless administrative access is prohibited.
- **FR-017**: ROS 2 MUST remain inactive unless an approved job contract explicitly requires and controls it.
- **FR-018**: The control plane MUST retain a decision history linking requested outcomes, specifications, releases, checks, and observed results.

### Key Entities

- **Work Package**: A reviewable statement of an outcome, scope, constraints, risks, dependencies, acceptance evidence, and recovery requirements.
- **Job Contract**: A versioned agreement defining permissible worker inputs, outputs, states, resources, privileges, and side effects.
- **Release**: An immutable deployable snapshot with a unique identity and associated verification results.
- **Job**: One execution instance of a supported job contract, including identity, lifecycle, timestamps, status, and failure reason.
- **Artifact**: A declared job output with identity, location, type, size, integrity information, and retention state.
- **Capability**: A detected or provisioned target facility such as storage, accelerator support, ROS, container execution, or a model.
- **Decision Record**: A dated choice with its rationale, consequences, and relationship to affected specifications.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A new operator request can be converted into a reviewable work package in under 15 minutes without changing the Jetson.
- **SC-002**: Every deployed release can be traced to repository content and verification evidence using one release identifier.
- **SC-003**: A healthy release is deployed and verified through a single documented operator workflow in under 10 minutes on the local network.
- **SC-004**: A failed candidate can be returned to the preceding release in under 5 minutes without loss of durable state.
- **SC-005**: All routine control-plane checks complete without requiring Jetson connectivity or target secrets.
- **SC-006**: One hundred percent of accepted jobs use an approved contract and expose a terminal success, failure, or cancellation state.
- **SC-007**: Reboot and expected process-failure tests restore worker readiness without manual login or intervention.
- **SC-008**: When required storage or dependencies are unavailable, no affected job begins and the operator receives an actionable reason.

## Assumptions

- One trusted operator initially owns approvals and access to the local-network Jetson.
- This repository is the only editable source of worker application code; target releases are deployment outputs.
- The current target is a Jetson Orin 64GB reachable through the `sauce-bot` SSH alias.
- Durable models, state, caches, and artifacts use the dedicated `/data` filesystem.
- ROS 2 and Docker are optional capabilities rather than baseline requirements for every job.
- The first concrete job and model/provider choice will be specified as a separate bounded feature.
- Remote multi-user access, public internet exposure, and a graphical administration interface are outside the first milestone.
