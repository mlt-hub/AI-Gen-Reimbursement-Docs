param(
    [string] $HostName = "127.0.0.1",
    [int] $Port = 5173,
    [int] $StartupTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$webRoot = Join-Path $repoRoot "web_app"
$artifactCheck = Join-Path $PSScriptRoot "check_web_source_artifacts.ps1"
$smokeScript = Join-Path $PSScriptRoot "web_smoke.ps1"

function Test-PortOpen {
    param(
        [string] $HostName,
        [int] $Port
    )

    $client = New-Object System.Net.Sockets.TcpClient
    try {
        $result = $client.BeginConnect($HostName, $Port, $null, $null)
        $success = $result.AsyncWaitHandle.WaitOne(300)
        if (!$success) {
            return $false
        }
        $client.EndConnect($result)
        return $true
    } catch {
        return $false
    } finally {
        $client.Close()
    }
}

function Find-FreePort {
    param(
        [string] $HostName,
        [int] $StartPort
    )

    for ($candidate = $StartPort; $candidate -lt ($StartPort + 20); $candidate++) {
        if (!(Test-PortOpen -HostName $HostName -Port $candidate)) {
            return $candidate
        }
    }

    throw "未找到可用端口: $StartPort-$($StartPort + 19)"
}

function Wait-ForUrl {
    param(
        [string] $Url,
        [int] $TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    do {
        try {
            $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 500) {
                return
            }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    } while ((Get-Date) -lt $deadline)

    throw "等待 Vite dev server 超时: $Url"
}

function Get-ListeningProcessIds {
    param([int] $Port)

    $ids = New-Object System.Collections.Generic.List[int]
    $pattern = "^\s*TCP\s+\S+:$Port\s+\S+\s+LISTENING\s+(\d+)\s*$"

    netstat -ano | ForEach-Object {
        if ($_ -match $pattern) {
            $ids.Add([int] $Matches[1])
        }
    }

    return $ids | Sort-Object -Unique
}

function Stop-DevServer {
    param(
        [System.Diagnostics.Process] $Process,
        [int] $Port
    )

    if ($Process -and (Get-Process -Id $Process.Id -ErrorAction SilentlyContinue)) {
        Stop-Process -Id $Process.Id -ErrorAction SilentlyContinue
    }

    Get-ListeningProcessIds -Port $Port | ForEach-Object {
        if ($_ -ne $PID) {
            Stop-Process -Id $_ -ErrorAction SilentlyContinue
        }
    }
}

if (!(Test-Path $webRoot)) {
    throw "未找到前端目录: $webRoot"
}

Write-Host "Step 1/4: 检查 web_app/src 生成物"
& $artifactCheck

Write-Host "Step 2/4: 执行前端生产构建"
Push-Location $webRoot
try {
    npm run build
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Pop-Location
}

$actualPort = Find-FreePort -HostName $HostName -StartPort $Port
if ($actualPort -ne $Port) {
    Write-Host "端口 $Port 已占用，改用 $actualPort。" -ForegroundColor Yellow
}

$baseUrl = "http://$HostName`:$actualPort/static/dist/"
$npm = Get-Command "npm.cmd" -ErrorAction SilentlyContinue
if (!$npm) {
    $npm = Get-Command "npm" -ErrorAction SilentlyContinue
}
if (!$npm) {
    throw "未找到 npm。"
}

$devProcess = $null
try {
    Write-Host "Step 3/4: 启动 Vite dev server ($baseUrl)"
    $devProcess = Start-Process -FilePath $npm.Source -ArgumentList @(
        "run",
        "dev",
        "--",
        "--host",
        $HostName,
        "--port",
        [string] $actualPort
    ) -WorkingDirectory $webRoot -WindowStyle Hidden -PassThru

    Wait-ForUrl -Url $baseUrl -TimeoutSeconds $StartupTimeoutSeconds

    Write-Host "Step 4/4: 执行 Web UI smoke test"
    & $smokeScript -BaseUrl $baseUrl
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
} finally {
    Stop-DevServer -Process $devProcess -Port $actualPort
}

Write-Host "Web UI 检查全部通过。" -ForegroundColor Green
