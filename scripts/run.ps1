[CmdletBinding()]
param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000,
    [switch]$NoReload,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RuntimeEnvFile = Join-Path $ProjectRoot "data\app.env"

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

    throw "未找到可用的 Python，请先运行 scripts/bootstrap.ps1 初始化环境。"
}

function Import-AppEnvFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content -Path $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith('#') -or -not $line.Contains('=')) {
            return
        }
        $parts = $line.Split('=', 2)
        $name = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($name) {
            [System.Environment]::SetEnvironmentVariable($name, $value, 'Process')
        }
    }
}

if (Test-Path $VenvPython) {
    $pythonRuntime = @{
        FilePath = $VenvPython
        PrefixArgs = @()
        Display = ".venv\Scripts\python.exe"
    }
} else {
    $pythonRuntime = Resolve-SystemPython
}

Import-AppEnvFile -Path $RuntimeEnvFile

$args = @($pythonRuntime.PrefixArgs + @("-m", "uvicorn", "app.main:app"))
if (-not $NoReload) {
    $args += "--reload"
}
$args += @("--host", $BindHost, "--port", $Port.ToString())

$displayCommand = "$($pythonRuntime.Display) " + (($args | Where-Object { $_ -notin $pythonRuntime.PrefixArgs }) -join " ")
Write-Host $displayCommand
if (Test-Path $RuntimeEnvFile) {
    Write-Host "已加载配置文件: data\app.env"
}

if (-not $DryRun) {
    Set-Location $ProjectRoot
    & $pythonRuntime.FilePath @args
    if ($LASTEXITCODE -ne 0) {
        throw "启动失败: $displayCommand"
    }
}
