# Data Model: Control-Plane Code Review Gate

## Review Request

- `job_record`: required readable JSON record path
- `workspace`: required Git worktree root
- `allow_paths`: one or more repository-relative POSIX glob patterns
- `checks`: zero or more unique trusted check IDs
- `output`: new artifact path outside the workspace

## Patch Evidence

- `sha256`: stable lowercase hexadecimal fingerprint
- `changed_paths`: normalized relative paths, including both rename endpoints

## Finding

- `code`: stable identifier
- `severity`: `blocking` or `suggestion`
- `message`: bounded explanation
- `path` and `line`: optional location

## Check Result

- `id`: trusted registry key
- `status`: `passed`, `failed`, `timeout`, or `unavailable`
- `exit_code`: integer or null
- `duration_ms`: nonnegative integer
- `output`: bounded diagnostics

## Review Artifact

- schema version, review ID, worker job ID, timestamps, verdict
- patch fingerprint, changed paths, findings, check results
- aggregate pre-review and post-review state fingerprints

State transition: validate -> collect evidence -> evaluate policy -> run checks -> prove non-mutation -> exclusively create artifact. Any blocker requests changes.
