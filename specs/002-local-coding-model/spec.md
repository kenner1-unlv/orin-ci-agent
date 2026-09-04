# Feature Specification: Local Coding Model

**Feature Branch**: `[002-local-coding-model]`

**Created**: 2026-09-02

**Status**: Approved for implementation

**Input**: User description: "Install the selected coding model and supporting runtime on the Jetson under `/data`, start it automatically, verify its commands, and give the worker basic coding access without unrestricted passwordless sudo."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persistent Local Inference (Priority: P1)

As the operator, I can request coding assistance from a local model on the Jetson after reboot without manually starting or re-downloading it.

**Why this priority**: Persistent, locally available inference is the foundation for all later coding jobs.

**Independent Test**: Reboot or restart the service, submit a small coding prompt, and receive a valid response while confirming the model and cache remain on `/data`.

**Acceptance Scenarios**:

1. **Given** the Jetson has completed boot and `/data` is mounted, **When** service readiness is checked, **Then** the local model endpoint becomes ready without an interactive login.
2. **Given** a valid coding prompt, **When** it is submitted locally, **Then** the service returns a model response and identifies the configured model.

---

### User Story 2 - Safe Coding Workspace (Priority: P2)

As the operator, I can assign a repository worktree to the worker and allow ordinary inspection, editing, patching, building, and testing without granting unrestricted system administration.

**Why this priority**: Useful coding requires tools, but broad host access would make mistakes unnecessarily dangerous.

**Independent Test**: Assign a disposable fixture repository, ask for a bounded change, and verify that the worker produces a diff and test evidence only within that workspace.

**Acceptance Scenarios**:

1. **Given** an assigned writable worktree, **When** a coding job runs, **Then** it can inspect files, modify files, run allowlisted development commands, and return a diff and test output.
2. **Given** a requested write outside the assigned worktree or worker data roots, **When** the worker evaluates it, **Then** the request is rejected or escalated rather than executed.

---

### User Story 3 - Observable and Recoverable Operation (Priority: P3)

As the operator, I can distinguish downloading, loading, ready, busy, failed, and stopped states and recover from failures without losing model artifacts.

**Why this priority**: Large local models have long preparation and load times; invisible failure would make operation unreliable.

**Independent Test**: Stop, start, and fail the model service while observing state, logs, readiness, and retained model files.

**Acceptance Scenarios**:

1. **Given** a runtime failure, **When** supervision responds, **Then** the service restarts and retains downloaded model data.
2. **Given** unavailable durable storage, **When** startup is attempted, **Then** the service fails clearly without downloading onto the system filesystem.

### Edge Cases

- `/data` is missing, read-only, full, or nearly full.
- Model download is interrupted or has an integrity mismatch.
- Runtime image and JetPack/CUDA versions are incompatible.
- Model loading exhausts memory or thermal/power limits are reached.
- The endpoint is accidentally configured beyond localhost.
- A coding prompt attempts instruction injection, secret discovery, privilege escalation, or writes outside its worktree.
- ROS or unrelated robot services are unintentionally started.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Model weights, caches, and generated coding artifacts MUST use dedicated paths under `/data`.
- **FR-002**: The selected model, quantization, source revision, size, and integrity digest MUST be recorded.
- **FR-003**: The model service MUST start after durable storage and its runtime prerequisites are available.
- **FR-004**: The model endpoint MUST listen only on the Jetson loopback interface until a separate authenticated transport is approved.
- **FR-005**: The service MUST expose observable health and readiness and restart after expected process failure.
- **FR-006**: A verified request MUST return the configured model identity and generated output.
- **FR-007**: Initial operation MUST limit concurrency and context to protect interactive system stability.
- **FR-008**: The coding worker MUST be restricted to explicitly assigned worktrees and worker-owned data directories for writes.
- **FR-009**: Basic tools MUST cover repository inspection, text search, patching, version-control diff/status, building, and tests.
- **FR-010**: Arbitrary administrative commands and unrestricted passwordless sudo MUST NOT be granted.
- **FR-011**: Container control MAY be granted when required and MUST be documented as root-equivalent capability.
- **FR-012**: ROS 2 and the existing robot stack MUST remain inactive throughout installation and verification.
- **FR-013**: Installation MUST be reproducible from versioned control-plane files and MUST include removal/recovery instructions.
- **FR-014**: Interrupted or invalid model downloads MUST NOT be treated as ready artifacts.
- **FR-015**: Logs and responses MUST NOT intentionally expose credentials or private key material.

### Key Entities

- **Model Artifact**: The pinned quantized weights, source revision, size, digest, and local path.
- **Inference Service**: The supervised local endpoint that loads the model and reports health/readiness.
- **Coding Workspace**: A disposable, explicitly assigned repository worktree with bounded write access.
- **Tool Policy**: The allowlist, roots, limits, and escalation rules controlling coding operations.
- **Inference Result**: Model output plus model identity, timing, token counts, and completion status.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After restart, the model becomes ready without operator login or intervention.
- **SC-002**: One hundred percent of model and cache bytes created by this feature reside under `/data`.
- **SC-003**: A standard coding prompt returns a non-empty response and model identity within five minutes after readiness.
- **SC-004**: The service remains responsive with at least 8 GiB of memory available to the rest of the system during the initial benchmark.
- **SC-005**: All attempted writes in the workspace-boundary test remain within approved roots.
- **SC-006**: ROS-related services and processes remain inactive before and after installation.
- **SC-007**: A stopped or failed model service can be restored without downloading the model again.

## Assumptions

- Qwen3-Coder-30B-A3B-Instruct Q4_K_M is the initial candidate and may be replaced if measured behavior fails the success criteria.
- Initial inference uses one request at a time and no more than 32K tokens of context.
- The operator has approved Docker-group membership if the selected Jetson runtime requires container access.
- Internet access is available during explicit model preparation, not required for normal inference.
- The initial coding tool layer will be built after the inference server itself passes health and benchmark checks.
