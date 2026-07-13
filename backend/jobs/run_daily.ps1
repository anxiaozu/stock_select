# 每日选股任务(Windows)：抓行情 -> 算指标 -> 兜底回填 -> 买入/卖出 -> 健康监控。
# 由 Windows 任务计划在每个交易日 18:00 自动执行；也可手动运行。
# 日志: backend/logs/daily.YYYYMMDD.log
# 状态: backend/logs/last_run_status.txt

$ErrorActionPreference = "Continue"
$JobsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Split-Path -Parent $JobsDir

$env:PYTHONPATH = $Backend
$env:PYTHONUNBUFFERED = "1"
$env:PYTHONIOENCODING = "utf-8"

# MySQL：请用环境变量配置密码，勿把真实密码写进仓库。
if ([string]::IsNullOrEmpty($env:MYSQL_HOST)) { $env:MYSQL_HOST = "localhost" }
if ([string]::IsNullOrEmpty($env:MYSQL_PORT)) { $env:MYSQL_PORT = "3306" }
if ([string]::IsNullOrEmpty($env:MYSQL_USER)) { $env:MYSQL_USER = "root" }
if ([string]::IsNullOrEmpty($env:MYSQL_DB))   { $env:MYSQL_DB   = "stock_data" }
if ([string]::IsNullOrEmpty($env:MYSQL_PWD)) {
    Write-Host "ERROR: 请先设置环境变量 MYSQL_PWD 后再运行（勿把密码写入脚本）。"
    exit 1
}

Set-Location $Backend
$DateTag = Get-Date -Format "yyyyMMdd"
$LogDir = Join-Path $Backend "logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$Log = Join-Path $LogDir "daily.$DateTag.log"
$StatusFile = Join-Path $LogDir "last_run_status.txt"
$SpotSourceFile = Join-Path $LogDir "spot_source.$DateTag.txt"

function Write-Log($msg) {
    Add-Content -Path $Log -Value $msg
}

function Run-Step($name, $script) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Log "`n########## [$ts] $name ##########"
    & python $script *>> $Log
    $code = $LASTEXITCODE
    if ($null -eq $code) { $code = 0 }
    if ($code -ne 0) {
        Write-Log "########## FAILURE $name exit=$code ##########"
    } else {
        Write-Log "########## $name exit=$code ##########"
    }
    return $code
}

$startTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
Write-Log "`n==================== START $startTs ===================="

$anyFailed = $false
$failedSteps = @()

function Invoke-TrackedStep($name, $script) {
    $code = Run-Step $name $script
    if ($code -ne 0) {
        $script:anyFailed = $true
        $script:failedSteps += "$name(exit=$code)"
    }
    return $code
}

Invoke-TrackedStep "18h_daily_job(抓当日行情)"           "jobs\18h_daily_job.py"            | Out-Null
Invoke-TrackedStep "sector_fund_flow(板块资金流)"        "jobs\sector_fund_flow_daily_job.py" | Out-Null
Invoke-TrackedStep "enrich_tencent(补市盈率市值等)"      "jobs\enrich_fundamentals_tencent.py" | Out-Null
Invoke-TrackedStep "lhb_detail(龙虎榜席位明细)"          "jobs\lhb_detail_daily_job.py"      | Out-Null
Invoke-TrackedStep "guess_indicators_daily_job(算指标)"  "jobs\guess_indicators_daily_job.py" | Out-Null
Invoke-TrackedStep "backfill_fundamentals(兜底回填)"     "jobs\backfill_fundamentals.py"    | Out-Null
Invoke-TrackedStep "buy_job(买入推荐)"                   "jobs\guess_indicators_daily_buy_job.py" | Out-Null
Invoke-TrackedStep "sell_job(卖出提示)"                  "jobs\guess_indicators_daily_sell_job.py" | Out-Null

# 无论前面是否失败，最后都跑 monitor。
$monitorCode = Run-Step "monitor_daily(健康监控)" "jobs\monitor_daily.py"
if ($null -eq $monitorCode) { $monitorCode = 0 }
if ($monitorCode -ne 0) {
    $anyFailed = $true
    $failedSteps += "monitor_daily(exit=$monitorCode)"
}

$spotSourceLine = "spot_source=(missing)"
if (Test-Path $SpotSourceFile) {
    $spotSourceLine = (Get-Content -Path $SpotSourceFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ([string]::IsNullOrEmpty($spotSourceLine)) {
        $spotSourceLine = "spot_source=(empty file)"
    }
}

$endTs = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
# 门禁：monitor 失败 → 非 0；前面步骤失败也记为非 0，便于计划任务感知。
$exitCode = 0
if ($monitorCode -ne 0) {
    $exitCode = $monitorCode
} elseif ($anyFailed) {
    $exitCode = 1
}

$status = if ($exitCode -eq 0) { "OK" } else { "FAILED" }
$statusBody = @(
    "status=$status"
    "exit_code=$exitCode"
    "date=$DateTag"
    "start=$startTs"
    "end=$endTs"
    $spotSourceLine
    "monitor_exit=$monitorCode"
    "failed_steps=$([string]::Join('; ', $failedSteps))"
) -join "`n"
Set-Content -Path $StatusFile -Value $statusBody -Encoding UTF8

Write-Log "==================== END $endTs $spotSourceLine monitor_exit=$monitorCode overall_exit=$exitCode ===================="
exit $exitCode
