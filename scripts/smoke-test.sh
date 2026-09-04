#!/usr/bin/env bash
set -euo pipefail

target="${1:-sauce@192.168.0.152}"
ssh "$target" bash -s <<'REMOTE'
set -euo pipefail
curl --fail --silent --show-error http://127.0.0.1:8765/health
printf '\n'
curl --fail --silent --show-error http://127.0.0.1:8765/ready
printf '\n'
REMOTE
