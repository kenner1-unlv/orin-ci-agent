# Promotion CLI

`promote-worker-job.ps1 -ReviewArtifact <json> -Workspace <repo> -Message <subject> -Output <new-json>`

Exit 0 means one local commit was created. Exit 2 means promotion was rejected or failed. There is no check-selection, command, push, merge, tag, deploy, or remote option.
