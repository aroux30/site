// .claude/hooks/track-vision-read.mjs — ثبت قطعی رسید خواندن تصاویر Vision
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
const fp = String(input?.tool_input?.file_path ?? "").replace(/\\/g, "/");

if (/\.png$/i.test(fp) && fp.includes(".loop/artifacts/")) {
  const dir = join(process.cwd(), ".loop");
  mkdirSync(dir, { recursive: true });
  let roundVal = process.env.GYM_ROUND;
  if (!roundVal) {
    try {
      const ledger = JSON.parse(readFileSync(join(process.cwd(), ".loop", "state_ledger.json"), "utf8"));
      roundVal = String(ledger.activeRound);
    } catch {}
  }
  const record = JSON.stringify({
    ts: new Date().toISOString(),
    round: roundVal ?? "interactive",
    phase: fp.includes("/before/") ? "before" : fp.includes("/after/") ? "after" : "other",
    path: fp
  });
  appendFileSync(join(dir, "vision_reads.jsonl"), record + "\n", "utf8");
}
process.exit(0);