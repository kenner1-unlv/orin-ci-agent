# Feature Specification: Sandboxed CI Intake

**Created**: 2026-09-03
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Import and Test a Worker Submission (Priority: P1)

After Orin completes a worker job, the CI agent imports immutable base history, the worker record, and its patch into a new disposable workspace visible in the local IDE, then runs review and CI checks there.

**Independent Test**: Import a fixture bundle and patch and verify the reconstructed patch exactly matches the record and produces a review artifact.

**Acceptance Scenarios**:

1. **Given** a completed job, **When** CI intake runs, **Then** a new isolated worktree and review artifact are created locally.
2. **Given** tampered, stale, duplicate, or malformed input, **When** intake runs, **Then** it fails closed without promotion.

### User Story 2 - Preserve Promotion Boundary (Priority: P2)

Orin may submit completed evidence but cannot commit or promote it; only the CI promotion command can commit after local review and extra checks.

**Independent Test**: Verify intake creates no commit and a rejected review cannot be promoted.

### Edge Cases

- Existing sandbox, unsafe identifier, invalid bundle, patch apply failure, mismatched job evidence, network interruption, or failed CI check.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Intake MUST accept only a completed 32-character worker job identifier.
- **FR-002**: Remote export MUST contain only the job record, base Git bundle, and recorded patch.
- **FR-003**: Local intake MUST create a new job-specific directory under the configured IDE sandbox root and refuse overwrite.
- **FR-004**: Intake MUST reconstruct from the base bundle and patch rather than trust a copied working directory.
- **FR-005**: Intake MUST run the existing review gate with fixed CI checks and store its artifact beside the sandbox.
- **FR-006**: Intake MUST NOT commit, push, merge, tag, or deploy.
- **FR-007**: A failed or mismatched review MUST remain inspectable but ineligible for promotion.

## Success Criteria *(mandatory)*

- **SC-001**: All valid fixtures reconstruct identical patch evidence.
- **SC-002**: All tampered fixtures fail or receive request-changes.
- **SC-003**: Intake creates zero commits and remote operations.

## Assumptions

- SSH alias `sauce-bot` reaches Orin and standard worker paths are configured.
- “Orin promotion” means submission/completion; CI retains actual promotion authority.
