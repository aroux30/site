// .claude/hooks/capture-verifier.mjs — ثبت خودکار و غیرقابل‌جعل حکم ساب‌ایجنت qa-verifier همراه با SHA-256
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { createHash } from "node:crypto";

let input = {};
try {
  const raw = readFileSync(0, "utf8");
  if (raw && raw.trim()) input = JSON.parse(raw);
} catch {
  input = {};
}

const agentType = String(input?.agent_type ?? "");
let round = process.env.GYM_ROUND;
if (!round) {
  try {
    const ledger = JSON.parse(readFileSync(join(process.cwd(), ".loop", "state_ledger.json"), "utf8"));
    round = String(ledger?.activeRound ?? "0");
  } catch {
    round = "0";
  }
}

const msg = String(input?.last_assistant_message ?? "");
const isVerifier =
  agentType.includes("qa-verifier") ||
  String(input?.description ?? "").toLowerCase().includes("qa-verifier") ||
  String(input?.prompt ?? "").includes("qa-verifier") ||
  msg.includes('"verdict"');

if (isVerifier) {
  const jsonMatch = msg.match(/```jsons*([sS]*?)```/i) ?? msg.match(/({[sS]*"verdict"[sS]*})/);
  if (!jsonMatch) {
    console.error("خطای ناظر: هیچ بلوک JSON معتبری شامل 'verdict' در پاسخ ناظر qa-verifier یافت نشد.");
    process.exit(2);
  }

  let parsed;
  try {
    parsed = JSON.parse(jsonMatch[1].trim());
  } catch (err) {
    console.error("خطای ناظر: بلوک JSON ناظر ساختار نامعتبر دارد: " + err.message);
    process.exit(2);
  }

  if (!parsed.verdict || !["APPROVE", "REJECT"].includes(parsed.verdict)) {
    console.error("خطای ناظر: مقدار verdict در JSON ناظر باید 'APPROVE' یا 'REJECT' باشد.");
    process.exit(2);
  }

  // محاسبه SHA-256 خروجی برای اطمینان از عدم دستکاری
  const rawString = JSON.stringify(parsed);
  const sha256 = createHash("sha256").update(rawString).digest("hex");
  parsed.sha256 = sha256;
  parsed.timestamp = new Date().toISOString();

  const scopeDir = (process.env.GYM_SCOPE || "builder") === "builder" ? "builder-gym" : "gym";
  const roundDir3 = join(process.cwd(), ".loop", "artifacts", scopeDir, `round-${String(round).padStart(3, "0")}`);
  const roundDir2 = join(process.cwd(), ".loop", "artifacts", scopeDir, `round-${String(round).padStart(2, "0")}`);
  mkdirSync(roundDir3, { recursive: true });
  mkdirSync(roundDir2, { recursive: true });
  writeFileSync(join(roundDir3, "verifier_verdict.json"), JSON.stringify(parsed, null, 2), "utf8");
  writeFileSync(join(roundDir2, "verifier_verdict.json"), JSON.stringify(parsed, null, 2), "utf8");
}

process.exit(0);
