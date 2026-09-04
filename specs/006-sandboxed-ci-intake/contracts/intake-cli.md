# Intake CLI

`import-worker-submission.ps1 -JobId <32hex> [-Target sauce-bot] [-AllowPath patterns]`

Creates `.ci-sandboxes/<job-id>/worktree`, `job.json`, `review.json`, and `intake.json`. It never commits or promotes.
