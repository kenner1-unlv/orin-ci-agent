# Tasks: Control-Plane Code Review Gate

## Phase 1: Setup

- [x] T001 Create the dependency-free reviewer package and CLI entry point in reviewer/pyproject.toml and reviewer/src/control_plane_reviewer/__main__.py
- [x] T002 [P] Add the Windows control-plane launcher in scripts/review-worker-job.ps1

## Phase 2: Foundational

- [x] T003 Define validated requests, findings, check results, and artifacts in reviewer/src/control_plane_reviewer/review.py
- [x] T004 Implement shell-free Git execution, canonical patch capture, changed-path parsing, and state fingerprinting in reviewer/src/control_plane_reviewer/review.py

## Phase 3: User Story 1 - Gate a Worker Patch (P1)

**Independent Test**: A matching safe job is approved; a failing trusted check requests changes; neither run changes the repository.

- [x] T005 [US1] Add approval and failed-check tests in reviewer/tests/test_review.py
- [x] T006 [US1] Implement job validation, immutable trusted-check dispatch, findings, and verdict derivation in reviewer/src/control_plane_reviewer/review.py
- [x] T007 [US1] Implement CLI parsing and exit-code behavior in reviewer/src/control_plane_reviewer/__main__.py

## Phase 4: User Story 2 - Detect Scope Drift and Tampering (P2)

**Independent Test**: Mismatched evidence, unauthorized paths, credentials, binary changes, and check mutations each create a blocking finding.

- [x] T008 [US2] Add patch mismatch, scope, credential, binary, and mutation tests in reviewer/tests/test_review.py
- [x] T009 [US2] Implement exact evidence comparison, glob scope enforcement, patch policy scans, and pre/post mutation blocking in reviewer/src/control_plane_reviewer/review.py

## Phase 5: User Story 3 - Preserve an Auditable Artifact (P3)

**Independent Test**: Every valid review exclusively creates one parseable artifact outside the workspace with identity, evidence, findings, checks, and timestamps.

- [x] T010 [US3] Add artifact schema, exclusive-create, and invalid-input tests in reviewer/tests/test_review.py
- [x] T011 [US3] Implement bounded artifact serialization and exclusive output creation in reviewer/src/control_plane_reviewer/review.py

## Phase 6: Polish

- [x] T012 [P] Document operator use, trust boundaries, and trusted check IDs in reviewer/README.md and README.md
- [x] T013 Run the automated suite and the clean/bad-patch quickstart scenarios from specs/004-control-plane-code-review/quickstart.md

## Dependencies & Execution Order

T001-T002 establish entry points. T003-T004 provide the shared foundation. US1 is the MVP; US2 and US3 build on its orchestration while remaining independently testable through their scenarios. Documentation and full validation finish the feature.

## Parallel Opportunities

T002 can proceed alongside T001. Documentation can begin once the CLI contract stabilizes. Tests for a story can be drafted before its corresponding implementation task.

## Implementation Strategy

Deliver US1 first as a useful deterministic gate, add tamper/scope protections in US2, then make its evidence durable in US3. No task adds mutation, commit, publication, merge, or deployment authority.
