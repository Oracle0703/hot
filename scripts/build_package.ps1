[CmdletBinding()]
param(
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SpecFile = Join-Path $ProjectRoot "hot_collector.spec"
$PyInstallerConfigDir = Join-Path $ProjectRoot ".pyinstaller"

function Resolve-SystemPython {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        return @{
            FilePath   = $pythonCommand.Source
            PrefixArgs = @()
            Display    = $pythonCommand.Source
        }
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        return @{
            FilePath   = $pyCommand.Source
            PrefixArgs = @("-3")
            Display    = "$($pyCommand.Source) -3"
        }
    }

    throw "未找到可用的 Python，请先安装 Python 3。"
}

function Test-PythonModule {
    param(
        [string]$FilePath,
        [string[]]$PrefixArgs,
        [string]$ModuleName
    )

    $previousErrorActionPreference = $ErrorActionPreference
    $global:ErrorActionPreference = "Continue"
    try {
        & $FilePath @PrefixArgs -c "import $ModuleName" 2>$null | Out-Null
        return $LASTEXITCODE -eq 0
    }
    finally {
        $global:ErrorActionPreference = $previousErrorActionPreference
    }
}

function Invoke-Step {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$DisplayCommand
    )

    Write-Host $DisplayCommand
    if (-not $DryRun) {
        $previousConfigDir = $env:PYINSTALLER_CONFIG_DIR
        try {
            New-Item -ItemType Directory -Force $PyInstallerConfigDir | Out-Null
            $env:PYINSTALLER_CONFIG_DIR = $PyInstallerConfigDir
            & $FilePath @Arguments
            if ($LASTEXITCODE -ne 0) {
                throw "命令执行失败: $DisplayCommand"
            }
        }
        finally {
            $env:PYINSTALLER_CONFIG_DIR = $previousConfigDir
        }
    }
}

$pythonCandidates = @()
if (Test-Path $VenvPython) {
    $pythonCandidates += @{
        FilePath   = $VenvPython
        PrefixArgs = @()
        Display    = ".venv\Scripts\python.exe"
    }
}
$pythonCandidates += Resolve-SystemPython

$pythonRuntime = $null
foreach ($candidate in $pythonCandidates) {
    if (Test-PythonModule -FilePath $candidate.FilePath -PrefixArgs $candidate.PrefixArgs -ModuleName "PyInstaller") {
        $pythonRuntime = $candidate
        break
    }
}

if ($null -eq $pythonRuntime) {
    throw "未找到带 PyInstaller 的 Python 解释器，请先安装 pyinstaller。"
}

$arguments = @($pythonRuntime.PrefixArgs + @("-m", "PyInstaller", $SpecFile, "--noconfirm", "--clean"))
$display = "$($pythonRuntime.Display) -m PyInstaller hot_collector.spec --noconfirm --clean"
Invoke-Step -FilePath $pythonRuntime.FilePath -Arguments $arguments -DisplayCommand $display

# Phase 1 / REQ-SYS-001: 注入 VERSION 文件 (commit + 构建时间 + channel)
$versionTarget = Join-Path $ProjectRoot 'dist\HotCollectorLauncher\VERSION'
$existingVersion = Join-Path $ProjectRoot 'VERSION'
if (Test-Path $existingVersion) {
    $declaredVersion = (Get-Content $existingVersion | Where-Object { $_ -like 'version=*' } | Select-Object -First 1) -replace '^version=', ''
}
else {
    $declaredVersion = '1.0.0-dev'
}
if (-not $declaredVersion) { $declaredVersion = '1.0.0-dev' }

try {
    $commit = (& git -C $ProjectRoot rev-parse --short HEAD 2>$null).Trim()
}
catch {
    $commit = 'unknown'
}
if (-not $commit) { $commit = 'unknown' }

$builtAt = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
$channel = if ($env:HOT_RELEASE_CHANNEL) { $env:HOT_RELEASE_CHANNEL } else { 'stable' }

$lines = @(
    "version=$declaredVersion",
    "commit=$commit",
    "built_at=$builtAt",
    "channel=$channel"
)
if (Test-Path (Split-Path -Parent $versionTarget)) {
    Set-Content -Path $versionTarget -Value $lines -Encoding ASCII
    Write-Host "已注入 VERSION: $versionTarget"
}
