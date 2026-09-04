#!/usr/bin/env bash
set -euo pipefail

readonly config_dir="$HOME/.config/persistent-worker"
readonly unit_dir="$HOME/.config/systemd/user"

mkdir -p "$config_dir" "$unit_dir"
cp /tmp/model-runtime.env "$config_dir/model-runtime.env"
cp /tmp/orin-model.service "$unit_dir/orin-model.service"

if docker container inspect orin-ollama >/dev/null 2>&1; then
  docker rm --force orin-ollama
fi

systemctl --user daemon-reload
systemctl --user enable --now orin-model.service

for attempt in $(seq 1 90); do
  if curl --fail --silent http://127.0.0.1:11434/api/version; then
    printf '\n'
    exit 0
  fi
  sleep 2
done

journalctl --user -u orin-model.service --no-pager -n 100 >&2
exit 1
