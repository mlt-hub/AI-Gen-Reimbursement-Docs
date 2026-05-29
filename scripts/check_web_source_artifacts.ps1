$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$srcRoot = Join-Path $repoRoot "web_app\src"

if (!(Test-Path $srcRoot)) {
    throw "未找到前端源码目录: $srcRoot"
}

$blockedPatterns = @("*.js", "*.vue.js", "*.vue.d.ts")
$found = New-Object System.Collections.Generic.List[System.IO.FileInfo]

foreach ($pattern in $blockedPatterns) {
    Get-ChildItem -Path $srcRoot -Recurse -File -Filter $pattern | ForEach-Object {
        $found.Add($_)
    }
}

$unique = $found | Sort-Object FullName -Unique

if ($unique.Count -gt 0) {
    Write-Host "web_app/src 下发现不应提交的生成文件:" -ForegroundColor Red
    $unique | ForEach-Object {
        $relative = Resolve-Path -LiteralPath $_.FullName -Relative
        Write-Host "  $relative"
    }
    Write-Host ""
    Write-Host "这些文件会干扰 Vite/TypeScript 模块解析，请删除后再运行检查。" -ForegroundColor Yellow
    exit 1
}

Write-Host "web_app/src 生成物检查通过。" -ForegroundColor Green
