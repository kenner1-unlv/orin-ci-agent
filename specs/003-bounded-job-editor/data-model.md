# Data Model: Bounded Coding Job Editor Evaluation

## Evaluation Case

- `id`: stable unique identifier
- `category`: localized, diagnosis, multi-file, test, new-file, or no-op
- `fixture_revision`: pinned commit or digest
- `instruction`: only text exposed to the model
- `approved_checks`: stable worker check identifiers
- `allowed_changed_paths`: evaluator-side paths or patterns
- `oracle`: hidden evaluator identifier and timeout
- `reference_patch`: calibration-only, never model-visible

The unpatched fixture must fail its targeted oracle and the reference patch must
pass. Every fixture must be clean before an attempt.

## Evaluation Attempt

- Case identity, one-based attempt number, and fresh workspace name
- Model digest, runtime version, worker version, and configuration
- Start/end timestamps and elapsed seconds
- Job ID/status, tool calls, checks, Git status, and patch
- Changed paths, oracle exit/output, and external `resolved` result
- Scope compliance, evidence consistency, retrieval result, failure category

States: `prepared -> submitted -> terminal -> graded -> retained`. Harness and
transport failures may be rerun; a safety failure terminates the campaign.

## Evaluation Run

- Run and suite revision, configuration, and attempt references
- Exact-resolve numerator/denominator and category scores
- Safety, scope, evidence, and retrieval counts
- Latency distribution, tool-use totals, and gate decision

One run contains many attempts. Each attempt references one case and durable
worker job. Raw records are append-only benchmark artifacts.

