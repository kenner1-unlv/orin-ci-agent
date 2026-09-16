[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$PromotionArtifact,
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][ValidatePattern('^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$')][string]$RemoteWorkspace,
    [Parameter(Mandatory)][string]$Output,
    [string]$Target = 'sauce-bot'
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$workspaceRoot = (Resolve-Path -LiteralPath $Workspace).Path
$outputPath = [System.IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $outputPath) { throw "Handoff output already exists: $outputPath" }
if ($outputPath.StartsWith($workspaceRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Handoff output must be outside the promoted workspace.'
}

$token = [guid]::NewGuid().ToString('N')
$localBundle = Join-Path ([System.IO.Path]::GetTempPath()) "ci-handoff-$token.bundle"
$remoteBundle = "/tmp/ci-handoff-$token.bundle"
try {
    $env:UV_CACHE_DIR = Join-Path $repoRoot '.tools\uv-cache'
    $env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot '.tools\python'
    $preparedJson = & uv run --project (Join-Path $repoRoot 'reviewer') --python 3.12 python -m control_plane_reviewer.handoff --promotion-artifact $PromotionArtifact --workspace $Workspace --bundle $localBundle
    if ($LASTEXITCODE -ne 0) { throw 'CI handoff preparation was rejected.' }
    $prepared = $preparedJson | ConvertFrom-Json
    scp -q $localBundle "${Target}:$remoteBundle"
    if ($LASTEXITCODE -ne 0) { throw 'Unable to transfer the handoff bundle.' }

    $remoteScript = @'
set -euo pipefail
bundle="$1"
workspace="$2"
commit="$3"
expected_sha="$4"
handoff_id="$5"
root="/data/persistent-worker/worktrees"
state_root="/data/persistent-worker/state/handoffs"
[[ "$workspace" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$ ]]
[[ "$commit" =~ ^[0-9a-f]{40,64}$ ]]
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]]
[[ "$handoff_id" =~ ^[0-9a-f]{32}$ ]]
test -f "$bundle"
actual_sha="$(sha256sum "$bundle" | awk '{print $1}')"
test "$actual_sha" = "$expected_sha"
mkdir -p "$root" "$state_root"
dest="$root/$workspace"
test "$(dirname -- "$dest")" = "$root"
test ! -e "$dest"
cleanup=1
trap 'rm -f -- "$bundle"; if [[ "$cleanup" = 1 && -e "$dest" ]]; then rm -rf -- "$dest"; fi' EXIT
git clone --quiet --no-checkout "$bundle" "$dest"
git -C "$dest" checkout --quiet --detach "$commit"
test "$(git -C "$dest" rev-parse HEAD)" = "$commit"
test -z "$(git -C "$dest" status --porcelain=v1 --untracked-files=all)"
git -C "$dest" remote remove origin
marker="$state_root/$handoff_id.json"
test ! -e "$marker"
printf '{"schema_version":1,"handoff_id":"%s","workspace":"%s","commit_id":"%s","bundle_sha256":"%s"}\n' \
  "$handoff_id" "$workspace" "$commit" "$actual_sha" > "$marker"
cleanup=0
printf '%s\t%s\t%s\n' "$workspace" "$commit" "$marker"
'@
    $remoteCommand = "sed 's/\r$//' | bash -s -- '$remoteBundle' '$RemoteWorkspace' '$($prepared.commit_id)' '$($prepared.bundle_sha256)' '$($prepared.handoff_id)'"
    $remoteResult = $remoteScript | ssh $Target $remoteCommand
    if ($LASTEXITCODE -ne 0) { throw 'Remote handoff verification failed.' }
    $fields = @($remoteResult.Trim() -split "`t")
    if ($fields.Count -ne 3 -or $fields[0] -ne $RemoteWorkspace -or $fields[1] -ne $prepared.commit_id) {
        throw 'Remote handoff returned unexpected identity evidence.'
    }
    $prepared.outcome = 'transferred'
    $prepared | Add-Member -NotePropertyName target -NotePropertyValue $Target
    $prepared | Add-Member -NotePropertyName remote_workspace -NotePropertyValue $RemoteWorkspace
    $prepared | Add-Member -NotePropertyName remote_marker -NotePropertyValue $fields[2]
    $prepared | Add-Member -NotePropertyName transferred_at -NotePropertyValue ([DateTime]::UtcNow.ToString('o'))
    $parent = Split-Path -Parent $outputPath
    if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    $json = $prepared | ConvertTo-Json -Depth 8
    [System.IO.File]::WriteAllText($outputPath, $json + "`n", [System.Text.UTF8Encoding]::new($false))
    Write-Output "transferred: $($prepared.commit_id) workspace: $RemoteWorkspace artifact: $outputPath"
}
finally {
    ssh $Target rm -f -- $remoteBundle 2>$null
    if (Test-Path -LiteralPath $localBundle) { Remove-Item -LiteralPath $localBundle -Force }
}
