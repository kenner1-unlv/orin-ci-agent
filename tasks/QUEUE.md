# Task Queue

## Next

- [x] Configure key-based `sauce-bot` SSH access for `sauce@192.168.0.152`.
- [x] Capture JetPack, OS, Python, CUDA, ROS, storage, memory, and container runtime versions.
- [x] Define the bounded coding editor as the first representative job and a persisted patch as its success artifact.
- [x] Choose `systemd --user` supervision and versioned SSH deployment with rollback.
- [x] Define local health/readiness endpoints and reserve the versioned `/v1/jobs` interface.
- [x] Install and verify a persistent localhost-only Qwen3-Coder model service on the Jetson GPU.
- [x] Implement and deploy the bounded coding-job executor over disposable worktrees and the approved basic-tool policy.
- [ ] Connect the CI/PM control plane to create assigned worktrees and review returned patches.

## Later

- [ ] Add CI for linting, unit tests, packaging, and deployment dry runs.
- [ ] Add a Jetson smoke-test workflow that is opt-in and never requires secrets in CI logs.
- [ ] Document backup, upgrade, rollback, and recovery procedures.
- [ ] Add asynchronous queueing and cancellation after the synchronous contract has operating evidence.

## Decision log

| Date | Decision | Reason |
| --- | --- | --- |
| 2026-09-02 | Keep the control plane separate from the future worker runtime | Allows specification and CI work before target access is finalized |
| 2026-09-02 | Use `sauce-bot` as the Jetson SSH alias and `sauce-bot.local` as its network name | Recovered from prior local SSH command history; avoids pinning deployment to a DHCP address |
| 2026-09-03 | Use a synchronous, localhost-only bounded editor for v1 | Keeps the first operating contract reviewable before adding queue complexity |
