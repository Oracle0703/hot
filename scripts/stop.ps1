[CmdletBinding()]
param(
    [int]$WaitSeconds = 15,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$PrintJson,
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 38080
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$PidFile = Join-Path $ProjectRoot "data\launcher.pid"

function Write-Info {
    param([string]$Message)
    Write-Host "[stop] $Message"
}

function Complete-Stop {
    param(
        [string]$Outcome,
        [string]$Message,
        [int]$ExitCode = 0,
        [Nullable[int]]$ProcessIdValue = $null,
        [string]$ProcessName = "",
        [Nullable[bool]]$ServiceRunning = $null,
        [bool]$RemovedPidFile = $false
    )

    if ($PrintJson) {
        $payload = [ordered]@{
            kind = "stop-script"
            outcome = $Outcome
            message = $Message
            pid = $ProcessIdValue
            process_name = $ProcessName
            pid_file = $PidFile
            pid_file_exists = (Test-Path $PidFile)
            removed_pid_file = $RemovedPidFile
            bind_host = $BindHost
            port = $Port
            service_running = $ServiceRunning
            dry_run = [bool]$DryRun
            force = [bool]$Force
            exit_code = $ExitCode
        }
        $payload | ConvertTo-Json -Compress | Write-Output
    }
    else {
        Write-Info $Message
    }
    exit $ExitCode
}

function Test-PortOpen {
    param(
        [string]$TargetHost,
        [int]$TargetPort
    )

    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($TargetHost, $TargetPort, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne(250)) {
            return $false
        }
        $client.EndConnect($async)
        return $true
    }
    catch {
        return $false
    }
    finally {
        if ($null -ne $client) {
            $client.Dispose()
        }
    }
}

if (-not (Test-Path $PidFile)) {
    Complete-Stop -Outcome "pid_file_missing" -Message "未发现 PID 文件: $PidFile" -ExitCode 0
}

$pidText = (Get-Content -LiteralPath $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1)
if ([string]::IsNullOrWhiteSpace($pidText)) {
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    Complete-Stop -Outcome "empty_pid_file_cleaned" -Message "PID 文件为空，直接清理: $PidFile" -ExitCode 0 -RemovedPidFile (-not $DryRun)
}

$processId = 0
if (-not [int]::TryParse($pidText.Trim(), [ref]$processId)) {
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    Complete-Stop -Outcome "invalid_pid_file_cleaned" -Message "PID 文件内容非法: $pidText，直接清理" -ExitCode 0 -RemovedPidFile (-not $DryRun)
}

$process = Get-Process -Id $processId -ErrorAction SilentlyContinue
if ($null -eq $process) {
    if (-not $DryRun) { Remove-Item -LiteralPath $PidFile -Force }
    Complete-Stop -Outcome "missing_process_pid_cleaned" -Message "进程 $processId 不存在，清理 PID 文件" -ExitCode 0 -ProcessIdValue $processId -RemovedPidFile (-not $DryRun)
}

$serviceRunning = Test-PortOpen -TargetHost $BindHost -TargetPort $Port
if (-not $serviceRunning) {
    if ($DryRun) {
        Complete-Stop -Outcome "stale_pid_detected" -Message "DryRun: 端口 $BindHost`:$Port 未监听，判定 PID 文件为陈旧状态，将清理 $PidFile" -ExitCode 0 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $false -RemovedPidFile $false
    }
    else {
        Remove-Item -LiteralPath $PidFile -Force
        Complete-Stop -Outcome "stale_pid_cleaned" -Message "端口 $BindHost`:$Port 未监听，判定 PID 文件为陈旧状态，清理 $PidFile" -ExitCode 0 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $false -RemovedPidFile $true
    }
}

if ($DryRun) {
    Complete-Stop -Outcome "stop_planned" -Message "DryRun: 将停止进程 $processId ($($process.ProcessName))，并删除 PID 文件 $PidFile" -ExitCode 0 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $true -RemovedPidFile $false
}

Write-Info "停止进程 $processId ($($process.ProcessName))"
try {
    if ($Force) {
        Stop-Process -Id $processId -Force
    }
    else {
        Stop-Process -Id $processId
    }
}
catch {
    Complete-Stop -Outcome "stop_failed" -Message "停止失败: $($_.Exception.Message)" -ExitCode 1 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $true -RemovedPidFile $false
}

$deadline = (Get-Date).AddSeconds([Math]::Max(1, $WaitSeconds))
while ((Get-Date) -lt $deadline) {
    if (-not (Get-Process -Id $processId -ErrorAction SilentlyContinue)) {
        break
    }
    Start-Sleep -Milliseconds 200
}

if (Get-Process -Id $processId -ErrorAction SilentlyContinue) {
    Complete-Stop -Outcome "stop_timeout" -Message "进程未在 $WaitSeconds 秒内退出，可重试加 -Force" -ExitCode 2 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $true -RemovedPidFile $false
}

if (Test-Path $PidFile) {
    Remove-Item -LiteralPath $PidFile -Force
}

Complete-Stop -Outcome "stopped" -Message "已停止" -ExitCode 0 -ProcessIdValue $processId -ProcessName $process.ProcessName -ServiceRunning $true -RemovedPidFile $true
