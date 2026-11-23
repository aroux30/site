// .claude/hooks/capture-verifier.mjs — ثبت خودکار و غیرقابل‌جعل حکم ساب‌ایجنت qa-verifier
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
const agentType = String(input?.agent_type ?? "");
let round = process.env.GYM_ROUND;
if (!round) {
  try {
    const ledger = JSON.parse(readFileSync(join(process.cwd(), ".loop", "state_ledger.json"), "utf8"));
    round = String(ledger.activeRound);
  } catch {}
}

const isVerifier = agentType.includes("qa-verifier") ||
                   String(input?.description ?? "").toLowerCase().includes("qa-verifier") ||
                   String(input?.prompt ?? "").includes("qa-verifier");

if (round && isVerifier) {
  const msg = String(input?.last_assistant_message ?? "");
  const jsonMatch = msg.match(/```json\s*([\s\S]*?)```/i) ?? msg.match(/(\{[\s\S]*"verdict"[\s\S]*\})/);
  if (jsonMatch) {
    try {
      const parsed = JSON.parse(jsonMatch[1].trim());
      const scopeDir = (process.env.GYM_SCOPE || "builder") === "builder" ? "builder-gym" : "gym";
      const outDir = join(process.cwd(), ".loop", "artifacts", scopeDir, `round-${String(round).padStart(3, "0")}`);
      mkdirSync(outDir, { recursive: true });
      writeFileSync(join(outDir, "verifier_verdict.json"), JSON.stringify(parsed, null, 2), "utf8");
    } catch {}
  }
}
process.exit(0);