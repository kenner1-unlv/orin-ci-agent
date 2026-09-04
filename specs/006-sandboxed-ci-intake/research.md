# Research

- Use a Git bundle plus patch rather than copying `.git` and the worktree; this minimizes transferred trust and reconstructs from immutable history.
- Refuse existing destinations and validate identifiers/archive members to prevent overwrite and traversal.
- Run the already trusted reviewer with fixed checks after reconstruction; do not duplicate policy.
