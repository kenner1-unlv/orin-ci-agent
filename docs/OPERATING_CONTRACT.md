# PM, CI, and Spec Operating Contract

## Responsibilities

- **PM:** maintain priorities, decisions, risks, and acceptance criteria.
- **Spec:** keep interfaces, deployment assumptions, and non-functional requirements explicit.
- **CI:** keep checks reproducible and independent of the physical Jetson where possible.
- **Worker:** implement only against an accepted task and its testable contract.

## Change flow

1. Capture the desired outcome in `tasks/QUEUE.md`.
2. Convert it into a small task with an acceptance check.
3. Update the relevant spec before changing an interface.
4. Implement and run the narrowest useful check first.
5. Record unresolved risks or decisions rather than hiding them in implementation details.

## Communication rules

- Do not place secrets, tokens, private keys, or copied production logs in this repository.
- Prefer facts that can be verified on the target over assumptions about the Jetson image.
- Every deployment-affecting change must include a rollback or recovery path.
- Keep the worker's control protocol versioned once the first interface exists.