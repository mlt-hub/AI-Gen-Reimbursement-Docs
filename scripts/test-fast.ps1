$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
& (Join-Path $repoRoot "scripts\test.ps1") -m "not slow" @args
exit $LASTEXITCODE
