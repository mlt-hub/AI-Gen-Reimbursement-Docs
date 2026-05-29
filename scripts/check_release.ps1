param(
    [string]$ArtifactDir = "dist\ard",
    [switch]$RequireProtectedData,
    [switch]$SkipArtifactCheck,
    [string[]]$PythonTestTargets = @(
        "tests/test_web_system.py",
        "tests/test_config_utils.py",
        "tests/test_licensing.py",
        "tests/test_logging_handler.py"
    )
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "web_app"
$testScript = Join-Path $repoRoot "scripts\test.ps1"
$dataProtectionCheck = Join-Path $repoRoot "scripts\check_release_data_protection.ps1"

function Step($Message) {
    Write-Host ""
    Write-Host "==> $Message" -ForegroundColor Cyan
}

Step "Python tests"
& $testScript @PythonTestTargets
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Step "Web build"
Push-Location $webRoot
try {
    npm run build
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
} finally {
    Pop-Location
}

Step "PowerShell syntax"
$scriptFiles = @(
    (Join-Path $repoRoot "build_exe.ps1"),
    $dataProtectionCheck,
    $PSCommandPath
)
foreach ($script in $scriptFiles) {
    $errors = $null
    [System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path $script), [ref]$null, [ref]$errors) | Out-Null
    if ($errors) {
        foreach ($error in $errors) {
            Write-Error "${script}: $($error.Message)"
        }
        exit 1
    }
    Write-Host "[通过] $script"
}

if (-not $SkipArtifactCheck) {
    Step "Release artifact data protection"
    $artifactPath = Join-Path $repoRoot $ArtifactDir
    if (-not (Test-Path -LiteralPath $artifactPath)) {
        if ($RequireProtectedData) {
            Write-Host "[错误] 发布产物不存在: $artifactPath" -ForegroundColor Red
            exit 1
        }
        Write-Host "[提示] 发布产物不存在，跳过发布包检查: $artifactPath" -ForegroundColor Yellow
    } else {
        & $dataProtectionCheck -ArtifactDir $artifactPath -RequireProtectedData:$RequireProtectedData
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
}

Write-Host ""
Write-Host "[通过] 发布前检查完成" -ForegroundColor Green
exit 0
