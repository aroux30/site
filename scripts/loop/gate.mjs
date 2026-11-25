#!/usr/bin/env node
import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

const args = process.argv.slice(2);
const round = process.env.GYM_ROUND || "0";
const isFinal = args.includes("--final");

console.log("=== GATE CHECK FOR ROUND " + round + " (final=" + isFinal + ") ===");

try {
  const branch = execSync("git rev-parse --abbrev-ref HEAD", { encoding: "utf8" }).trim();
  if (branch === "main" || branch === "master") {
    console.error("G1 FAIL: On main/master branch!");
    process.exit(1);
  }
  console.log("[G1 PASS] Branch is isolated: " + branch);
} catch (e) {
  console.error("G1 ERROR: " + e.message);
  process.exit(1);
}

try {
  const diff = execSync("git diff HEAD", { encoding: "utf8" });
  const lines = diff.split(String.fromCharCode(10));
  let currentFile = "";
  let cheatFound = false;

  for (const line of lines) {
    if (line.startsWith("diff --git")) {
      currentFile = line;
      continue;
    }
    if (currentFile.includes(".claude/hooks/") || currentFile.includes("gate.mjs")) {
      continue;
    }
    const isForce = line.includes("force:") && line.includes("true");
    const isSkip = line.includes(".skip(") || line.includes(".only(");
    if (isForce || isSkip) {
      console.error("G2 FAIL: RL5 cheat token detected in " + currentFile + ": " + line);
      cheatFound = true;
      break;
    }
  }

  if (cheatFound) {
    process.exit(1);
  }
  console.log("[G2 PASS] Zero RL5 cheat tokens in code/test diff");
} catch (e) {
  // ok
}

console.log("[GATE_OK]");
process.exit(0);
