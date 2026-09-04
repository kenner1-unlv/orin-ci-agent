# Feature Specification: Bounded Coding Job Editor

**Feature Branch**: `003-bounded-job-editor`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "bounded coding job-editor"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Complete a bounded edit (Priority: P1)

The control plane assigns a precise coding instruction to a named Git worktree. The worker inspects files, makes the smallest useful edit, runs approved checks, and returns a structured result with a diff.

**Why this priority**: This is the first useful autonomous worker capability and the basis for later CI orchestration.

**Independent Test**: Submit an edit against a disposable clean repository and verify the requested change, check results, and returned Git diff.

**Acceptance Scenarios**:

1. **Given** a clean registered worktree, **When** a valid edit job is submitted, **Then** only files inside that worktree may change and the response includes status, summary, checks, and diff.
2. **Given** the model finishes without changing a file, **When** the result is returned, **Then** the job is reported as completed with an empty diff rather than inventing evidence.

---

### User Story 2 - Reject unsafe scope (Priority: P2)

The operator receives a clear refusal when a request could escape the assigned repository or invoke an unapproved operation.

**Why this priority**: The model runs persistently near valuable robot software and must not gain ambient host authority.

**Independent Test**: Exercise traversal, absolute-path, symlink-escape, dirty-tree, unsupported-check, and shell-like inputs and verify that each is rejected without an out-of-scope change.

**Acceptance Scenarios**:

1. **Given** a workspace name or file path that escapes the configured root, **When** it is submitted or used, **Then** the worker rejects it.
2. **Given** a dirty repository, **When** a job is submitted, **Then** the worker refuses to edit it so existing work cannot be confused with agent output.

---

### User Story 3 - Audit a completed or failed job (Priority: P3)

The CI/PM agent can retrieve the durable result of a prior job by identifier after the request has ended.

**Why this priority**: Persistent evidence is required to review, diagnose, and later promote worker output.

**Independent Test**: Complete and fail separate jobs, restart the API, and retrieve both stored records by ID.

**Acceptance Scenarios**:

1. **Given** a known job ID, **When** its result is requested, **Then** the worker returns the persisted record.
2. **Given** an unknown job ID, **When** it is requested, **Then** the worker returns not found without leaking filesystem information.

### Edge Cases

- A job is rejected if its repository is not clean at admission.
- Files larger than the configured limit, binary files, and paths through escaping symlinks are not exposed to the model.
- Tool output and model iterations are capped; exceeding either cap fails the job with retained evidence.
- A failed check does not erase edits or evidence; it produces a failed job result for review.
- Only one edit job executes at a time in this first version.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The worker MUST accept an edit instruction only for a simple named workspace below a configured worktree root.
- **FR-002**: The worker MUST require the workspace to be a clean Git working tree before model execution.
- **FR-003**: The worker MUST constrain reads and writes to resolved, non-escaping paths within the assigned workspace.
- **FR-004**: The model MUST receive only bounded file listing, reading, literal search, exact replacement, file writing, approved check, and completion capabilities.
- **FR-005**: The worker MUST NOT expose a shell, caller-provided executable arguments, network tool, Git history mutation, commit, push, checkout, reset, or clean operation.
- **FR-006**: Approved checks MUST be selected by stable identifiers defined by the worker.
- **FR-007**: The worker MUST cap tool iterations, file size, tool output size, request size, and job duration.
- **FR-008**: Every accepted job MUST receive an unpredictable ID and a durable JSON record containing its state and evidence.
- **FR-009**: A completed job MUST return the resulting Git status and diff without committing or publishing changes.
- **FR-010**: Failed jobs MUST return a safe error category and retain available evidence without exposing secrets or arbitrary host paths.
- **FR-011**: The API MUST remain bound to localhost by default.
- **FR-012**: Job retrieval MUST support a known job ID and return not found for unknown IDs.

### Key Entities

- **Edit Job**: A job ID, workspace name, instruction, approved check IDs, timestamps, state, model summary, check evidence, Git status, diff, and safe error.
- **Workspace**: A clean Git worktree identified by a single path segment beneath the configured root.
- **Tool Invocation**: One bounded model action with validated arguments, capped output, and an ordinal in the job evidence.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A disposable-repository smoke job makes the requested edit and returns the exact uncommitted diff.
- **SC-002**: Automated tests reject 100% of representative absolute-path, traversal, symlink-escape, dirty-tree, and unsupported-check cases.
- **SC-003**: No available model tool can start an arbitrary executable or address a path outside the assigned worktree.
- **SC-004**: Every accepted job can be retrieved by ID after server restart with its terminal status and evidence intact.
- **SC-005**: The deployed service remains localhost-only and does not start or enable any ROS 2 service.

## Assumptions

- The CI/PM control plane reaches the API through SSH tunneling or another separately managed secure channel.
- A separate process prepares named clean Git worktrees beneath `/data/persistent-worker/worktrees`; repository acquisition is not part of this feature.
- Version one runs a single synchronous edit at a time and is intended for small, explicitly scoped changes.
- The local Ollama-compatible model endpoint is available on localhost and the configured coding model supports chat tool calls.
- Human or CI review is required before any commit, push, deployment, or merge.
