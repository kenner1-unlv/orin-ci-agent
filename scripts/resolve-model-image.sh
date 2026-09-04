#!/usr/bin/env bash
set -euo pipefail

readonly root='/data/persistent-worker/tools/jetson-containers'

if [[ ! -f "$root/.env" ]]; then
  cp "$root/.env.default" "$root/.env"
fi

cd "$root"
./autotag ollama
