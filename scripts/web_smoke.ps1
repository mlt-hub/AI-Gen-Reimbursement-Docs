param(
    [string] $BaseUrl = "http://127.0.0.1:5173/static/dist/",
    [int] $VirtualTimeBudgetMs = 3000,
    [string] $EdgePath = ""
)

$ErrorActionPreference = "Stop"

function Find-Edge {
    param([string] $ExplicitPath)

    if ($ExplicitPath -and (Test-Path $ExplicitPath)) {
        return $ExplicitPath
    }

    $candidates = @(
        "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        "C:\Program Files\Microsoft\Edge\Application\msedge.exe"
    )

    foreach ($candidate in $candidates) {
        if (Test-Path $candidate) {
            return $candidate
        }
    }

    $command = Get-Command "msedge.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }

    throw "未找到 Microsoft Edge。请通过 -EdgePath 指定 msedge.exe 路径。"
}

function Join-WebPath {
    param(
        [string] $Base,
        [string] $Path
    )

    $trimmed = $Base.TrimEnd("/")
    if (!$Path) {
        return "$trimmed/"
    }
    return "$trimmed/$($Path.TrimStart('/'))"
}

function Get-Dom {
    param(
        [string] $Url,
        [string] $BrowserPath
    )

    $args = @(
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--disable-crash-reporter",
        "--disable-features=msEdgeChinaBrowserImport",
        "--virtual-time-budget=$VirtualTimeBudgetMs",
        "--dump-dom",
        $Url
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $BrowserPath @args 2>$null | Out-String
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ([string]::IsNullOrWhiteSpace($output)) {
        throw "无法读取页面 DOM: $Url"
    }
    return $output
}

function Assert-Contains {
    param(
        [string] $Dom,
        [string] $Text,
        [string] $Url
    )

    if (!$Dom.Contains($Text)) {
        throw "页面缺少预期文本 '$Text': $Url"
    }
}

function Assert-AnyContains {
    param(
        [string] $Dom,
        [string[]] $Texts,
        [string] $Url
    )

    foreach ($text in $Texts) {
        if ($Dom.Contains($text)) {
            return
        }
    }
    throw "页面缺少任一预期文本 [$($Texts -join ', ')]: $Url"
}

$edge = Find-Edge -ExplicitPath $EdgePath
$homeUrl = Join-WebPath -Base $BaseUrl -Path ""
$configUrl = Join-WebPath -Base $BaseUrl -Path "config"
$promptDebugUrl = Join-WebPath -Base $BaseUrl -Path "prompt-debug"

Write-Host "Web smoke test: $homeUrl"
$homeDom = Get-Dom -Url $homeUrl -BrowserPath $edge
Assert-Contains -Dom $homeDom -Text "AI 生成项目报账文档" -Url $homeUrl
Assert-Contains -Dom $homeDom -Text "任务设置" -Url $homeUrl
Assert-Contains -Dom $homeDom -Text "执行监控" -Url $homeUrl
Assert-AnyContains -Dom $homeDom -Texts @("后端未连接", "后端已连接", "检查服务中") -Url $homeUrl

Write-Host "Web smoke test: $configUrl"
$configDom = Get-Dom -Url $configUrl -BrowserPath $edge
Assert-Contains -Dom $configDom -Text "AI 生成项目报账文档" -Url $configUrl
Assert-AnyContains -Dom $configDom -Texts @("环境变量", "个人配置", "系统配置") -Url $configUrl
Assert-Contains -Dom $configDom -Text "FPA 策略" -Url $configUrl
Assert-Contains -Dom $configDom -Text "方案与规则集" -Url $configUrl
Assert-Contains -Dom $configDom -Text "计算依据归类判定原则" -Url $configUrl
Assert-Contains -Dom $configDom -Text "CFP 计算公式" -Url $configUrl
Assert-Contains -Dom $configDom -Text "领域上下文" -Url $configUrl
Assert-Contains -Dom $configDom -Text "FPA 稳定边界" -Url $configUrl
Assert-Contains -Dom $configDom -Text "Prompt 配置" -Url $configUrl
Assert-Contains -Dom $configDom -Text "AI 场景提示词" -Url $configUrl
Assert-Contains -Dom $configDom -Text "高级配置" -Url $configUrl
Assert-Contains -Dom $configDom -Text "YAML / JSON 配置文件" -Url $configUrl

Write-Host "Web smoke test: $promptDebugUrl"
$promptDebugDom = Get-Dom -Url $promptDebugUrl -BrowserPath $edge
Assert-Contains -Dom $promptDebugDom -Text "通用提示词调试" -Url $promptDebugUrl
Assert-Contains -Dom $promptDebugDom -Text "AI 返回结果" -Url $promptDebugUrl

Write-Host "Web UI smoke test 通过。" -ForegroundColor Green
