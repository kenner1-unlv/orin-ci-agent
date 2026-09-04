# Local Coding Model Runtime

## Pinned components

- Model: `qwen3-coder:30b-a3b-q4_K_M`
- Published size: 19 GB
- Ollama manifest identifier: `06c1097efce0`
- Quantization: `Q4_K_M`
- Jetson Containers commit: `70c149aea6126594153ef7690ec4890f8f396518`
- Runtime: official Ollama `v0.32.15` JetPack 6 ARM64 release artifact
- Initial context limit: 32,768 tokens
- Initial concurrency: one request
- Endpoint: `127.0.0.1:11434`

Verified runtime archives:

- ARM64 base: SHA-256 `c898270b1690eab0f51aa9e9197686b7b4c6a7d88b83967763818f3127e477e9`
- JetPack 6 add-on: SHA-256 `344636e28d3bd31ab44caae5ac917c02cbb77b4ab692acc9ef90fc83b6c80a02`

## Storage

- Model store: `/data/persistent-worker/models/ollama`
- Runtime tools: `/data/persistent-worker/tools`
- Coding worktrees: `/data/persistent-worker/worktrees`
- Coding artifacts: `/data/persistent-worker/artifacts`

## Security boundary

The endpoint is loopback-only. The `sauce` account is a member of the Docker group, which is effectively root-equivalent and must be treated as privileged. Unrestricted passwordless sudo is not configured. ROS remains inactive.

The first coding executor may read an assigned worktree and write only within that worktree and the worker artifact/cache roots. It may use basic repository and build commands, but it must not expose a generic remote shell through the worker API.

Available baseline commands include Bash, Git, ripgrep, jq, curl, Python 3, CMake, Make, GCC/G++, sed, awk, grep, find, patch, tar, and sha256sum. Command availability does not itself authorize execution; the future coding job contract defines the allowlist and writable worktree.

## Verified operation

- `orin-model.service` is enabled and active as a persistent user service.
- The endpoint is listening only on `127.0.0.1:11434`.
- Ollama reports version `0.32.15`.
- Qwen3-Coder is loaded with `100% GPU` processing.
- The model returned the required `READY` smoke-test response.
- Cold model load was approximately 11.1 seconds; a warm two-token smoke response completed in approximately 0.15 seconds.
- Model storage uses 18 GB under `/data`; approximately 40 GiB system memory remained available after loading.
- `orin_stack.service` remained inactive and no ROS processes were detected.

The first repeatable performance baseline measured median warm generation at
28.03 tokens/s and 5,060-token prompt processing at 737.42 tokens/s. See
[`MODEL_BENCHMARKS.md`](MODEL_BENCHMARKS.md) for the complete results and limits.

## Recovery

Stop or disable `orin-model.service` without deleting the model directory. Restarting the service reuses the downloaded model. Removing this capability requires disabling the user service, removing its unit/config, and optionally removing its dedicated `/data` model/runtime directories after explicit confirmation.
