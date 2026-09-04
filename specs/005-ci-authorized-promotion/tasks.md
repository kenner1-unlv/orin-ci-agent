# Tasks: CI-Authorized Promotion

- [x] T001 [US1] Add promotion validation and fixed CI checks in reviewer/src/control_plane_reviewer/promote.py
- [x] T002 [US1] Add exact-path staging, staged fingerprint verification, hook-free local commit, and artifact output in reviewer/src/control_plane_reviewer/promote.py
- [x] T003 [US1] Expose promotion CLI in reviewer/src/control_plane_reviewer/promote.py and scripts/promote-worker-job.ps1
- [x] T004 [US1] Test successful exact promotion in reviewer/tests/test_promote.py
- [x] T005 [US2] Test stale, unapproved, extra-path, dirty-index, and failed-check rejection in reviewer/tests/test_promote.py
- [x] T006 [US2] Document CI-only authority and non-authorities in reviewer/README.md and docs/roles/CI_SPEC.md
- [x] T007 Run all reviewer tests and repository consistency checks
