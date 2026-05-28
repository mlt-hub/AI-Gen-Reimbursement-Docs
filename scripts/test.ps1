$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (!(Test-Path $venvPython)) {
    throw "未找到 .venv Python: $venvPython"
}

& $venvPython -m pytest @args
exit $LASTEXITCODE
