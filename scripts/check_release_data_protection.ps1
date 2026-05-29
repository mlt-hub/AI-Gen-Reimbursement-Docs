param(
    [Parameter(Mandatory = $true)]
    [string]$ArtifactDir,

    [switch]$RequireProtectedData
)

$ErrorActionPreference = "Stop"

$artifact = Resolve-Path -LiteralPath $ArtifactDir -ErrorAction Stop
$artifactPath = $artifact.Path
$failed = $false

function Fail($Message) {
    Write-Host "[错误] $Message" -ForegroundColor Red
    $script:failed = $true
}

function Warn($Message) {
    Write-Host "[提示] $Message" -ForegroundColor Yellow
}

$forbiddenPatterns = @(
    "*private_key*.pem",
    "*signing_private_key*.pem",
    "*master_secret*",
    "*issued_licenses.jsonl",
    "*license_secret*",
    "*cek*.txt",
    "*cek*.b64"
)

foreach ($pattern in $forbiddenPatterns) {
    $matches = Get-ChildItem -LiteralPath $artifactPath -Recurse -Force -File -Filter $pattern -ErrorAction SilentlyContinue
    foreach ($match in $matches) {
        Fail "发布包包含敏感文件: $($match.FullName)"
    }
}

$dataEnc = Join-Path $artifactPath "data.enc"
$publicKey = Join-Path $artifactPath "ai_gen_reimbursement_docs\licensing\public_key.pem"

if (-not (Test-Path -LiteralPath $dataEnc -PathType Leaf)) {
    if ($RequireProtectedData) {
        Fail "发布包缺少 data.enc"
    } else {
        Warn "发布包未包含 data.enc"
    }
}

if (-not (Test-Path -LiteralPath $publicKey -PathType Leaf)) {
    if ($RequireProtectedData) {
        Fail "发布包缺少 public_key.pem"
    } else {
        Warn "发布包未包含 public_key.pem"
    }
}

$rawProtectedDirs = @(
    "ai_gen_reimbursement_docs\licensing\private_key.pem",
    ".ard-keys",
    "data\in_templates",
    "data\out_templates",
    "data\audio"
)

foreach ($relativePath in $rawProtectedDirs) {
    $candidate = Join-Path $artifactPath $relativePath
    if (Test-Path -LiteralPath $candidate) {
        Fail "发布包包含不应分发的路径: $candidate"
    }
}

$dataDir = Join-Path $artifactPath "data"
if (Test-Path -LiteralPath $dataDir -PathType Container) {
    $dataItems = Get-ChildItem -LiteralPath $dataDir -Force -Recurse -ErrorAction SilentlyContinue
    foreach ($item in $dataItems) {
        Fail "发布包包含明文 data 内容: $($item.FullName)"
    }
}

$publicAudio = Join-Path $artifactPath "web_app\static\audio\ticktick_pop.wav"
if (-not (Test-Path -LiteralPath $publicAudio -PathType Leaf)) {
    Warn "发布包未包含 Web 提示音资源: web_app\static\audio\ticktick_pop.wav"
}

if ($failed) {
    exit 1
}

Write-Host "[通过] 发布包数据保护检查完成: $artifactPath" -ForegroundColor Green
exit 0
