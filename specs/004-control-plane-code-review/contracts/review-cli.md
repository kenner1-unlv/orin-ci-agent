# CLI Contract

```text
review-worker-job.ps1
  -JobRecord <path>
  -Workspace <path>
  -AllowPath <glob> [-AllowPath <glob> ...]
  [-Check <trusted-id> ...]
  -Output <new-json-path>
```

Trusted check IDs: `git_diff_check`, `python_unittest`, `python_compileall`.

The command prints a one-line verdict and artifact path. Exit `0` means approved, `1` means changes requested, and `2` means invalid input or execution failure. It refuses unknown or duplicate checks, unsupported worker states, output inside the workspace, and existing output. Neither the record nor CLI accepts command text.
