[CmdletBinding()]
param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 38080,
    [string]$RuntimeRoot = "",
    [switch]$PrintJson
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$LauncherExe = Join-Path $ProjectRoot "HotCollectorLauncher.exe"
$LauncherPy = Join-Path $ProjectRoot "launcher.py"
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

function Resolve-SystemPython {
    $pythonCommand = Get-Command python -ErrorAction SilentlyContinue
    if ($null -ne $pythonCommand) {
        return @{
            FilePath = $pythonCommand.Source
            PrefixArgs = @()
        }
    }

    $pyCommand = Get-Command py -ErrorAction SilentlyContinue
    if ($null -ne $pyCommand) {
        return @{
            FilePath = $pyCommand.Source
            PrefixArgs = @("-3")
        }
    }

    throw "未找到可用的 Python 运行时。"
}

function Resolve-LauncherInvocation {
    $launcherArgs = @("--probe", "--host", $BindHost, "--port", $Port.ToString())
    if ($RuntimeRoot) {
        $launcherArgs += @("--runtime-root", $RuntimeRoot)
    }
    if ($PrintJson) {
        $launcherArgs += "--print-json"
    }

    if (Test-Path $LauncherExe) {
        return @{
            FilePath = $LauncherExe
            Arguments = $launcherArgs
        }
    }

    if (-not (Test-Path $LauncherPy)) {
        throw "未找到 launcher.py 或 HotCollectorLauncher.exe。"
    }

    if (Test-Path $VenvPython) {
        $pythonRuntime = @{
            FilePath = $VenvPython
            PrefixArgs = @()
        }
    }
    else {
        $pythonRuntime = Resolve-SystemPython
    }

    return @{
        FilePath = $pythonRuntime.FilePath
        Arguments = @($pythonRuntime.PrefixArgs + @($LauncherPy) + $launcherArgs)
    }
}

$invocation = Resolve-LauncherInvocation
& $invocation.FilePath @($invocation.Arguments)
exit $LASTEXITCODE
