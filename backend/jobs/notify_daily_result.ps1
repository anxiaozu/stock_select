# 根据 last_run_status.txt / exit code 通知日更结果。
# 可由计划任务在 run_daily.ps1 之后单独调用，也可手动跑。
#
# 用法:
#   powershell -File jobs\notify_daily_result.ps1
#   powershell -File jobs\notify_daily_result.ps1 -ExitCode 1
#
# 若设置了 STOCK_ALERT_WEBHOOK，失败时 POST {"text":"..."}；否则只打印 ALERT。

param(
    [int]$ExitCode = -1
)

$ErrorActionPreference = "Continue"
$Backend = "E:\stock_new\stock\backend"
$LogDir = Join-Path $Backend "logs"
$StatusFile = Join-Path $LogDir "last_run_status.txt"

$statusText = ""
if (Test-Path $StatusFile) {
    $statusText = Get-Content -Path $StatusFile -Raw -ErrorAction SilentlyContinue
}

if ($ExitCode -lt 0) {
    if ($statusText -match "exit_code=(\d+)") {
        $ExitCode = [int]$Matches[1]
    } else {
        $ExitCode = 0
    }
}

$DateTag = Get-Date -Format "yyyyMMdd"
if ($statusText -match "date=(\d{8})") {
    $DateTag = $Matches[1]
}

$msg = if ($ExitCode -eq 0) {
    "StockDailyJob OK date=$DateTag`n$statusText"
} else {
    "StockDailyJob FAILED exit=$ExitCode date=$DateTag`n$statusText"
}

Write-Output $msg

if ($ExitCode -ne 0) {
    $webhook = $env:STOCK_ALERT_WEBHOOK
    if ([string]::IsNullOrEmpty($webhook)) {
        Write-Output "ALERT"
        Write-Output $msg
    } else {
        try {
            $payload = @{ text = $msg } | ConvertTo-Json -Compress
            Invoke-RestMethod -Uri $webhook -Method Post -Body $payload -ContentType "application/json; charset=utf-8" -TimeoutSec 10 | Out-Null
            Write-Output "webhook posted"
        } catch {
            Write-Output "ALERT webhook failed: $($_.Exception.Message)"
            Write-Output $msg
        }
    }
}

exit $ExitCode
