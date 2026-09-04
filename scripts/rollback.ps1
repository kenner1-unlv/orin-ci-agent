param(
    [string]$Target = "sauce-bot"
)

$ErrorActionPreference = "Stop"
ssh $Target @'
set -eu
base="$HOME/.local/share/persistent-worker"
current="$(readlink -f "$base/current")"
previous="$(find "$base/releases" -mindepth 1 -maxdepth 1 -type d ! -path "$current" -printf '%T@ %p\n' | sort -nr | head -n 1 | cut -d' ' -f2-)"
if [ -z "$previous" ]; then
  echo "No previous release is available." >&2
  exit 1
fi
ln -sfn "$previous" "$base/current"
systemctl --user restart persistent-worker.service
echo "Rolled back to $previous"
'@
