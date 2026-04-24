[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$DatabasePath,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $DatabasePath) {
    $DatabasePath = Join-Path $ProjectRoot "data\hot_topics.db"
}

function Write-Info {
    param([string]$Message)
    Write-Host "[restore] $Message"
}

if (-not (Test-Path $File)) {
    Write-Info "备份文件不存在: $File"
    exit 1
}

$pidFile = Join-Path $ProjectRoot "data\launcher.pid"
if (Test-Path $pidFile) {
    Write-Info "检测到 PID 文件，请先执行 scripts\stop.ps1 停止服务后再恢复"
    exit 2
}

Write-Info "源备份: $File"
Write-Info "目标数据库: $DatabasePath"

if ($DryRun) {
    Write-Info "DryRun: 将把备份文件复制为目标数据库（覆盖）"
    exit 0
}

$dataDir = Split-Path -Parent $DatabasePath
if (-not (Test-Path $dataDir)) {
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null
}

if (Test-Path $DatabasePath) {
    $rollback = "$DatabasePath.before-restore-$((Get-Date).ToString('yyyyMMdd-HHmmss'))"
    Copy-Item -LiteralPath $DatabasePath -Destination $rollback -Force
    Write-Info "现有数据库已备份至: $rollback"
}

Copy-Item -LiteralPath $File -Destination $DatabasePath -Force
Write-Info "恢复完成。请重新启动系统验证。"
exit 0
