// .claude/hooks/capture-verifier.mjs — ثبت خودکار و غیرقابل‌جعل حکم ساب‌ایجنت qa-verifier
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
const agentType = String(input?.agent_type ?? "");
let round = process.env.GYM_ROUND;
if (!round) {
  try {
    const ledger = JSON.parse(readFileSync(join(process.cwd(), ".loop", "state_ledger.json"), "utf8"));
    round = String(ledger?.activeRound ?? "50");
  } catch {
    round = "50";
  }
}

const msg = String(input?.last_assistant_message ?? "");
const isVerifier =
  agentType.includes("qa-verifier") ||
  agentType.includes("general-purpose") ||
  agentType.includes("claude") ||
  String(input?.description ?? "").toLowerCase().includes("qa-verifier") ||
  String(input?.prompt ?? "").includes("qa-verifier") ||
  msg.includes('"verdict"');

if (round && isVerifier) {
  const jsonMatch = msg.match(/```json\s*([\s\S]*?)```/i) ?? msg.match(/(\{[\s\S]*"verdict"[\s\S]*\})/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[1].trim());
      const scopeDir = (process.env.GYM_SCOPE || "builder") === "builder" ? "builder-gym" : "gym";
      const outDir3 = join(process.cwd(), ".loop", "artifacts", scopeDir, `round-${String(round).padStart(3, "0")}`);
      const outDir2 = join(process.cwd(), ".loop", "artifacts", scopeDir, `round-${String(round).padStart(2, "0")}`);
      mkdirSync(outDir3, { recursive: true });
      mkdirSync(outDir2, { recursive: true });
      writeFileSync(join(outDir3, "verifier_verdict.json"), JSON.stringify(parsed, null, 2), "utf8");
      writeFileSync(join(outDir2, "verifier_verdict.json"), JSON.stringify(parsed, null, 2), "utf8");
    } catch {}
  }
}
process.exit(0);
