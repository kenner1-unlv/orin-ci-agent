# Quickstart: Validate the Review Gate

## Prerequisites

- Git and `uv` are available on the control-plane machine.
- A completed worker job JSON record and matching worktree are local.

## Automated validation

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.tools/uv-cache')
$env:UV_PYTHON_INSTALL_DIR = (Join-Path (Resolve-Path '.tools') 'python')
uv run --project reviewer --python 3.12 python -m unittest discover -s reviewer/tests -v
```

The suite proves approval plus mismatch, scope, credential, failed-check, output, and mutation rejection.

## Review a worker job

```powershell
./scripts/review-worker-job.ps1 `
  -JobRecord C:\review-input\job.json `
  -Workspace C:\review-input\worktree `
  -AllowPath 'src/**','tests/**' `
  -Check git_diff_check,python_unittest `
  -Output C:\review-artifacts\review.json
```

Expect exit `0` and `approve` for matching safe evidence. Alter the workspace and use a fresh output path; expect exit `1` with `PATCH_MISMATCH`.
