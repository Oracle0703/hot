[CmdletBinding()]
param(
    [string]$DatabasePath,
    [string]$BackupDir,
    [int]$Keep = 14,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot

if (-not $DatabasePath) {
    $DatabasePath = Join-Path $ProjectRoot "data\hot_topics.db"
}
if (-not $BackupDir) {
    $BackupDir = Join-Path $ProjectRoot "data\backups"
}

function Write-Info {
    param([string]$Message)
    Write-Host "[backup] $Message"
}

if (-not (Test-Path $DatabasePath)) {
    Write-Info "数据库不存在，跳过: $DatabasePath"
    exit 0
}

$timestamp = (Get-Date).ToString("yyyyMMdd-HHmmss")
$baseName = [System.IO.Path]::GetFileNameWithoutExtension($DatabasePath)
$ext = [System.IO.Path]::GetExtension($DatabasePath)
$targetName = "$baseName-$timestamp$ext"
$targetPath = Join-Path $BackupDir $targetName

Write-Info "源: $DatabasePath"
Write-Info "目标: $targetPath"

if ($DryRun) {
    Write-Info "DryRun: 将创建备份目录、复制数据库、保留最近 $Keep 份"
    exit 0
}

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
}

Copy-Item -LiteralPath $DatabasePath -Destination $targetPath -Force
Write-Info "已生成备份: $targetPath"

if ($Keep -gt 0) {
    $existing = Get-ChildItem -LiteralPath $BackupDir -File -Filter "$baseName-*$ext" |
    Sort-Object LastWriteTime -Descending
    if ($existing.Count -gt $Keep) {
        $toRemove = $existing | Select-Object -Skip $Keep
        foreach ($item in $toRemove) {
            Write-Info "清理旧备份: $($item.Name)"
            Remove-Item -LiteralPath $item.FullName -Force
        }
    }
}

exit 0
