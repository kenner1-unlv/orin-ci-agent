# Research

- **Decision**: Require the source-owned `git_diff_check`, `python_unittest`, and `python_compileall` suite. **Rationale**: callers cannot weaken promotion gates. **Alternative**: caller-selected checks permit bypass.
- **Decision**: Require clean index, then stage only reviewed paths and compare the cached binary diff fingerprint before commit. **Rationale**: the commit content becomes cryptographically tied to review. **Alternative**: `git add -A` can include unrelated files.
- **Decision**: use `--no-verify` plus a nonexistent hooks path. **Rationale**: reviewed repository hooks are executable, untrusted input. **Alternative**: ordinary commit could execute worker-submitted code.
- **Decision**: local commit only. **Rationale**: publication and deployment remain separate explicit authorities.
