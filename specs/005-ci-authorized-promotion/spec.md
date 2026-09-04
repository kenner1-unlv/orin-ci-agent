# Feature Specification: CI-Authorized Promotion

**Feature Branch**: `005-ci-authorized-promotion`
**Created**: 2026-09-03
**Status**: Draft
**Input**: User description: "Only the CI agent may promote or commit submitted worker code, after running extra checks."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Promote an Approved Submission (Priority: P1)

The CI agent takes an approved review artifact, independently reruns mandatory CI checks against the unchanged submitted patch, and creates a local commit only if every gate passes.

**Why this priority**: It makes CI—not the worker—the sole authority that turns an uncommitted patch into repository history.

**Independent Test**: Promote an approved fixture and verify one commit is created containing exactly the reviewed paths.

**Acceptance Scenarios**:

1. **Given** an approved artifact and unchanged patch, **When** all mandatory CI checks pass, **Then** exactly one local commit is created and a promotion artifact records its identity.
2. **Given** a failed check, stale review, changed patch, or unapproved review, **When** promotion is attempted, **Then** no commit is created.

### User Story 2 - Preserve Authority Boundaries (Priority: P2)

The worker and ordinary callers cannot supply commands, bypass checks, include unreviewed paths, or cause push, merge, or deployment.

**Why this priority**: Promotion is a narrow authority grant, not general repository or release control.

**Independent Test**: Attempt bypass inputs and verify rejection with unchanged HEAD and index.

**Acceptance Scenarios**:

1. **Given** any caller-controlled command or missing mandatory check, **When** promotion is attempted, **Then** it is rejected.
2. **Given** a successful commit, **When** promotion completes, **Then** no remote, merge, or deployment state changed.

### Edge Cases

- Dirty index, empty patch, deleted or renamed files, changed HEAD, existing output, check mutation, or commit hook behavior.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Only the explicit CI promotion command MUST create a promotion commit.
- **FR-002**: Promotion MUST require an approved review artifact tied to the worker job and current patch fingerprint.
- **FR-003**: Promotion MUST independently rerun a locally controlled mandatory CI check set and MUST NOT accept executable command text.
- **FR-004**: Promotion MUST refuse a dirty index, changed review evidence, missing reviewed paths, extra paths, failed checks, or a check that changes repository state.
- **FR-005**: Promotion MUST stage only the paths named by the approved review and verify the staged patch identity before committing.
- **FR-006**: Promotion MUST disable repository hooks and MUST create at most one local commit with worker and review identities in its message.
- **FR-007**: Promotion MUST NOT push, merge, tag, deploy, or access the network.
- **FR-008**: Promotion MUST exclusively create a machine-readable artifact containing checks, source identities, commit identity, and outcome.

### Key Entities

- **Promotion Request**: Approved review artifact, workspace, commit message, mandatory checks, and output path.
- **Promotion Artifact**: Worker, review, patch, checks, and resulting commit identities.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of accepted fixtures create exactly one commit containing exactly the reviewed patch.
- **SC-002**: 100% of stale, failed, mutated, or bypass fixtures create no commit.
- **SC-003**: No promotion test performs push, merge, tag, deployment, or network access.

## Assumptions

- Invocation of the promotion command is reserved to the CI agent by the surrounding control plane.
- V1 creates a local commit only; later publication requires a separate authorization.
