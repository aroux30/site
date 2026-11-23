// .claude/hooks/track-vision-read.mjs — ثبت قطعی رسید خواندن تصاویر Vision
import { appendFileSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";

const input = JSON.parse(readFileSync(0, "utf8"));
const fp = String(input?.tool_input?.file_path ?? "").replace(/\\/g, "/");

if (/\.png$/i.test(fp) && fp.includes(".loop/artifacts/")) {
  const dir = join(process.cwd(), ".loop");
  mkdirSync(dir, { recursive: true });
  const roundMatch = fp.match(/round-0*(\d+)/i);
  const detectedRound = roundMatch ? parseInt(roundMatch[1], 10) : null;
  const record = JSON.stringify({
    ts: new Date().toISOString(),
    round: process.env.GYM_ROUND ?? (detectedRound ? String(detectedRound) : "interactive"),
    phase: fp.includes("/before/") ? "before" : fp.includes("/after/") ? "after" : "other",
    path: fp
  });
  appendFileSync(join(dir, "vision_reads.jsonl"), record + "\n", "utf8");
}
process.exit(0);