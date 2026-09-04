[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$JobRecord,
    [Parameter(Mandatory)][string]$Workspace,
    [Parameter(Mandatory)][string[]]$AllowPath,
    [string[]]$Check = @(),
    [Parameter(Mandatory)][string]$Output
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $repoRoot '.tools\uv-cache'
$env:UV_PYTHON_INSTALL_DIR = Join-Path $repoRoot '.tools\python'
$arguments = @('run', '--project', (Join-Path $repoRoot 'reviewer'), '--python', '3.12', 'python', '-m', 'control_plane_reviewer', '--job-record', $JobRecord, '--workspace', $Workspace)
foreach ($path in $AllowPath) { $arguments += @('--allow-path', $path) }
foreach ($checkId in $Check) { $arguments += @('--check', $checkId) }
$arguments += @('--output', $Output)
& uv @arguments
exit $LASTEXITCODE
