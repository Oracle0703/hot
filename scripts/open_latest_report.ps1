[CmdletBinding()]
param(
    [switch]$OpenDocx,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReportRoot = Join-Path $ProjectRoot 'outputs\reports\global'
$MarkdownPath = Join-Path $ReportRoot 'hot-report.md'
$DocxPath = Join-Path $ReportRoot 'hot-report.docx'

if (-not (Test-Path $ReportRoot)) {
    throw "未找到报告目录: $ReportRoot"
}

if ($OpenDocx) {
    if (-not (Test-Path $DocxPath)) {
        throw "未找到 DOCX 报告: $DocxPath"
    }
    Write-Host "打开报告文件: $DocxPath"
    if (-not $DryRun) {
        Start-Process $DocxPath
    }
    return
}

Write-Host "打开报告目录: $ReportRoot"
if (-not $DryRun) {
    Start-Process $ReportRoot
}
