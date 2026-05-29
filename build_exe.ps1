param(
    [switch]$RequireProtectedData
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  AI生成项目报账文档 — 打包 exe" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$root = $PSScriptRoot

function Fail($Message) {
    Write-Host "[错误] $Message" -ForegroundColor Red
    exit 1
}

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
Push-Location "$root\web_app"
if (-not (Test-Path "$root\web_app\node_modules")) {
    Write-Host "[前端] npm install..." -ForegroundColor Yellow
    npm install --silent
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Fail "npm install 失败。"
    }
} else {
    Write-Host "[前端] 已发现 node_modules，跳过 npm install。" -ForegroundColor Yellow
}
Write-Host "[前端] npm run build..." -ForegroundColor Yellow
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "[提示] 前端构建失败，等待后重试一次..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Fail "前端构建失败。"
    }
}
Pop-Location
if (-not (Test-Path "$root\web_app\static\dist\index.html")) {
    Fail "前端构建失败，未生成 web_app\static\dist\index.html。"
}

# 清理旧构建
Write-Host "[清理] 旧构建..." -ForegroundColor Yellow
$buildPath = Join-Path $root "build"
$distPath = Join-Path $root "dist"
foreach ($path in @($buildPath, $distPath)) {
    if (Test-Path -LiteralPath $path) {
        Remove-Item -LiteralPath $path -Recurse -Force -ErrorAction Stop
    }
    if (Test-Path -LiteralPath $path) {
        Fail "无法清理旧构建目录: $path"
    }
}

# 打包 --onedir（秒启动，不解压到 TEMP）
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
    Fail "打包失败。"
}

# 复制模板和配置到 dist/ard/
$outDir = "$root\dist\$exe_name"
Write-Host "[复制] 附加文件到 $outDir..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "$outDir\config" | Out-Null
# 版本标记文件
"ai-gen-reimbursement-docs v$ver" | Out-File -Encoding utf8 "$outDir\ard-v$ver"
Copy-Item "$root\pyproject.toml" "$outDir\pyproject.toml" -Force
Copy-Item "$root\README.md" "$outDir\README.md" -Force
Copy-Item "$root\CHANGELOG.md" "$outDir\CHANGELOG.md" -Force
if (Test-Path "$root\assets\audio") {
    New-Item -ItemType Directory -Force -Path "$outDir\assets" | Out-Null
    New-Item -ItemType Directory -Force -Path "$outDir\web_app\static" | Out-Null
    Copy-Item "$root\assets\audio" "$outDir\assets\audio" -Recurse -Force
    Copy-Item "$root\assets\audio" "$outDir\web_app\static\audio" -Recurse -Force
} else {
    Write-Host "[提示] 未发现 assets\audio，提示音资源不会进入发布包。" -ForegroundColor Yellow
}
if (Test-Path "$root\data.enc") {
    Copy-Item "$root\data.enc" "$outDir\data.enc" -Force
} elseif ($RequireProtectedData) {
    Write-Host "[错误] 发布包缺少 data.enc，请先运行 scripts\build_data_package.py。" -ForegroundColor Red
    exit 1
} else {
    Write-Host "[提示] 未发现 data.enc，本次构建不会包含受保护数据包。" -ForegroundColor Yellow
}
if (Test-Path "$root\ai_gen_reimbursement_docs\licensing\public_key.pem") {
    New-Item -ItemType Directory -Force -Path "$outDir\ai_gen_reimbursement_docs\licensing" | Out-Null
    Copy-Item "$root\ai_gen_reimbursement_docs\licensing\public_key.pem" "$outDir\ai_gen_reimbursement_docs\licensing\public_key.pem" -Force
} elseif ($RequireProtectedData) {
    Write-Host "[错误] 发布包缺少 public_key.pem，请从发行方密钥目录复制公钥到 ai_gen_reimbursement_docs\licensing\public_key.pem。" -ForegroundColor Red
    exit 1
} else {
    Write-Host "[提示] 未发现 public_key.pem，离线激活需要通过 --public-key 指定公钥。" -ForegroundColor Yellow
}
Copy-Item "$root\config\.env.example" "$outDir\config\.env.example" -Force
Copy-Item "$root\config\system_config.yaml.example" "$outDir\config\system_config.yaml.example" -Force
# 只拷贝 web_app 的必要文件（server.py + 前端构建产物）
New-Item -ItemType Directory -Force -Path "$outDir\web_app\static\dist" | Out-Null
Copy-Item "$root\web_app\server.py" "$outDir\web_app\server.py" -Force
Copy-Item "$root\web_app\static\dist\*" "$outDir\web_app\static\dist" -Recurse -Force

Write-Host "[检查] 发布包数据保护..." -ForegroundColor Yellow
& "$root\scripts\check_release_data_protection.ps1" -ArtifactDir "$outDir" -RequireProtectedData:$RequireProtectedData
if ($LASTEXITCODE -ne 0) {
    Write-Host "[错误] 发布包数据保护检查失败！" -ForegroundColor Red
    exit 1
}

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
if (-not $env:GITHUB_ACTIONS) {
    pause
}
