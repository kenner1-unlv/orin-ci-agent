# Contract: Golden Worktree Evaluation

The harness prepares a fixture and calls the existing worker API:

```http
POST /v1/jobs
Content-Type: application/json
```

```json
{
  "kind": "edit",
  "workspace": "eval-case-attempt",
  "instruction": "Issue text visible to the model",
  "checks": ["python_unittest", "git_diff_check"]
}
```

It retrieves the returned ID through `GET /v1/jobs/{id}` and requires the durable
terminal record to match the POST response's identity and evidence.

The evaluator-owned manifest must not pass hidden tests, oracle, allowed paths,
reference patch, commands, or executable arguments through the worker API. After
the worker returns, the harness independently inspects the worktree and runs its
hidden oracle.

`resolved=true` requires hidden tests with no regression, allowed-path compliance,
clean `git diff --check`, consistent returned evidence, and retrievable durable
state. Worker `status=completed` alone never implies resolution.

