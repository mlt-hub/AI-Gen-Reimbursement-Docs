param(
    [string] $BaseUrl = "http://127.0.0.1:5173/static/dist/",
    [int] $Width = 390,
    [int] $Height = 844,
    [string] $ScreenshotDir = ""
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "web_app"
$smokeScript = Join-Path $PSScriptRoot "web_mobile_smoke.mjs"

if (!(Test-Path $webRoot)) {
    throw "未找到前端目录: $webRoot"
}

if (!(Test-Path $smokeScript)) {
    throw "未找到移动端检查脚本: $smokeScript"
}

$node = Get-Command "node.exe" -ErrorAction SilentlyContinue
if (!$node) {
    $node = Get-Command "node" -ErrorAction SilentlyContinue
}
if (!$node) {
    throw "未找到 Node.js。"
}

$arguments = @(
    $smokeScript,
    "--base-url",
    $BaseUrl,
    "--width",
    [string] $Width,
    "--height",
    [string] $Height
)

if ($ScreenshotDir) {
    $arguments += @("--screenshot-dir", $ScreenshotDir)
}

Push-Location $webRoot
try {
    & $node.Source @arguments
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}
