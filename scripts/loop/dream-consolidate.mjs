import fs from "node:fs";
import path from "node:path";

const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const MEMORY_PATH = path.join(PROJECT_ROOT, ".loop", "MEMORY.md");
const MAX_LINES = 200;

export function consolidateMemory() {
  console.log(">>> [Dream-Consolidate] Running offline memory consolidation pass...");

  if (!fs.existsSync(MEMORY_PATH)) {
    console.warn("Memory file not found. Skipping consolidation.");
    return;
  }

  const raw = fs.readFileSync(MEMORY_PATH, "utf8");
  const lines = raw.split("\n");

  console.log(`    Current memory length: ${lines.length} lines (Hard ceiling: ${MAX_LINES}).`);

  // Strip trailing blank lines and deduplicate entries
  const cleaned = [];
  const seenHeaders = new Set();

  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith("###") || trimmed.startsWith("##")) {
      if (seenHeaders.has(trimmed)) {
        continue;
      }
      seenHeaders.add(trimmed);
    }
    cleaned.push(line);
  }

  // Enforce 200 lines hard ceiling
  let finalized = cleaned;
  if (finalized.length > MAX_LINES) {
    console.warn(`    Memory exceeded ${MAX_LINES} lines (${finalized.length}). Compacting oldest sections...`);
    // Keep header (first 30 lines) and newest rules (last 160 lines)
    const header = finalized.slice(0, 30);
    const tail = finalized.slice(-(MAX_LINES - 35));
    finalized = [
      ...header,
      "",
      "> *[Note: Middle section compacted during automated dream-consolidation pass]*",
      "",
      ...tail,
    ];
  }

  fs.writeFileSync(MEMORY_PATH, finalized.join("\n"), "utf8");
  console.log(`>>> Memory consolidated cleanly to ${finalized.length} lines.`);
}

if (process.argv[1] && process.argv[1].endsWith("dream-consolidate.mjs")) {
  consolidateMemory();
}
