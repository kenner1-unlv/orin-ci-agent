#!/usr/bin/env bash
set -euo pipefail

target="${1:-sauce@192.168.0.152}"
ssh "$target" bash -s <<'REMOTE'
set -euo pipefail
name="bounded-editor-smoke-$(date -u +%Y%m%dT%H%M%SZ)"
repo="/data/persistent-worker/worktrees/$name"
mkdir -p "$repo"
git -C "$repo" init -q
git -C "$repo" config user.email smoke@example.invalid
git -C "$repo" config user.name "Bounded Editor Smoke"
printf 'The deployment marker is ALPHA.\n' > "$repo/README.md"
git -C "$repo" add README.md
git -C "$repo" commit -qm fixture

request="$(jq -n --arg workspace "$name" '{kind:"edit",workspace:$workspace,instruction:"In README.md, replace the deployment marker ALPHA with BETA. Make no other changes.",checks:["git_diff_check"]}')"
response="$(curl --fail --silent --show-error --max-time 300 -H 'Content-Type: application/json' -d "$request" http://127.0.0.1:8765/v1/jobs)"
printf '%s\n' "$response" | jq '{id,status,summary,checks,git_status,diff,error,message}'
test "$(printf '%s\n' "$response" | jq -r .status)" = completed
grep -qx 'The deployment marker is BETA.' "$repo/README.md"
printf '%s\n' "$response" | jq -er '.diff | contains("-The deployment marker is ALPHA.") and contains("+The deployment marker is BETA.")' >/dev/null
job_id="$(printf '%s\n' "$response" | jq -r .id)"
curl --fail --silent --show-error "http://127.0.0.1:8765/v1/jobs/$job_id" | jq -e --arg id "$job_id" '.id == $id and .status == "completed"' >/dev/null
printf 'SMOKE_OK workspace=%s job=%s\n' "$name" "$job_id"
REMOTE
