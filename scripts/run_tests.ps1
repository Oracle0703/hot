# 一键回归脚本 (REQ-TEST-001)
# 用法:
#   .\scripts\run_tests.ps1            # 全量
#   .\scripts\run_tests.ps1 -Unit      # 仅 unit
#   .\scripts\run_tests.ps1 -Integration
#   .\scripts\run_tests.ps1 -E2E
[CmdletBinding()]
param(
    [switch]$Unit,
    [switch]$Integration,
    [switch]$E2E,
    [switch]$VerboseOutput
)

$ErrorActionPreference = 'Stop'
Set-Location -Path (Join-Path $PSScriptRoot '..')

$python = Join-Path -Path '.venv' -ChildPath 'Scripts\python.exe'
if (-not (Test-Path $python)) {
    throw "未找到虚拟环境 Python: $python,请先执行 scripts\bootstrap.ps1"
}

$paths = @()
if ($Unit) { $paths += 'tests/unit' }
if ($Integration) { $paths += 'tests/integration' }
if ($E2E) { $paths += 'tests/e2e' }
if ($paths.Count -eq 0) { $paths = @('tests') }

$pytestArgs = @('-m', 'pytest') + $paths
if (-not $VerboseOutput) { $pytestArgs += '-q' }

Write-Host "==> $python $($pytestArgs -join ' ')" -ForegroundColor Cyan
& $python @pytestArgs
exit $LASTEXITCODE
