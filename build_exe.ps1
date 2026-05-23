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

# 读取版本号
$toml = "$PSScriptRoot\pyproject.toml"
$ver = (Select-String -Path $toml -Pattern '^version = "(.+)"' | ForEach-Object { $_.Matches.Groups[1].Value })
if (-not $ver) { $ver = "unknown" }
$exe_name = "ard"
Write-Host "[版本] $ver" -ForegroundColor Cyan

# 前端构建
Write-Host "[前端] npm install..." -ForegroundColor Yellow
Push-Location "$root\web_app"
npm install --silent
Write-Host "[前端] npm run build..." -ForegroundColor Yellow
npm run build
Pop-Location
if (-not (Test-Path "$root\web_app\static\dist\index.html")) {
    Write-Host "[错误] 前端构建失败！" -ForegroundColor Red
    pause
    exit 1
}

# 清理旧构建
Write-Host "[清理] 旧构建..." -ForegroundColor Yellow
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# 打包 --onedir（秒启动，不解压到 TEMP）
$root = $PSScriptRoot
Write-Host "[打包] 生成 $exe_name.exe (onedir)..." -ForegroundColor Yellow
pyinstaller `
    --name $exe_name `
    --add-data "$root\ai_gen_reimbursement_docs;ai_gen_reimbursement_docs" `
    --add-data "$root\pyproject.toml;." `
    --hidden-import "openpyxl.cell._writer" `
    --hidden-import "win32com" `
    --hidden-import "pythoncom" `
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

# 复制模板和配置到 dist/ard/
$outDir = "$root\dist\$exe_name"
Write-Host "[复制] 附加文件到 $outDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$outDir\data" | Out-Null
New-Item -ItemType Directory -Force -Path "$outDir\config" | Out-Null
# 版本标记文件
"ai-gen-reimbursement-docs v$ver" | Out-File -Encoding utf8 "$outDir\ard-v$ver"
Copy-Item "$root\pyproject.toml" "$outDir\pyproject.toml" -Force
Copy-Item "$root\README.md" "$outDir\README.md" -Force
Copy-Item "$root\CHANGELOG.md" "$outDir\CHANGELOG.md" -Force
Copy-Item "$root\data\out_templates" "$outDir\data\out_templates" -Recurse -Force
Copy-Item "$root\data\in_templates" "$outDir\data\in_templates" -Recurse -Force
Copy-Item "$root\data\audio" "$outDir\data\audio" -Recurse -Force
Copy-Item "$root\config\.env.example" "$outDir\config\.env.example" -Force
Copy-Item "$root\config\system_config.yaml.example" "$outDir\config\system_config.yaml.example" -Force
# 只拷贝 web_app 的必要文件（server.py + 前端构建产物）
New-Item -ItemType Directory -Force -Path "$outDir\web_app\static\dist" | Out-Null
Copy-Item "$root\web_app\server.py" "$outDir\web_app\server.py" -Force
Copy-Item "$root\web_app\static\dist\*" "$outDir\web_app\static\dist" -Recurse -Force

# 创建 zip 便携版
Write-Host "[ZIP] 打包 ard-v$ver.zip..." -ForegroundColor Yellow
Compress-Archive -Path "$outDir\*" -DestinationPath "$root\dist\ard-v$ver.zip" -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  打包完成！" -ForegroundColor Green
Write-Host "  exe: dist\$exe_name\$exe_name.exe" -ForegroundColor Green
Write-Host "  zip: dist\ard-v$ver.zip" -ForegroundColor Green
Write-Host ""
Write-Host "  使用方法:" -ForegroundColor White
Write-Host "    dist\$exe_name\$exe_name.exe --web" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Green
pause
