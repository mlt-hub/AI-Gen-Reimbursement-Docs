Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  COSMIC 工具 — 打包 exe" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 PyInstaller
$pyi = pip show pyinstaller 2>$null
if (-not $pyi) {
    Write-Host "[安装] PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# 从 pyproject.toml 读取版本号
$toml = "$PSScriptRoot\pyproject.toml"
$ver = (Select-String -Path $toml -Pattern '^version = "(.+)"' | ForEach-Object { $_.Matches.Groups[1].Value })
if (-not $ver) { $ver = "unknown" }
$exe_name = "cosmic_v$ver"
Write-Host "[版本] $ver" -ForegroundColor Cyan

# 清理旧构建
Write-Host "[清理] 旧构建..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 打包（使用绝对路径避免路径解析问题）
$root = $PSScriptRoot
Write-Host "[打包] 生成 $exe_name.exe..." -ForegroundColor Yellow
pyinstaller --onefile `
    --name $exe_name `
    --add-data "$root\cosmic_tool;cosmic_tool" `
    --add-data "$root\data\template.xlsx;data" `
    --hidden-import "openpyxl.cell._writer" `
    --distpath dist `
    --workpath build `
    --specpath build `
    --console `
    "$root\cosmic_tool\main.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 打包失败！" -ForegroundColor Red
    pause
    exit 1
}

# 复制模板和配置
Write-Host "[复制] 附加文件..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$root\dist\data" | Out-Null
Copy-Item "$root\data\template.xlsx" "$root\dist\data\" -Force
Copy-Item "$root\cosmic_tool\.env.example" "$root\dist\.env.example" -Force
Copy-Item "$root\cosmic_tool\business.env.example" "$root\dist\business.env.example" -Force
if (Test-Path "$root\cosmic_tool\.env") {
    Copy-Item "$root\cosmic_tool\.env" "$root\dist\.env" -Force
}
if (Test-Path "$root\cosmic_tool\business.env") {
    Copy-Item "$root\cosmic_tool\business.env" "$root\dist\business.env" -Force
}

# 复制一份并命名为 cosmic.exe（方便无版本号调用）
Copy-Item "$root\dist\$exe_name.exe" "$root\dist\cosmic.exe" -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  exe: dist\$exe_name.exe" -ForegroundColor Green
Write-Host "  别名: dist\cosmic.exe" -ForegroundColor Green
Write-Host ""
Write-Host "  使用方法:" -ForegroundColor White
Write-Host "    dist\$exe_name.exe --docx `"需求书.docx`" --all" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
pause
