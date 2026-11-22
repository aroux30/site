# ==============================================================================
# run-gym-loop.ps1
# Progressive Overload QA & Fix Loop Runner for Windows
# ==============================================================================

param(
    [int]$MaxRounds = 20,
    [double]$BudgetPerRound = 2.00
)

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "main") {
    throw "ابتدا روی یک شاخه autofix/* بروید! اجرای مستقیم روی main ممنوع است."
}

for ($round = 1; $round -le $MaxRounds; $round++) {
    if (Test-Path "AGENT_STOP") {
        Write-Host "[STOP] فایل AGENT_STOP دیده شد. حلقه تمیز متوقف شد." -ForegroundColor Red
        break
    }

    Write-Host "`n================ GYM ROUND $round / $MaxRounds ================" -ForegroundColor Cyan
    $prompt = "فایل GYM_LOOP.md را کامل بخوان و دقیقاً راند شماره $round را طبق چرخه ۷ مرحله‌ای آن اجرا کن. حتماً از وضعیت فعلی در .loop/GYM_LOG.md ادامه بده، عکس before و after بگیر و با Vision بررسی کن، ری‌بیلد کن، کل تست‌ها را کامل بزن، کامیت کن و .loop/GYM_LOG.md را آپدیت کن."

    $output = claude -p $prompt --permission-mode dontAsk --max-turns 35 --max-budget-usd $BudgetPerRound --output-format text 2>&1
    $output | Tee-Object -FilePath ".loop\gym-round-$round.log"

    if ($output -match "GYM_ALL_5_LEVELS_MASTERED") {
        Write-Host "`n[DONE] هر ۵ سطح وزنه با موفقیت کامل پاک‌سازی و تایید شدند!" -ForegroundColor Green
        break
    }
}
