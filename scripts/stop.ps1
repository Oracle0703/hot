[CmdletBinding()]
param(
    [int]$WaitSeconds = 15,
    [switch]$Force,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $ProjectRoot "data\launcher.pid"

function Write-Info {
    param([string]$Message)
    Write-Host "[stop] $Message"
}

if (-not (Test-Path $PidFile)) {
    Write-Info "未发现 PID 文件: $PidFile"
    Write-Info "若服务仍在运行，可手工关闭对应窗口或执行 Get-Process | Where-Object { `$_.ProcessName -like '*hot_collector*' }"
    exit 0
}

$pidText = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($pidText)) {
    Write-Info "PID 文件为空，直接清理: $PidFile"
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    exit 0
}

$processId = 0
if (-not [int]::TryParse($pidText.Trim(), [ref]$processId)) {
    Write-Info "PID 文件内容非法: $pidText，直接清理"
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    exit 0
}

$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    Write-Info "进程 $processId 不存在，清理 PID 文件"
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    exit 0
}

if ($DryRun) {
    Write-Info "DryRun: 将停止进程 $processId ($($process.ProcessName))，并删除 PID 文件 $PidFile"
    exit 0
}

Write-Info "停止进程 $processId ($($process.ProcessName))"
try {
    if ($Force) {
        Stop-Process -Id $processId -Force
    }
    else {
        Stop-Process -Id $processId
    }
}
catch {
    Write-Info "停止失败: $($_.Exception.Message)"
    exit 1
}

$deadline = (Get-Date).AddSeconds([Math]::Max(1, $WaitSeconds))
while ((Get-Date) -lt $deadline) {
    if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 200
}

if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
    Write-Info "进程未在 $WaitSeconds 秒内退出，可重试加 -Force"
    exit 2
}

if (Test-Path $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

Write-Info "已停止"
exit 0
