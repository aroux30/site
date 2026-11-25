#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";

const round = process.env.GYM_ROUND || "0";
console.log("[Round-Report] Generating report for round " + round + "...");
const reportPath = path.join(".loop", "rounds", "builder-round-" + String(round).padStart(3, "0") + ".md");
fs.mkdirSync(path.dirname(reportPath), { recursive: true });
if (!fs.existsSync(reportPath)) {
  fs.writeFileSync(reportPath, "# Round " + round + " Report" + String.fromCharCode(10) + String.fromCharCode(10) + "- Status: In Progress" + String.fromCharCode(10), "utf8");
}
console.log("[Round-Report] Report created at " + reportPath);
