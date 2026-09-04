#!/usr/bin/env bash
set -euo pipefail

echo SERVICE
systemctl --user is-enabled orin-model.service
systemctl --user is-active orin-model.service

echo ENDPOINT
curl --fail --silent http://127.0.0.1:11434/api/version
printf '\n'
ss -ltnp | grep -F '127.0.0.1:11434'

echo MODEL
/data/persistent-worker/tools/ollama-current/bin/ollama list
/data/persistent-worker/tools/ollama-current/bin/ollama ps

echo STORAGE
du -sh /data/persistent-worker/models/ollama
df -h /data

echo MEMORY
free -h

echo BASIC_COMMANDS
for command_name in bash git curl python3 cmake make gcc g++ rg jq sed awk grep find patch tar sha256sum; do
  if command -v "$command_name" >/dev/null 2>&1; then
    printf '%-12s %s\n' "$command_name" "$(command -v "$command_name")"
  else
    printf '%-12s missing\n' "$command_name"
  fi
done

echo ROS
systemctl is-active orin_stack.service 2>/dev/null || true
if ps -eo comm,args --no-headers | grep -Eiq '[r]os2|[r]oscore|[r]oslaunch|[p]oint_lio|[n]av2|[s]lam_toolbox'; then
  echo running
  exit 1
fi
echo no-ros-processes
