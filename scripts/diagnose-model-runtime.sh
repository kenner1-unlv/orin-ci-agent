#!/usr/bin/env bash
set -euo pipefail

systemctl --user stop orin-model.service || true
set -a
source "$HOME/.config/persistent-worker/model-runtime.env"
set +a
export OLLAMA_NUM_PARALLEL=1
export OLLAMA_MAX_LOADED_MODELS=1
export OLLAMA_FLASH_ATTENTION=1
export OLLAMA_KV_CACHE_TYPE=q8_0
timeout 15 /data/persistent-worker/tools/ollama-current/bin/ollama serve
