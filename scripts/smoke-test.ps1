param(
    [string]$Target = "sauce-bot"
)

$ErrorActionPreference = "Stop"
$remoteCommand = 'set -eu; curl --fail --silent --show-error http://127.0.0.1:8765/health; echo; curl --fail --silent --show-error http://127.0.0.1:8765/ready; echo'
ssh $Target $remoteCommand
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
