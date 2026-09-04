# Data Model

- **Promotion request**: review artifact path, worktree root, bounded commit subject, new output path.
- **Validated review**: schema version, approval verdict, worker/review IDs, patch SHA-256, exact changed paths.
- **Promotion artifact**: schema version, promotion ID, source identities, checks, parent commit, new commit, patch SHA-256, timestamps, `committed` outcome.

States: validate -> rerun checks -> prove unchanged -> stage reviewed paths -> verify staged identity -> commit -> record artifact. Any pre-commit failure leaves HEAD unchanged.
