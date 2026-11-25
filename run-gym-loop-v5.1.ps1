# run-gym-loop-v5.1.ps1 — اجرای حلقه با بازنشانی کانتکست در هر دور (ویندوز)
# مثال ۱ (راه‌اندازی زیرساخت یک‌باره R000):
#   git checkout -b autofix/builder-gym-v5
#   .\run-gym-loop-v5.1.ps1 -Variant 5.2 -BootstrapOnly
# مثال ۲ (آزمایش ۳ دور فقط بیلدر - نسخه ۵.۲):
#   .\run-gym-loop-v5.1.ps1 -Variant 5.2 -MaxRounds 3
# مثال ۳ (اجرای ۲۰ دور کل سایت + بیلدر - نسخه ۵.۱):
#   .\run-gym-loop-v5.1.ps1 -Variant 5.1 -MaxRounds 20 -BudgetPerRound 6.00
# توقف فوری: Ctrl+C یا New-Item AGENT_STOP
# جهت‌دهی: دستور را در STEER.md بنویس تا دور بعد اولویت اول شود.

param(
  [ValidateSet("5.1","5.2")][string]$Variant = "5.2",
  [int]$MaxRounds = 20,
  [double]$BudgetPerRound = 6.00,
  [int]$MaxTurns = 150,
  [ValidateSet("auto","dontAsk")][string]$PermissionMode = "auto",
  [switch]$BootstrapOnly
)

$ErrorActionPreference = "Stop"
$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -eq "main" -or $branch -eq "master") {
  throw "روی شاخه main/master هستی! اول شاخه ایزوله بساز: git checkout -b autofix/builder-gym-v5"
}

$env:CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = "1"

if ($Variant -eq "5.1") {
  $env:GYM_SCOPE = "both"
  $promptFile = "GYM_LOOP_V5.1.md"
  $doneRegex  = '(?m)^\s*GYM_ALL_LEVELS_AND_ELEMENTOR_MASTERED\s*$'
} else {
  $env:GYM_SCOPE = "builder"
  $promptFile = "BUILDER_GYM_LOOP_V5.2.md"
  $doneRegex  = '(?m)^\s*BUILDER_GYM_ALL_LEVELS_MASTERED\s*$'
}

if (-not (Test-Path $promptFile)) {
  throw "فایل $promptFile در ریشه پروژه پیدا نشد."
}

New-Item -ItemType Directory -Force -Path ".loop\runner-logs" | Out-Null
$stalls = 0

for ($i = 1; $i -le $MaxRounds; $i++) {
  if (Test-Path "AGENT_STOP") {
    Write-Host "[STOP] فایل AGENT_STOP دیده شد. حلقه تمیز متوقف شد." -ForegroundColor Yellow
    break
  }

  $headBefore = (git rev-parse HEAD).Trim()
  Write-Host "`n=== GYM v$Variant | RUN $i / $MaxRounds | scope=$($env:GYM_SCOPE) | mode=$PermissionMode | branch=$branch ===" -ForegroundColor Cyan

  if ($BootstrapOnly -or -not (Test-Path ".loop\state_ledger.json")) {
    $task = "فقط دور R000 (راه‌اندازی زیرساخت، اسکریپت‌های scripts/loop، فیکسچرهای کالیبراسیون RED/GREEN، هوک‌ها و qa-verifier طبق اسکیل qa-round-gate) را اجرا کن، گزارش بده و بایست."
  } else {
    $task = "دقیقاً یک دور (Round) بعدی را طبق چرخه ۷ قدمی اجرا کن؛ وضعیت و وزنه فعلی را از .loop/state_ledger.json بخوان و اسکیل‌های .claude/skills/ را فقط در قدم مربوطه بارگذاری کن."
  }

  $prompt = "فایل $promptFile را کامل بخوان. GYM_SCOPE=$($env:GYM_SCOPE). $task"

  $cliArgs = @(
    "-p", $prompt,
    "--permission-mode", $PermissionMode,
    "--max-turns", $MaxTurns,
    "--max-budget-usd", $BudgetPerRound,
    "--output-format", "text"
  )

  # رفع باگ dontAsk: بدون allowedTools، حالت dontAsk ابزارهای Bash/Edit را خودکار Deny می‌کند
  if ($PermissionMode -eq "dontAsk") {
    $cliArgs += @(
      "--allowedTools",
      "Read", "Grep", "Glob", "Edit", "Write", "MultiEdit", "Agent", "Skill",
      "Bash(node *)", "Bash(npx *)", "Bash(npm *)", "Bash(python *)",
      "Bash(git status*)", "Bash(git diff*)", "Bash(git log*)",
      "Bash(git add *)", "Bash(git commit *)", "Bash(git revert *)", "Bash(git restore *)",
      "Bash(powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/loop/rebuild-and-verify.ps1)"
    )
  }

  $output = & claude @cliArgs 2>&1
  $text = ($output | Out-String)
  $logPath = ".loop\runner-logs\v$Variant-run-{0:D3}.log" -f $i
  $text | Out-File -Encoding utf8 $logPath
  $output | Select-Object -Last 30

  if ($BootstrapOnly) {
    Write-Host "[R000] راه‌اندازی تمام شد. فیکسچرهای RED/GREEN و scripts/loop را چک کن، بعد بدون -BootstrapOnly اجرا کن." -ForegroundColor Green
    break
  }

  if ($text -match $doneRegex) {
    Write-Host "[DONE] وزنه‌های اصلی با GATE_OK و تایید qa-verifier پاک‌سازی شدند." -ForegroundColor Green
  }

  $headAfter = (git rev-parse HEAD).Trim()
  if ($headAfter -eq $headBefore) { $stalls++ } else { $stalls = 0 }
  if ($stalls -ge 3) {
    Write-Host "[STALL] ۳ اجرای پیاپی بدون کامیت. NEEDS_HUMAN.md و آخرین لاگ ($logPath) را بررسی کن." -ForegroundColor Red
    break
  }
}