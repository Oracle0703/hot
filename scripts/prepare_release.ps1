[CmdletBinding()]
param(
    [string]$ReleaseRoot = 'release\HotCollector',
    [string]$DistRoot = 'dist\HotCollectorLauncher',
    [string]$PlaywrightBrowsersPath = '',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $ProjectRoot $ReleaseRoot
$DistDir = Join-Path $ProjectRoot $DistRoot
$DataDir = Join-Path $ReleaseDir 'data'
$LogsDir = Join-Path $ReleaseDir 'logs'
$ReportsDir = Join-Path $ReleaseDir 'outputs\reports'
$SharedReportsDir = Join-Path $ReleaseDir 'outputs\shared-reports'
$BrowsersDir = Join-Path $ReleaseDir 'playwright-browsers'
$PrerequisitesDir = Join-Path $ReleaseDir 'prerequisites'
$ReadmeSource = Join-Path $ProjectRoot 'README-运营版.txt'
$LauncherExe = Join-Path $ReleaseDir 'HotCollectorLauncher.exe'
$StartBat = Join-Path $ReleaseDir '启动系统.bat'
$StopBat = Join-Path $ReleaseDir '停止系统.bat'
$InstallBat = Join-Path $ReleaseDir '安装依赖.bat'
$AppEnvFile = Join-Path $DataDir 'app.env'

function Invoke-Message {
    param([string]$Text)
    Write-Host $Text
}

function New-FileContent {
    param(
        [string]$Path,
        [string]$Content
    )
    if (-not $DryRun) {
        Set-Content -Path $Path -Value $Content -Encoding UTF8
    }
}

if (-not $PlaywrightBrowsersPath) {
    $PlaywrightBrowsersPath = Join-Path $ProjectRoot 'playwright-browsers'
}

Invoke-Message "准备发布目录: $ReleaseDir"
Invoke-Message "复制运行时文件: $DistDir -> $ReleaseDir"
Invoke-Message "目标启动器: $LauncherExe"
Invoke-Message "浏览器目录来源: $PlaywrightBrowsersPath"

if (-not $DryRun) {
    if (-not (Test-Path $DistDir)) {
        throw "未找到打包输出目录: $DistDir，请先执行 scripts/build_package.ps1"
    }

    if (Test-Path $ReleaseDir) {
        Remove-Item -Path $ReleaseDir -Recurse -Force
    }

    New-Item -ItemType Directory -Force $ReleaseDir | Out-Null
    Copy-Item -Path (Join-Path $DistDir '*') -Destination $ReleaseDir -Recurse -Force
    New-Item -ItemType Directory -Force $DataDir, $LogsDir, $ReportsDir, $SharedReportsDir, $BrowsersDir, $PrerequisitesDir | Out-Null

    if (Test-Path $ReadmeSource) {
        Copy-Item -Path $ReadmeSource -Destination (Join-Path $ReleaseDir 'README-运营版.txt') -Force
    }

    if ($PlaywrightBrowsersPath -and (Test-Path $PlaywrightBrowsersPath)) {
        Copy-Item -Path (Join-Path $PlaywrightBrowsersPath '*') -Destination $BrowsersDir -Recurse -Force
    }
}

$startContent = "@echo off`r`ncd /d %~dp0`r`nHotCollectorLauncher.exe`r`n"
$stopContent = @'
@echo off
powershell -ExecutionPolicy Bypass -Command "$pidFile = Join-Path '%~dp0data' 'launcher.pid'; if (Test-Path $pidFile) { $targetPid = Get-Content $pidFile | Select-Object -First 1; if ($targetPid) { Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue }; Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue }"
'@
$installContent = @"
@echo off
cd /d %~dp0
if exist prerequisites\VC_redist.x64.exe (
  echo [1/1] 正在安装 Microsoft Visual C++ x64 运行库...
  powershell -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~dp0prerequisites\VC_redist.x64.exe' -ArgumentList '/install /passive /norestart' -Verb RunAs -Wait"
) else (
  echo 未找到 prerequisites\VC_redist.x64.exe，已跳过运行库安装。
)
echo 依赖安装步骤结束。
pause
"@
$appEnvContent = @"
APP_NAME=热点信息采集系统
APP_ENV=production
APP_DEBUG=false
ENABLE_SCHEDULER=true
SCHEDULER_POLL_SECONDS=30
REPORT_SHARE_DIR=outputs\shared-reports
ENABLE_DINGTALK_NOTIFIER=false
DINGTALK_WEBHOOK=
DINGTALK_SECRET=
DINGTALK_KEYWORD=热点报告
X_AUTH_TOKEN=
X_CT0=
BILIBILI_COOKIE=
# 如需切换 MySQL，可改为 mysql+pymysql://user:password@127.0.0.1:3306/hot_topic
# DATABASE_URL=sqlite:///./data/hot_topics.db
# REPORTS_ROOT=outputs/reports
"@

Invoke-Message "写入启动脚本: $StartBat"
Invoke-Message "写入停止脚本: $StopBat"
Invoke-Message "写入依赖安装脚本: $InstallBat"
Invoke-Message "写入默认配置: $AppEnvFile"
New-FileContent -Path $StartBat -Content $startContent
New-FileContent -Path $StopBat -Content $stopContent
New-FileContent -Path $InstallBat -Content $installContent
New-FileContent -Path $AppEnvFile -Content $appEnvContent




