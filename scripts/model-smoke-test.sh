#!/usr/bin/env bash
set -euo pipefail

readonly endpoint='http://127.0.0.1:11434'
readonly model='qwen3-coder:30b-a3b-q4_K_M'

curl --fail --silent --show-error "$endpoint/api/tags" | grep -F "$model" >/dev/null
curl --fail --silent --show-error "$endpoint/api/generate" \
  -H 'Content-Type: application/json' \
  -d "{\"model\":\"$model\",\"prompt\":\"Reply with exactly READY\",\"stream\":false,\"options\":{\"num_ctx\":2048,\"temperature\":0}}"
printf '\n'

ros_state="$(systemctl is-active orin_stack.service 2>/dev/null || true)"
if [[ "$ros_state" != inactive ]]; then
  printf 'Expected orin_stack.service to be inactive, found %s\n' "$ros_state" >&2
  exit 1
fi
if ps -eo comm,args --no-headers | grep -Eiq '[r]os2|[r]oscore|[r]oslaunch|[p]oint_lio|[n]av2|[s]lam_toolbox'; then
  echo 'ROS process detected after model test' >&2
  exit 1
fi
