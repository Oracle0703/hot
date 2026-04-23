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
            FilePath = $pythonCommand.Source
            PrefixArgs = @()
            Display = $pythonCommand.Source
        }
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        return @{
            FilePath = $pyCommand.Source
            PrefixArgs = @("-3")
            Display = "$($pyCommand.Source) -3"
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
    } finally {
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
        } finally {
            $env:PYINSTALLER_CONFIG_DIR = $previousConfigDir
        }
    }
}

$pythonCandidates = @()
if (Test-Path $VenvPython) {
    $pythonCandidates += @{
        FilePath = $VenvPython
        PrefixArgs = @()
        Display = ".venv\Scripts\python.exe"
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
