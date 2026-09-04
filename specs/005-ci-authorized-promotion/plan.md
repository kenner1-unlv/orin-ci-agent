# Implementation Plan: CI-Authorized Promotion

Use the existing standard-library reviewer package. Add a separate promotion command that validates an approved artifact, reruns the fixed CI suite, proves checks did not mutate state, stages only reviewed paths, verifies the staged patch SHA-256, commits with hooks disabled, and writes an exclusive promotion artifact. Tests use temporary Git repositories and local identity configuration. No remote operations exist in the implementation.

**Technical context**: Python 3.10+, Git CLI, unittest, Windows control plane. The unratified constitution adds no gates; the CI brief requires independent checks, immutable identity, evidence, and explicit deployment separation, all satisfied by this design.

**Structure**: `reviewer/src/control_plane_reviewer/promote.py`, CLI dispatch in `__main__.py`, `scripts/promote-worker-job.ps1`, and promotion tests in `reviewer/tests/test_promote.py`.
