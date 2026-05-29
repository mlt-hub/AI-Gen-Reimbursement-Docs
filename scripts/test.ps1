$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (Test-Path $venvPython) {
    & $venvPython -m pytest @args
} else {
    & python -m pytest @args
}
exit $LASTEXITCODE
