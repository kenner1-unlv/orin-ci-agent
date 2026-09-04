# Tasks: Bounded Coding Job Editor

## Phase 1: Setup

- [X] T001 Create the repository-evaluation package structure and manifest schema in scripts/repo-eval/README.md
- [X] T002 [P] Add generated repository-evaluation artifacts and temporary fixture paths to .gitignore

## Phase 2: Foundational

- [X] T003 Define 12 deterministic fixture cases, hidden oracles, reference outcomes, categories, and allowed paths in scripts/repo-eval/cases.py
- [X] T004 Implement fresh-worktree preparation, Git evidence capture, worker API submission, durable retrieval, and isolated oracle execution in scripts/repo-eval/run.py
- [X] T005 Add harness calibration and aggregate gate scoring for safety, resolution, evidence, retrieval, and latency in scripts/repo-eval/run.py

## Phase 3: User Story 1 - Complete a bounded edit (P1)

- [X] T006 [US1] Add harness unit tests for fixture calibration, result scoring, no-op handling, and changed-path enforcement in scripts/repo-eval/test_repo_eval.py
- [X] T007 [US1] Run all 12 golden cases once against the deployed Orin worker and retain raw results in benchmarks/

## Phase 4: User Story 2 - Reject unsafe scope (P2)

- [X] T008 [US2] Expand worker safety tests for symlink escape, binary/oversize files, dirty trees, unsupported checks, request limits, concurrency, and unknown tools in worker/tests/test_app.py
- [X] T009 [US2] Run the representative rejection suite against disposable Orin worktrees and retain the report in benchmarks/

## Phase 5: User Story 3 - Audit completed or failed jobs (P3)

- [X] T010 [US3] Add tests for empty diffs, failed-check evidence, unknown IDs, malformed model responses, and durable retrieval after server restart in worker/tests/test_app.py
- [X] T011 [US3] Verify every golden-suite terminal record by GET and compare persisted status/diff to the scored worktree in scripts/repo-eval/run.py

## Phase 6: Polish and Decision

- [X] T012 Document first-attempt results, failures, gate decision, and whether to start the 36-attempt repeatability run in docs/MODEL_BENCHMARKS.md

## Dependencies

- T001 and T002 can run in parallel.
- T003 depends on T001; T004 depends on T003; T005 depends on T004.
- T006 depends on T003-T005; T007 depends on T006.
- T008 and T010 may run in parallel after T001.
- T009 depends on T008; T011 depends on T004 and completes with T007.
- T012 depends on T007, T009, and T011.

## Independent validation

- **US1**: At least 9/12 fresh golden worktrees pass hidden tests with allowed diffs.
- **US2**: Every representative unsafe request is rejected without an out-of-scope write.
- **US3**: Every accepted job has retrievable terminal evidence matching its worktree.

## MVP

T001-T007 provide the first useful repository-level model score. T008-T012 add the
non-negotiable safety and evidence gates required for promotion.
