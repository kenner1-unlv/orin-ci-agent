[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$ReviewArtifact,
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string]$Message,
    [Parameter(Mandatory)][string]$Output
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $repoRoot '.tools\uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot '.tools\python'
& uv run --project (Join-Path $repoRoot 'reviewer') --python 3.12 python -m control_plane_reviewer.promote --review-artifact $ReviewArtifact --workspace $Workspace --message $Message --output $Output
exit $LASTEXITCODE
