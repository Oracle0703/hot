[CmdletBinding()]
param(
    [switch]$InstallPlaywright,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$RequirementsFile = Join-Path $ProjectRoot "requirements.txt"
$DataDir = Join-Path $ProjectRoot "data"
$ReportsDir = Join-Path $ProjectRoot "outputs\reports"
$AppEnvTemplate = Join-Path $ProjectRoot ".env.example"
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

    throw "未找到可用的 Python，请先安装 Python 3。"
}

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

New-Item -ItemType Directory -Force $DataDir | Out-Null
New-Item -ItemType Directory -Force $ReportsDir | Out-Null
Write-Host "项目目录: $ProjectRoot"
Write-Host "数据目录已确认: $DataDir"
Write-Host "报告目录已确认: $ReportsDir"
if (-not (Test-Path $RuntimeEnvFile) -and (Test-Path $AppEnvTemplate)) {
    if ($DryRun) {
        Write-Host "将创建运行配置模板: $RuntimeEnvFile"
    } else {
        Copy-Item $AppEnvTemplate $RuntimeEnvFile
        Write-Host "已创建运行配置模板: $RuntimeEnvFile"
    }
}

if (-not (Test-Path $VenvPython)) {
    $systemPython = Resolve-SystemPython
    $createVenvArgs = @($systemPython.PrefixArgs + @("-m", "venv", (Join-Path $ProjectRoot ".venv")))
    Invoke-Step -FilePath $systemPython.FilePath -Arguments $createVenvArgs -DisplayCommand "$($systemPython.Display) -m venv .venv"
}

$resolvedPython = if (Test-Path $VenvPython) { $VenvPython } else { $null }
if ($null -eq $resolvedPython) {
    $resolvedPython = $VenvPython
}

Invoke-Step -FilePath $resolvedPython -Arguments @("-m", "pip", "install", "-r", $RequirementsFile) -DisplayCommand ".venv\Scripts\python.exe -m pip install -r requirements.txt"

if ($InstallPlaywright) {
    Invoke-Step -FilePath $resolvedPython -Arguments @("-m", "playwright", "install", "chromium") -DisplayCommand ".venv\Scripts\python.exe -m playwright install chromium"
}
