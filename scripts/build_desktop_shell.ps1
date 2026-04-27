[CmdletBinding()]
param(
    [string]$SourceRoot = 'desktop-shell\electron',
    [string]$OutputRoot = 'build\HotCollectorDesktopShell',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$SourceDir = Join-Path $ProjectRoot $SourceRoot
$OutputDir = Join-Path $ProjectRoot $OutputRoot
$RuntimeDir = Join-Path $OutputDir 'runtime'
$AppDir = Join-Path $OutputDir 'app'
$AssetsSourceDir = Join-Path $SourceDir 'assets'
$AssetsOutputDir = Join-Path $AppDir 'assets'
$LaunchBat = Join-Path $OutputDir 'launch-desktop-shell.bat'
$ElectronRuntimeSource = Join-Path $SourceDir 'node_modules\electron\dist'

function Invoke-Message {
    param([string]$Text)
    Write-Host $Text
}

function Invoke-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$DisplayCommand,
        [string]$WorkingDirectory = $ProjectRoot
    )

    Write-Host $DisplayCommand
    if (-not $DryRun) {
        Push-Location $WorkingDirectory
        try {
            & $FilePath @Arguments
            if ($LASTEXITCODE -ne 0) {
                throw "命令执行失败: $DisplayCommand"
            }
        }
        finally {
            Pop-Location
        }
    }
}

function New-FileContent {
    param(
        [string]$Path,
        [string]$Content
    )

    if (-not $DryRun) {
        Set-Content -Path $Path -Value $Content -Encoding ASCII
    }
}

Invoke-Message "准备 Electron 桌面壳: $SourceDir"
Invoke-Message "目标输出目录: $OutputDir"

if (-not (Test-Path $SourceDir)) {
    throw "未找到桌面壳源码目录: $SourceDir"
}

Invoke-Step -FilePath 'npm.cmd' -Arguments @('install', '--no-fund', '--no-audit', '--package-lock=false') -DisplayCommand 'npm install --no-fund --no-audit --package-lock=false' -WorkingDirectory $SourceDir

Invoke-Message "复制 Electron 运行时: $ElectronRuntimeSource -> $RuntimeDir"
Invoke-Message "Electron 主程序: $RuntimeDir\\electron.exe"
Invoke-Message "复制桌面壳应用文件: $SourceDir -> $AppDir"
Invoke-Message "复制托盘资源: $AssetsSourceDir\\tray.png -> $AssetsOutputDir\\tray.png"
Invoke-Message "写入桌面壳启动脚本: $LaunchBat"

$launchContent = @"
@echo off
cd /d %~dp0
set "HOT_DESKTOP_RUNTIME_ROOT=%~dp0.."
"%~dp0runtime\electron.exe" "%~dp0app"
"@

if (-not $DryRun) {
    if (-not (Test-Path $ElectronRuntimeSource)) {
        throw "未找到 Electron 运行时目录: $ElectronRuntimeSource"
    }

    if (Test-Path $OutputDir) {
        Remove-Item -Path $OutputDir -Recurse -Force
    }

    New-Item -ItemType Directory -Force $OutputDir, $RuntimeDir, $AppDir, $AssetsOutputDir | Out-Null
    Copy-Item -Path (Join-Path $ElectronRuntimeSource '*') -Destination $RuntimeDir -Recurse -Force
    Copy-Item -Path (Join-Path $SourceDir 'package.json') -Destination (Join-Path $AppDir 'package.json') -Force
    Copy-Item -Path (Join-Path $SourceDir 'main.js') -Destination (Join-Path $AppDir 'main.js') -Force
    Copy-Item -Path (Join-Path $SourceDir 'shell-state.js') -Destination (Join-Path $AppDir 'shell-state.js') -Force
    if (Test-Path $AssetsSourceDir) {
        Copy-Item -Path (Join-Path $AssetsSourceDir '*') -Destination $AssetsOutputDir -Recurse -Force
    }
}

New-FileContent -Path $LaunchBat -Content $launchContent
