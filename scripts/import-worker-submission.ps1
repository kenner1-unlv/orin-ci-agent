[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{32}$')][string]$JobId,
    [string]$Target = 'sauce-bot',
    [Parameter(Mandatory)][string[]]$AllowPath,
    [string]$SandboxRoot
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
if (-not $SandboxRoot) { $SandboxRoot = Join-Path $repoRoot '.ci-sandboxes' }
$localTemp = Join-Path ([System.IO.Path]::GetTempPath()) "ci-submission-$JobId.tar.gz"
$remoteArchive = "/tmp/ci-submission-$JobId.tar.gz"
$extractRoot = $null
try {
    $remoteScript = @'
set -euo pipefail
job_id="$1"
archive="$2"
[[ "$job_id" =~ ^[0-9a-f]{32}$ ]]
job="/data/persistent-worker/state/jobs/$job_id.json"
test -f "$job"
workspace="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["workspace"])' "$job")"
[[ "$workspace" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]
repo="/data/persistent-worker/worktrees/$workspace"
test "$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["status"])' "$job")" = completed
tmp="$(mktemp -d)"
trap 'rm -rf -- "$tmp"' EXIT
cp -- "$job" "$tmp/job.json"
python3 -c 'import json,sys; open(sys.argv[2],"w",encoding="utf-8",newline="").write(json.load(open(sys.argv[1]))["diff"])' "$job" "$tmp/submission.patch"
git -C "$repo" bundle create "$tmp/base.bundle" HEAD
tar -C "$tmp" -czf "$archive" job.json submission.patch base.bundle
'@
    $remoteCommand = "sed 's/\r$//' | bash -s -- '$JobId' '$remoteArchive'"
    $remoteScript | ssh $Target $remoteCommand
    scp -q "${Target}:$remoteArchive" $localTemp
    $members = @(tar -tzf $localTemp | ForEach-Object { $_.TrimEnd('/') } | Where-Object { $_ })
    $memberList = (@($members | Sort-Object) -join ',')
    if ($memberList -ne 'base.bundle,job.json,submission.patch') { throw 'Submission archive contains unexpected members.' }
    $extractRoot = Join-Path ([System.IO.Path]::GetTempPath()) "ci-intake-$JobId"
    if (Test-Path -LiteralPath $extractRoot) { throw "Temporary intake path already exists: $extractRoot" }
    New-Item -ItemType Directory -Path $extractRoot | Out-Null
    tar -xzf $localTemp -C $extractRoot
    $env:UV_CACHE_DIR = Join-Path $repoRoot '.tools\uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot '.tools\python'
    $arguments = @('run','--project',(Join-Path $repoRoot 'reviewer'),'--python','3.12','python','-m','control_plane_reviewer.intake','--job-record',(Join-Path $extractRoot 'job.json'),'--bundle',(Join-Path $extractRoot 'base.bundle'),'--patch',(Join-Path $extractRoot 'submission.patch'),'--sandbox-root',$SandboxRoot)
    foreach ($path in $AllowPath) { $arguments += @('--allow-path',$path) }
    & uv @arguments
    exit $LASTEXITCODE
}
finally {
    ssh $Target rm -f -- $remoteArchive 2>$null
    if (Test-Path -LiteralPath $localTemp) { Remove-Item -LiteralPath $localTemp -Force }
    if ($extractRoot -and (Test-Path -LiteralPath $extractRoot)) { Remove-Item -LiteralPath $extractRoot -Recurse -Force }
}
