[CmdletBinding()]
param(
    [string]$ReleaseRoot = 'release\HotCollector-Upgrade',
    [string]$DistRoot = 'dist\HotCollectorLauncher',
    [string]$DesktopShellDistRoot = 'build\HotCollectorDesktopShell',
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReleaseDir = Join-Path $ProjectRoot $ReleaseRoot
$DistDir = Join-Path $ProjectRoot $DistRoot
$DesktopShellDistDir = Join-Path $ProjectRoot $DesktopShellDistRoot
$ReadmeSource = Join-Path $ProjectRoot 'README-运营版.txt'
$DesktopShellDir = Join-Path $ReleaseDir 'desktop-shell'
$LauncherExe = Join-Path $ReleaseDir 'HotCollectorLauncher.exe'
$StartBat = Join-Path $ReleaseDir '启动系统.bat'
$StopBat = Join-Path $ReleaseDir '停止系统.bat'
$StatusBat = Join-Path $ReleaseDir '查看状态.bat'
$DesktopBat = Join-Path $ReleaseDir '打开桌面版.bat'
$UpgradeReadme = Join-Path $ReleaseDir '升级说明.txt'

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

function Copy-ProgramFiles {
    param(
        [string]$SourceDir,
        [string]$DestinationDir
    )

    $maxAttempts = 5
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        $robocopyCommand = Get-Command 'robocopy.exe' -ErrorAction SilentlyContinue
        if ($null -ne $robocopyCommand) {
            & $robocopyCommand.Source $SourceDir $DestinationDir /E /R:2 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
            if ($LASTEXITCODE -lt 8) {
                return
            }
            if ($attempt -lt $maxAttempts) {
                Start-Sleep -Seconds 2
                continue
            }
            throw "robocopy 复制程序文件失败，退出码: $LASTEXITCODE"
        }

        try {
            Copy-Item -Path (Join-Path $SourceDir '*') -Destination $DestinationDir -Recurse -Force
            return
        } catch {
            if ($attempt -ge $maxAttempts) {
                throw
            }
            Start-Sleep -Seconds 2
        }
    }
}

Invoke-Message "准备升级包目录: $ReleaseDir"
Invoke-Message "复制程序文件: $DistDir -> $ReleaseDir"
Invoke-Message "复制桌面壳文件: $DesktopShellDistDir -> $DesktopShellDir"
Invoke-Message "目标启动器: $LauncherExe"
Invoke-Message "说明: 此升级包仅覆盖程序文件，不包含 data/logs/outputs/playwright-browsers"

if (-not $DryRun) {
    if (-not (Test-Path $DistDir)) {
        throw "未找到打包输出目录: $DistDir，请先执行 scripts/build_package.ps1"
    }
    if (-not (Test-Path $DesktopShellDistDir)) {
        throw "未找到桌面壳输出目录: $DesktopShellDistDir，请先执行 scripts/build_desktop_shell.ps1"
    }

    if (Test-Path $ReleaseDir) {
        Remove-Item -Path $ReleaseDir -Recurse -Force
    }

    New-Item -ItemType Directory -Force $ReleaseDir | Out-Null
    Copy-ProgramFiles -SourceDir $DistDir -DestinationDir $ReleaseDir
    Copy-ProgramFiles -SourceDir $DesktopShellDistDir -DestinationDir $DesktopShellDir

    if (Test-Path $ReadmeSource) {
        Copy-Item -Path $ReadmeSource -Destination (Join-Path $ReleaseDir 'README-运营版.txt') -Force
    }
}

$startContent = "@echo off`r`ncd /d %~dp0`r`nHotCollectorLauncher.exe`r`n"
$desktopContent = "@echo off`r`ncd /d %~dp0`r`ncall desktop-shell\launch-desktop-shell.bat`r`n"
$stopContent = @'
@echo off
powershell -ExecutionPolicy Bypass -Command "$pidFile = Join-Path '%~dp0data' 'launcher.pid'; if (Test-Path $pidFile) { $targetPid = Get-Content $pidFile | Select-Object -First 1; if ($targetPid) { Stop-Process -Id $targetPid -Force -ErrorAction SilentlyContinue }; Remove-Item -Path $pidFile -Force -ErrorAction SilentlyContinue }"
'@
$statusContent = "@echo off`r`ncd /d %~dp0`r`nHotCollectorLauncher.exe --probe --print-json %*`r`n"
$upgradeReadmeContent = @"
固定目录覆盖升级说明
====================

1. 先双击“停止系统.bat”关闭旧版本
2. 将本升级包内的全部文件覆盖到现有安装目录
3. 不要删除原安装目录下的 data、logs、outputs、playwright-browsers
4. 覆盖完成后，双击“启动系统.bat”启动新版本

此升级包只包含程序文件，默认不会携带或覆盖你的运行配置与数据库。
"@

Invoke-Message "写入启动脚本: $StartBat"
Invoke-Message "写入停止脚本: $StopBat"
Invoke-Message "写入状态脚本: $StatusBat"
Invoke-Message "写入桌面版脚本: $DesktopBat"
Invoke-Message "写入升级说明: $UpgradeReadme"
New-FileContent -Path $StartBat -Content $startContent
New-FileContent -Path $StopBat -Content $stopContent
New-FileContent -Path $StatusBat -Content $statusContent
New-FileContent -Path $DesktopBat -Content $desktopContent
New-FileContent -Path $UpgradeReadme -Content $upgradeReadmeContent
