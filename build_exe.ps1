Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI生成项目报账文档 — 打包 exe" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 PyInstaller
$pyi = pip show pyinstaller 2>$null
if (-not $pyi) {
    Write-Host "[安装] PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# 读取版本号（用于 zip 文件名）
$toml = "$PSScriptRoot\pyproject.toml"
$ver = (Select-String -Path $toml -Pattern '^version = "(.+)"' | ForEach-Object { $_.Matches.Groups[1].Value })
if (-not $ver) { $ver = "unknown" }
$exe_name = "ard"
Write-Host "[版本] $ver" -ForegroundColor Cyan

# 清理旧构建
Write-Host "[清理] 旧构建..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 打包（使用绝对路径避免路径解析问题）
$root = $PSScriptRoot
Write-Host "[打包] 生成 $exe_name.exe..." -ForegroundColor Yellow
pyinstaller --onefile `
    --name $exe_name `
    --add-data "$root\ai_gen_reimbursement_docs;ai_gen_reimbursement_docs" `
    --add-data "$root\pyproject.toml;." `
    --hidden-import "openpyxl.cell._writer" `
    --collect-all "fastapi" `
    --collect-all "uvicorn" `
    --collect-all "starlette" `
    --collect-all "python_multipart" `
    --distpath dist `
    --workpath build `
    --specpath build `
    --console `
    "$root\ai_gen_reimbursement_docs\main.py"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 打包失败！" -ForegroundColor Red
    pause
    exit 1
}

# 复制模板和配置
Write-Host "[复制] 附加文件..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$root\dist\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$root\dist\config" | Out-Null
# 生成版本标记文件
"ai-gen-reimbursement-docs v$ver" | Out-File -Encoding utf8 "$root\dist\ard_v$ver"
Copy-Item "$root\pyproject.toml" "$root\dist\pyproject.toml" -Force
Copy-Item "$root\README.md" "$root\dist\README.md" -Force
Copy-Item "$root\CHANGELOG.md" "$root\dist\CHANGELOG.md" -Force
Copy-Item "$root\data\out_templates" "$root\dist\data\out_templates" -Recurse -Force
Copy-Item "$root\data\in_templates" "$root\dist\data\in_templates" -Recurse -Force
Copy-Item "$root\data\audio" "$root\dist\data\audio" -Recurse -Force
Copy-Item "$root\config\.env.example" "$root\dist\config\.env.example" -Force
Copy-Item "$root\config\system_config.yaml.example" "$root\dist\config\system_config.yaml.example" -Force
Copy-Item "$root\config\business_rules.yaml.example" "$root\dist\config\business_rules.yaml.example" -Force
Copy-Item "$root\web_app" "$root\dist\web_app" -Recurse -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  exe: dist\$exe_name.exe" -ForegroundColor Green
Write-Host ""
Write-Host "  使用方法:" -ForegroundColor White
Write-Host "    dist\$exe_name.exe --from-excel 功能清单-录入模板.xlsx --gen-all" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
pause
