# Control-plane reviewer

This is the read-only gate between an Orin editing job and any later integration action. It validates a completed worker record against a local Git worktree, enforces authorized paths and patch policy, reruns trusted checks, and creates a JSON verdict artifact outside the worktree.

Run it on Windows with `scripts/review-worker-job.ps1`; see `specs/004-control-plane-code-review/quickstart.md`.

Trusted checks are fixed in reviewer source: `git_diff_check`, `python_unittest`, and `python_compileall`. Inputs select IDs but cannot provide commands, arguments, environment changes, or repository-defined scripts.

Approval means the recorded and local patches match, all selected checks passed, no deterministic blocker was found, and the final repository fingerprint equals the initial fingerprint. It is not a commit, merge, push, deployment, or substitute for human product judgment.

Only the CI promotion entry point, `scripts/promote-worker-job.ps1`, may turn an approved patch into a local commit. It reruns all mandatory CI checks, rejects stale evidence or a dirty index, stages only reviewed paths, verifies the staged patch fingerprint, and disables repository hooks. It has no push, merge, tag, deploy, network, or check-bypass option.

`scripts/import-worker-submission.ps1` is the intake boundary. Orin exports only its completed job record, base Git bundle, and recorded patch. CI reconstructs these under ignored `.ci-sandboxes/<job-id>/worktree`, then runs all fixed review checks locally. Intake never commits; “completed on Orin” means submitted for CI, not promoted.

`scripts/handoff-promoted-worker-base.ps1` is the chaining boundary. It accepts only a
clean workspace whose `HEAD` equals the commit in a successful promotion artifact,
creates and hashes an exact Git bundle, and transfers it into a new Orin workspace.
The remote side verifies the hash and commit, removes the bundle remote, refuses to
overwrite an existing workspace, and writes a durable handoff marker for auditing.
