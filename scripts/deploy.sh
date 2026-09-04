#!/usr/bin/env bash
set -euo pipefail

target="${1:-sauce@192.168.0.152}"
repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${TMPDIR:-/tmp}/persistent-worker-$release.tar.gz"
trap 'rm -f "$archive"' EXIT

tar -C "$repo_root/worker" -czf "$archive" --exclude=__pycache__ --exclude=.pytest_cache .
scp "$archive" "$target:/tmp/persistent-worker-$release.tar.gz"
ssh "$target" bash -s -- "$release" <<'REMOTE'
set -euo pipefail
release_id="$1"
base="$HOME/.local/share/persistent-worker"
release_dir="$base/releases/$release_id"
mkdir -p "$release_dir" "$HOME/.config/persistent-worker" "$HOME/.config/systemd/user"
mkdir -p /data/persistent-worker/state /data/persistent-worker/models /data/persistent-worker/artifacts /data/persistent-worker/cache /data/persistent-worker/worktrees
tar -xzf "/tmp/persistent-worker-$release_id.tar.gz" -C "$release_dir"
rm -f "/tmp/persistent-worker-$release_id.tar.gz"
cp "$release_dir/deploy/persistent-worker.service" "$HOME/.config/systemd/user/persistent-worker.service"
if [[ ! -f "$HOME/.config/persistent-worker/worker.env" ]]; then
  cp "$release_dir/config/worker.env.example" "$HOME/.config/persistent-worker/worker.env"
else
  while IFS= read -r line; do
    key="${line%%=*}"
    grep -q "^${key}=" "$HOME/.config/persistent-worker/worker.env" || printf '%s\n' "$line" >> "$HOME/.config/persistent-worker/worker.env"
  done < "$release_dir/config/worker.env.example"
fi
PYTHONPATH="$release_dir/src" /usr/bin/python3 -m unittest discover -s "$release_dir/tests" -v
ln -sfn "$release_dir" "$base/current"
systemctl --user daemon-reload
systemctl --user enable persistent-worker.service
systemctl --user restart persistent-worker.service
systemctl --user --no-pager --full status persistent-worker.service
REMOTE
