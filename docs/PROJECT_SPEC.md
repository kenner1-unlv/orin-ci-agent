# Persistent Worker Project Spec

## Purpose

Define and coordinate a reliable worker process running on a Jetson Orin 64GB, with this repository acting as its PM, CI, and specification control plane.

## Target

| Field | Value |
| --- | --- |
| Device | Jetson Orin 64GB |
| Network | Local wireless network |
| Host or IP | `192.168.0.152` (verified 2026-09-02; `sauce-bot.local` did not resolve) |
| SSH alias | `sauce-bot` |
| SSH user | `sauce` |
| SSH identity | `~/.ssh/id_ed25519` (path only; private key remains outside this repository) |
| OS / JetPack | Ubuntu 22.04.5 LTS / JetPack `6.2.1+b38` (L4T `36.4.7`) |
| Kernel / architecture | `5.15.148-tegra` / `aarch64` |
| CUDA availability | CUDA SDK `12.6.11` |
| Runtime | `/usr/bin/python3` (`3.10.12`); Docker `29.4.2`; ROS 2 Humble installed but not active |
| Durable storage | `/data` on 1.8 TiB NVMe; approximately 1.7 TiB free at inventory time |

## Initial requirements

- The worker must restart after an expected process failure or device reboot.
- Deployment must be repeatable from a clean checkout.
- Health, readiness, job start, job completion, and failure must be observable.
- Secrets and private key material must remain outside this repository.
- CI must validate the worker without requiring access to the Jetson.
- The worker must expose an explicit stop and graceful shutdown path.
- Runtime jobs must not implicitly install packages or download executable code.

## Open decisions

- What jobs will the worker execute first?
- What transport will submit jobs: SSH, HTTP, queue, or another protocol?
- Which process supervisor will own it: systemd, Docker, or another runtime?
- What data must persist across restarts?
- What is the acceptable CPU, memory, GPU, storage, and network budget?
- What constitutes a successful first milestone?

## Acceptance criteria for the first worker milestone

1. A clean checkout can be installed on the Jetson using documented commands.
2. The worker starts under the selected supervisor and survives a restart.
3. A local health check returns a useful status.
4. A representative job completes and produces a verifiable result.
5. Failure and shutdown behavior are covered by an automated test.
