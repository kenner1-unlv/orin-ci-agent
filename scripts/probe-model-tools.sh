#!/usr/bin/env bash
set -euo pipefail

payload="$(jq -n '{model:"qwen3-coder:30b-a3b-q4_K_M",stream:false,messages:[{role:"user",content:"Use the finish tool with summary READY."}],tools:[{type:"function",function:{name:"finish",description:"Finish",parameters:{type:"object",required:["summary"],properties:{summary:{type:"string"}}}}}]}')"
curl --silent --show-error --include --max-time 120 -H 'Content-Type: application/json' -d "$payload" http://127.0.0.1:11434/api/chat
