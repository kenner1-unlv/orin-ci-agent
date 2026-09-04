param(
    [string]$Target = "sauce-bot"
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$workerRoot = Join-Path $repoRoot "worker"
$release = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$archive = Join-Path ([System.IO.Path]::GetTempPath()) "persistent-worker-$release.tar.gz"

try {
    tar -C $workerRoot -czf $archive --exclude="__pycache__" --exclude=".pytest_cache" .
    scp $archive "${Target}:/tmp/persistent-worker-$release.tar.gz"
    ssh $Target @"
set -eu
base="`$HOME/.local/share/persistent-worker"
release="`$base/releases/$release"
mkdir -p "`$release" "`$HOME/.config/persistent-worker" "`$HOME/.config/systemd/user" "`$HOME/.local/state/persistent-worker"
mkdir -p /data/persistent-worker/state /data/persistent-worker/models /data/persistent-worker/artifacts /data/persistent-worker/cache
tar -xzf "/tmp/persistent-worker-$release.tar.gz" -C "`$release"
rm "/tmp/persistent-worker-$release.tar.gz"
cp "`$release/deploy/persistent-worker.service" "`$HOME/.config/systemd/user/persistent-worker.service"
if [ ! -f "`$HOME/.config/persistent-worker/worker.env" ]; then
  cp "`$release/config/worker.env.example" "`$HOME/.config/persistent-worker/worker.env"
fi
ln -sfn "`$release" "`$base/current"
systemctl --user daemon-reload
systemctl --user enable --now persistent-worker.service
systemctl --user restart persistent-worker.service
PYTHONPATH="`$release/src" /usr/bin/python3 -m unittest discover -s "`$release/tests" -v
systemctl --user --no-pager --full status persistent-worker.service
"@
}
finally {
    if (Test-Path -LiteralPath $archive) {
        Remove-Item -LiteralPath $archive -Force
    }
}
