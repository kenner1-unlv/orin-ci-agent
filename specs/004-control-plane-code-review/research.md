# Research: Control-Plane Code Review Gate

## Decision: Separate control-plane package

**Rationale**: Review policy must not be shipped from or controlled by the worker it evaluates. A standard-library package with a small Windows launcher minimizes dependencies.

**Alternatives considered**: Extending the worker collapses the trust boundary. PowerShell-only logic is harder to test portably.

## Decision: Canonical Git evidence compatible with the worker

**Rationale**: Capture the tracked binary diff from `HEAD`, enumerate untracked paths with NUL delimiters, sort them, and append no-index binary diffs. Compare exact evidence and hash it with SHA-256. Scope inspection checks both rename endpoints.

**Alternatives considered**: A temporary Git index may execute repository-configured clean filters. A separate clone is stronger isolation but adds lifecycle complexity.

## Decision: Immutable trusted-check registry

**Rationale**: Requests select stable identifiers only. Source-owned argument arrays launch without a shell. No repository, worker, or caller field contributes executable text.

**Alternatives considered**: Command strings are flexible but turn reviewed input into execution authority.

## Decision: Pre/post repository state proof

**Rationale**: Hash HEAD, staged diff, canonical patch, and a full non-`.git` filesystem manifest before and after checks. This catches ignored cache, index, and commit mutations.

**Alternatives considered**: Git status misses ignored outputs. Immutable copied/containerized review remains later hardening.

## Decision: Deterministic verdict

**Rationale**: Patch mismatch, scope violations, binary changes, likely credentials, failed checks, and workspace mutation block. Any blocker yields `request_changes`; invalid execution is separate.

**Alternatives considered**: Model commentary may add value later but cannot override deterministic evidence.
