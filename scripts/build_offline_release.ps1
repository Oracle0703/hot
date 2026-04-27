[CmdletBinding()]
param(
    [string]$ReleaseRoot = ('release\HotCollector-Offline-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),
    [string]$DistRoot = 'dist\HotCollectorLauncher',
    [string]$DesktopShellDistRoot = 'build\HotCollectorDesktopShell',
    [string]$PlaywrightBrowsersPath = '',
    [string]$VcRedistPath = '',
    [string]$VcRedistUrl = 'https://aka.ms/vs/17/release/vc_redist.x64.exe',
    [switch]$SkipBuild,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildScript = Join-Path $PSScriptRoot 'build_package.ps1'
$BuildDesktopShellScript = Join-Path $PSScriptRoot 'build_desktop_shell.ps1'
$PrepareScript = Join-Path $PSScriptRoot 'prepare_release.ps1'
$PackagingDir = Join-Path $ProjectRoot 'packaging'
$PrereqCacheDir = Join-Path $PackagingDir 'prerequisites'
$ReleaseDir = Join-Path $ProjectRoot $ReleaseRoot
$ReleasePrereqDir = Join-Path $ReleaseDir 'prerequisites'
$ZipPath = "$ReleaseDir.zip"

function Invoke-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$DisplayCommand
    )

    Write-Host $DisplayCommand
    if (-not $DryRun) {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "命令执行失败: $DisplayCommand"
        }
    }
}

function New-ReleaseArchive {
    param(
        [string]$SourceDir,
        [string]$DestinationZip
    )

    $tarCommand = Get-Command 'tar.exe' -ErrorAction SilentlyContinue
    if (-not $tarCommand) {
        throw '未找到 tar.exe，无法生成离线发布压缩包。请确认当前 Windows 环境可用 tar.exe。'
    }

    $sourceParent = Split-Path -Parent $SourceDir
    $sourceLeaf = Split-Path -Leaf $SourceDir
    $displayCommand = "tar.exe -a -cf $DestinationZip -C $sourceParent $sourceLeaf"

    Write-Host "生成压缩包: $DestinationZip"
    Write-Host $displayCommand

    if ($DryRun) {
        return
    }

    if (Test-Path $DestinationZip) {
        Remove-Item -Path $DestinationZip -Force
    }

    Push-Location $sourceParent
    try {
        & $tarCommand.Source '-a' '-cf' $DestinationZip $sourceLeaf
        if ($LASTEXITCODE -ne 0) {
            throw "压缩包生成失败: $displayCommand"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not $PlaywrightBrowsersPath) {
    $PlaywrightBrowsersPath = Join-Path $ProjectRoot 'playwright-browsers'
}

if ($DryRun -or (-not $SkipBuild)) {
    Invoke-Step -FilePath 'powershell.exe' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $BuildDesktopShellScript, '-OutputRoot', $DesktopShellDistRoot) -DisplayCommand "powershell.exe -ExecutionPolicy Bypass -File scripts\build_desktop_shell.ps1 -OutputRoot $DesktopShellDistRoot"
}

if (-not $SkipBuild) {
    Invoke-Step -FilePath 'powershell.exe' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $BuildScript) -DisplayCommand 'powershell.exe -ExecutionPolicy Bypass -File scripts\build_package.ps1'
}

Invoke-Step -FilePath 'powershell.exe' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $PrepareScript, '-ReleaseRoot', $ReleaseRoot, '-DistRoot', $DistRoot, '-DesktopShellDistRoot', $DesktopShellDistRoot, '-PlaywrightBrowsersPath', $PlaywrightBrowsersPath) -DisplayCommand "powershell.exe -ExecutionPolicy Bypass -File scripts\prepare_release.ps1 -ReleaseRoot $ReleaseRoot -DistRoot $DistRoot -DesktopShellDistRoot $DesktopShellDistRoot -PlaywrightBrowsersPath $PlaywrightBrowsersPath"

$resolvedVcRedist = $VcRedistPath
if (-not $resolvedVcRedist) {
    $resolvedVcRedist = Join-Path $PrereqCacheDir 'VC_redist.x64.exe'
}

Write-Host "准备运行库文件: $resolvedVcRedist"
if (-not $DryRun) {
    New-Item -ItemType Directory -Force $PrereqCacheDir | Out-Null
    New-Item -ItemType Directory -Force $ReleasePrereqDir | Out-Null

    if (-not (Test-Path $resolvedVcRedist)) {
        Write-Host "下载 VC++ 运行库: $VcRedistUrl"
        Invoke-WebRequest -Uri $VcRedistUrl -OutFile $resolvedVcRedist
    }

    Copy-Item -Path $resolvedVcRedist -Destination (Join-Path $ReleasePrereqDir 'VC_redist.x64.exe') -Force
}

New-ReleaseArchive -SourceDir $ReleaseDir -DestinationZip $ZipPath

# Phase 4 / REQ-SEC-020: 生成 SHA256SUMS.txt,运维侧凭此校验包完整性。
if (-not $DryRun) {
    $sumsPath = "$ZipPath.sha256"
    $hash = Get-FileHash -Path $ZipPath -Algorithm SHA256
    $line = "{0}  {1}" -f $hash.Hash.ToLower(), (Split-Path -Leaf $ZipPath)
    Set-Content -Path $sumsPath -Value $line -Encoding ASCII
    Write-Host "生成校验文件: $sumsPath"
}
