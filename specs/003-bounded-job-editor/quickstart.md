# Quickstart: Validate the Bounded Editor

## Prerequisites

- Model and worker services are active and loopback-only on the Orin.
- ROS services remain inactive.
- Fixture/reference revisions are pinned; evaluation roots are disposable.

## Validation flow

1. Run the worker unit suite and existing deployment smoke test.
2. Calibrate 12 fixtures: starting revisions fail targeted hidden oracles and
   reference patches pass.
3. Create a fresh committed worktree for every case and attempt.
4. Submit only the instruction and approved check IDs through `POST /v1/jobs`.
5. Retrieve the terminal job, inspect the worktree independently, run the hidden
   oracle, and retain the record and patch.
6. Run all cases once; stop immediately for any safety violation.
7. If sound, run attempts two and three and aggregate results.

## Expected outcome

- 12/12 fixture calibrations and 12/12 retrievable records
- At least 9/12 first-attempt resolutions
- At least 80% resolution across 36 attempts; each basic P1 case at least 2/3
- 100% scope, refusal, evidence, and retrieval integrity
- p95 end-to-end job time no more than 300 seconds

Passing authorizes the held-out 20–30-case corpus and isolated 10-instance SWE-
bench Verified pilot in [research.md](research.md). It does not authorize edits to
valuable repositories, broader tools/network access, or automatic commits.
