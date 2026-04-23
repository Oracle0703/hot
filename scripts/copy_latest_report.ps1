[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Destination,
    [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$ReportRoot = Join-Path $ProjectRoot 'outputs\reports\global'
$MarkdownPath = Join-Path $ReportRoot 'hot-report.md'
$DocxPath = Join-Path $ReportRoot 'hot-report.docx'
$DestinationRoot = (Resolve-Path -LiteralPath (Split-Path -Path $Destination -Parent) -ErrorAction SilentlyContinue)

if (-not (Test-Path $MarkdownPath)) {
    throw "未找到 Markdown 报告: $MarkdownPath"
}
if (-not (Test-Path $DocxPath)) {
    throw "未找到 DOCX 报告: $DocxPath"
}

$TargetDir = $Destination
if (-not [System.IO.Path]::IsPathRooted($TargetDir)) {
    $TargetDir = Join-Path $ProjectRoot $TargetDir
}

Write-Host "复制报告到: $TargetDir"
Write-Host "- Markdown: $MarkdownPath"
Write-Host "- DOCX: $DocxPath"

if (-not $DryRun) {
    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    Copy-Item -Path $MarkdownPath -Destination (Join-Path $TargetDir 'hot-report.md') -Force
    Copy-Item -Path $DocxPath -Destination (Join-Path $TargetDir 'hot-report.docx') -Force
}
