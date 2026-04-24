[CmdletBinding()]
param(
    [string]$ReleaseRoot = ('release\HotCollector-Upgrade-' + (Get-Date -Format 'yyyyMMdd-HHmmss')),
    [string]$DistRoot = 'dist\HotCollectorLauncher',
    [switch]$SkipBuild,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$BuildScript = Join-Path $PSScriptRoot 'build_package.ps1'
$PrepareScript = Join-Path $PSScriptRoot 'prepare_upgrade_release.ps1'
$ReleaseDir = Join-Path $ProjectRoot $ReleaseRoot
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
        throw '未找到 tar.exe，无法生成升级压缩包。请确认当前 Windows 环境可用 tar.exe。'
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

if (-not $SkipBuild) {
    Invoke-Step -FilePath 'powershell.exe' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $BuildScript) -DisplayCommand 'powershell.exe -ExecutionPolicy Bypass -File scripts\build_package.ps1'
}

Invoke-Step -FilePath 'powershell.exe' -Arguments @('-ExecutionPolicy', 'Bypass', '-File', $PrepareScript, '-ReleaseRoot', $ReleaseRoot, '-DistRoot', $DistRoot) -DisplayCommand "powershell.exe -ExecutionPolicy Bypass -File scripts\prepare_upgrade_release.ps1 -ReleaseRoot $ReleaseRoot -DistRoot $DistRoot"

New-ReleaseArchive -SourceDir $ReleaseDir -DestinationZip $ZipPath

# Phase 4 / REQ-SEC-020: 升级包同样附 SHA256 校验。
if (-not $DryRun) {
    $sumsPath = "$ZipPath.sha256"
    $hash = Get-FileHash -Path $ZipPath -Algorithm SHA256
    $line = "{0}  {1}" -f $hash.Hash.ToLower(), (Split-Path -Leaf $ZipPath)
    Set-Content -Path $sumsPath -Value $line -Encoding ASCII
    Write-Host "生成校验文件: $sumsPath"
}
