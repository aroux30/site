// .claude/hooks/stop-gate.mjs — دروازه قطعی پایان دور
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

let input = {};
try {
  const raw = readFileSync(0, "utf8");
  if (raw && raw.trim()) input = JSON.parse(raw);
} catch {
  input = {};
}

// فقط در حالت /goal تعاملی: اگر stop_hook_active === true بود فوراً exit 0 (جلوگیری از حلقه بی‌نهایت و سقف ۸تایی Claude Code v2.1.143+)
if (input?.stop_hook_active === true) {
  process.exit(0);
}
if (existsSync(join(process.cwd(), "AGENT_STOP"))) {
  process.exit(0);
}

let round = process.env.GYM_ROUND;
if (!round) {
  try {
    const ledger = JSON.parse(readFileSync(join(process.cwd(), ".loop", "state_ledger.json"), "utf8"));
    round = String(ledger?.activeRound ?? "");
  } catch {}
}
if (!round) process.exit(0);

const root = process.cwd();
const missing = [];
const visionReceiptsPath = join(root, ".loop", "vision_receipts.jsonl");
const visionLogPath = join(root, ".loop", "vision_reads.jsonl");
const ledgerPath = join(root, ".loop", "state_ledger.json");
const scopeDir = (process.env.GYM_SCOPE || "builder") === "builder" ? "builder-gym" : "gym";
const roundDir3 = join(root, ".loop", "artifacts", scopeDir, `round-${String(round).padStart(3, "0")}`);
const roundDir2 = join(root, ".loop", "artifacts", scopeDir, `round-${String(round).padStart(2, "0")}`);
const roundDir = existsSync(roundDir3) ? roundDir3 : roundDir2;
const verdictPath = existsSync(join(roundDir3, "verifier_verdict.json"))
  ? join(roundDir3, "verifier_verdict.json")
  : join(roundDir2, "verifier_verdict.json");

if (!existsSync(ledgerPath)) missing.push(".loop/state_ledger.json وجود ندارد یا آپدیت نشده است.");
if (!existsSync(join(roundDir, "mutation_report.json"))) {
  missing.push(`گزارش تست ${roundDir}/mutation_report.json ساخته نشده است.`);
}
if (!existsSync(verdictPath)) {
  missing.push(`تاییدیه ساب‌ایجنت ناظر (verifier_verdict.json) برای دور ${round} ثبت نشده است. ساب‌ایجنت qa-verifier را فراخوانی کن.`);
} else {
  try {
    const v = JSON.parse(readFileSync(verdictPath, "utf8"));
    if (v?.verdict !== "APPROVE") {
      missing.push(`حکم ساب‌ایجنت ناظر "${v?.verdict}" است نه "APPROVE". ایرادهای blocking_reasons را رفع و مجدداً داوری بگیر.`);
    }
  } catch {
    missing.push("فایل verifier_verdict.json ساختار JSON معتبر ندارد.");
  }
}

let beforeReads = 0;
let afterReads = 0;
const targetVisionPath = existsSync(visionReceiptsPath) ? visionReceiptsPath : visionLogPath;
if (existsSync(targetVisionPath)) {
  const lines = readFileSync(targetVisionPath, "utf8").trim().split(/\r?\n/).filter(Boolean);
  for (const line of lines) {
    try {
      const rec = JSON.parse(line);
      if (String(rec.round) === String(round)) {
        if (rec.phase === "before") beforeReads++;
        if (rec.phase === "after") afterReads++;
      }
    } catch {}
  }
}
if (beforeReads === 0) missing.push(`هیچ عکس before/ برای دور ${round} با ابزار Read (Vision) باز نشده است.`);
if (afterReads === 0) missing.push(`هیچ عکس after/ برای دور ${round} با ابزار Read (Vision) باز نشده است.`);

if (missing.length > 0) {
  console.log(
    JSON.stringify({
      decision: "block",
      reason: `توقف دور ${round} مسدود شد. موارد زیر پیش از پایان دور الزامی هستند:\n- ${missing.join("\n- ")}`
    })
  );
}
process.exit(0);
