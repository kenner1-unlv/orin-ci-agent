# Orin Agentic Worker

This directory is the source of truth for the service deployed to the Jetson. Edit and test it here, then deploy a versioned copy to the device.

The service provides a bounded coding editor backed by the local Ollama model. It can inspect and edit one clean, named Git worktree at a time. It cannot execute a generic shell command, mutate Git history, commit, push, or address paths outside that worktree.

## Local development

```bash
./scripts/test-worker.sh
cd worker
PYTHONPATH=src python3 -m orin_worker
```

The service listens on `127.0.0.1:8765` by default. Its worktrees live below `/data/persistent-worker/worktrees`, job records below `/data/persistent-worker/state/jobs`, and patch artifacts below `/data/persistent-worker/artifacts/jobs`.

```bash
curl --fail http://127.0.0.1:8765/health
curl --fail http://127.0.0.1:8765/ready
```

## Deploy to the Jetson

From the repository root:

```bash
./scripts/deploy.sh
./scripts/smoke-test.sh
```

Deployments live under `~/.local/share/persistent-worker/releases`. The active release is selected by the `current` symlink. Runtime state remains in `~/.local/state/persistent-worker` and is not replaced during deployment.

The service uses the Jetson's system Python 3 and currently has no third-party runtime dependencies.
Agent sampling defaults to temperature 0 and seed 0 to reduce repository-task
variance. The model may still vary across complete multi-turn tool loops, so
promotion decisions use repeated external-oracle evaluation rather than one job.

To run after boot without an interactive login, enable user lingering once on the Jetson:

```bash
sudo loginctl enable-linger sauce
```

## API v1

- `GET /health`: process is alive.
- `GET /ready`: state storage is writable and the worker can accept work.
- `POST /v1/jobs`: synchronously execute one bounded edit job.
- `GET /v1/jobs/{id}`: retrieve a persisted job record.

Example request:

```json
{
  "kind": "edit",
  "workspace": "assigned-worktree",
  "instruction": "Add a regression test for the empty input case.",
  "checks": ["python_unittest", "git_diff_check"]
}
```

The `workspace` is a single directory name below `WORKER_WORKTREE_ROOT`. Supported check IDs are `git_diff_check`, `python_unittest`, and `python_compileall`. Callers cannot provide commands or arguments.
