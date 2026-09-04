# Feature Specification: Control-Plane Code Review Gate

**Feature Branch**: `004-control-plane-code-review`

**Created**: 2026-09-03

**Status**: Draft

**Input**: User description: "Add the next-stage code review on the control-plane box after the bounded Orin worker produces a patch."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Gate a Worker Patch (Priority: P1)

An operator reviews a completed worker job before accepting its patch and receives an approve or request-changes verdict backed by independently collected evidence.

**Why this priority**: This is the safety boundary between autonomous editing and any later integration workflow.

**Independent Test**: Submit a valid worker job record and matching workspace, then verify that the review reports the exact patch, reruns trusted checks, and returns an approval without changing the workspace.

**Acceptance Scenarios**:

1. **Given** a completed worker job whose recorded patch matches the workspace and whose trusted checks pass, **When** the operator runs review, **Then** the system records an approval and supporting evidence.
2. **Given** a patch containing a blocking policy violation or a failed trusted check, **When** review runs, **Then** the system requests changes and identifies each blocking finding.

---

### User Story 2 - Detect Scope Drift and Tampering (Priority: P2)

An operator can tell when the workspace no longer represents the patch produced by the worker or when the patch touches files outside the authorized scope.

**Why this priority**: A review is not trustworthy if its evidence is for a different patch or includes unrelated changes.

**Independent Test**: Alter a reviewed workspace or add an out-of-scope file and verify that review blocks with a specific mismatch or scope finding.

**Acceptance Scenarios**:

1. **Given** a worker job record and a workspace with a different patch, **When** review runs, **Then** the system blocks approval and reports the mismatch.
2. **Given** a patch that changes an unauthorized path, **When** review runs, **Then** the system blocks approval and names that path.

---

### User Story 3 - Preserve an Auditable Review Artifact (Priority: P3)

An operator can inspect a durable, machine-readable report tied to the worker job, including findings, check results, and the exact reviewed patch identity.

**Why this priority**: Later promotion decisions need reproducible evidence rather than terminal output alone.

**Independent Test**: Complete a review and verify that its artifact can be read without the original process and contains the job identity, verdict, findings, check results, timestamps, and patch fingerprint.

**Acceptance Scenarios**:

1. **Given** any completed review, **When** its artifact is opened, **Then** all decision evidence and the worker job identity are present.
2. **Given** invalid input, **When** review cannot proceed, **Then** the system produces a clear error and does not claim approval.

### Edge Cases

- The worker job record is missing, malformed, incomplete, or not in a successful terminal state.
- The workspace is not a repository, has no patch, contains binary changes, or changes while review is running.
- A configured trusted check is unknown, unavailable, times out, or attempts to alter the workspace.
- The patch contains an untracked file, renamed file, deleted file, very large file, or a likely credential.
- The requested output path already exists or its parent cannot be written.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a worker job record, the corresponding workspace, an authorized path scope, and a selected set of trusted checks.
- **FR-002**: The system MUST reject records that are malformed, lack a stable worker job identifier, or do not represent a successfully completed editing job.
- **FR-003**: The system MUST independently derive the complete workspace patch, including tracked and untracked changes.
- **FR-004**: The system MUST compare the derived patch with the patch evidence recorded by the worker and block approval when they differ.
- **FR-005**: The system MUST block changes outside the authorized path scope and identify each offending path.
- **FR-006**: The system MUST run only checks selected from a locally controlled registry; job records and callers MUST NOT supply executable command text.
- **FR-007**: The system MUST record every check's identity, outcome, duration, and bounded diagnostic output.
- **FR-008**: The system MUST identify blocking security and review-policy violations detectable from the patch, including likely committed credentials and unsupported binary changes.
- **FR-009**: The system MUST distinguish blocking findings from non-blocking suggestions and derive the final verdict from blocking findings.
- **FR-010**: The system MUST verify that review itself did not alter repository state and MUST block if state changed during review.
- **FR-011**: The system MUST write a durable machine-readable artifact containing the review identity, worker job identity, patch fingerprint, verdict, findings, checks, and timestamps.
- **FR-012**: The system MUST provide concise operator output and distinct outcomes for approval, requested changes, and invalid execution.
- **FR-013**: The review process MUST NOT edit source files, stage changes, create commits, push changes, merge changes, or deploy software.
- **FR-014**: The first release MUST operate locally on the control-plane machine and MUST NOT require the Orin worker to remain online after its job record and workspace are available.

### Key Entities

- **Review Request**: The worker record, workspace, authorized path patterns, and trusted check identifiers selected by the operator.
- **Patch Evidence**: The normalized complete diff and a stable fingerprint that identify exactly what was reviewed.
- **Finding**: A coded observation with severity, message, and optional path and line location.
- **Check Result**: The outcome, timing, and bounded diagnostics from one locally controlled verification.
- **Review Artifact**: The durable record joining the worker job to its patch evidence, findings, checks, and verdict.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In acceptance fixtures, 100% of matching clean patches with passing checks are approved and 100% of patch mismatches, out-of-scope changes, credential findings, and failed checks are blocked.
- **SC-002**: Every completed review produces one parseable artifact containing all required audit fields and a stable fingerprint for the reviewed patch.
- **SC-003**: Review leaves repository state byte-for-byte equivalent to its starting state in 100% of acceptance runs.
- **SC-004**: An operator can review a normal worker patch and understand the verdict and any blocking reason in under two minutes, excluding the runtime of project checks.
- **SC-005**: No acceptance path permits caller-controlled or worker-controlled command text to execute.

## Assumptions

- The operator has already transferred or otherwise made the worker job record and corresponding repository workspace available on the control-plane machine.
- The worker's durable record includes its job identifier, terminal state, and patch evidence; compatible field aliases may be normalized at the review boundary.
- Trusted checks are project-owned and identified by stable names. Adding arbitrary per-request shell commands is out of scope.
- The initial gate provides deterministic policy and test evidence. Human or model-authored semantic commentary may be layered on later but cannot override a blocking deterministic finding.
- Patch application, commits, pushes, pull requests, merges, and deployment remain separate, explicitly authorized future stages.
