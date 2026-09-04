#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root/worker"

python_bin="$(command -v python3 || true)"
if [[ -z "$python_bin" ]]; then
  for candidate in /c/Users/"${USERNAME:-russe}"/AppData/Local/Programs/Python/Python*/python.exe; do
    if [[ -x "$candidate" ]]; then
      python_bin="$candidate"
      break
    fi
  done
fi
if [[ -z "$python_bin" ]]; then
  echo "Python 3 was not found" >&2
  exit 127
fi

"$python_bin" -m unittest discover -s tests -v
"$python_bin" -m compileall -q src tests
