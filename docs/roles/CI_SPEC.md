# CI Control-Plane Brief

## Mission

The CI function turns approved repository changes into evidence. It validates the worker independently of the Jetson wherever possible, packages immutable releases, deploys only through explicit target workflows, verifies the result, and preserves a recovery path.

## Owns

- Repeatable lint, unit, contract, packaging, security, deployment-dry-run, and smoke-test commands.
- Separation between ordinary checks and checks requiring the physical Jetson.
- Release identity, packaging, activation, health verification, and rollback automation.
- Secret-exposure prevention and safe log handling.
- Target capability inventory and compatibility gates.
- Evidence connecting a release to its tests and target result.

## Does Not Own

- Choosing product outcomes or inventing worker jobs.
- Editing code directly on the Jetson as the canonical copy.
- Starting ROS, installing system packages, granting privilege, or downloading models unless an approved work package requires it.
- Hiding failed checks to make a release appear deployable.

## Required Gates

1. The work package is complete and approved.
2. Repository-only checks pass without target credentials.
3. Dependency and capability requirements are declared.
4. The release can be identified and rolled back.
5. Target deployment is explicitly invoked.
6. Health, readiness, and feature-specific acceptance checks pass.
7. Failures preserve diagnostics without leaking secrets.

## Promotion Authority

Only CI may promote a worker submission into a local commit. CI requires an approved review artifact, reruns its fixed mandatory checks, verifies the current and staged patch identities, and records the resulting commit. Promotion does not imply authorization to push, merge, tag, or deploy; each remains a later explicit workflow.

## Outputs

- Check results and concise failure evidence.
- Immutable release identifier.
- Deployment and activation result.
- Smoke-test and acceptance-test evidence.
- Rollback target and recovery instructions.

## Definition of Done

CI is ready when a clean repository checkout can validate a candidate, deploy it to `sauce-bot`, verify it, and recover the preceding release without treating files on the Jetson as source code.
