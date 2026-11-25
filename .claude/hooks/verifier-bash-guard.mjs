// .claude/hooks/verifier-bash-guard.mjs — قفل اختصاصی دستورات شل ناظر بدبین qa-verifier
import { readFileSync } from "node:fs";

let input = {};
try {
  const raw = readFileSync(0, "utf8");
  if (raw && raw.trim()) input = JSON.parse(raw);
} catch {
  input = {};
}

const cmd = String(input?.tool_input?.command ?? "").trim();

const deny = (reason) => {
  console.error("BLOCKED BY VERIFIER-BASH-GUARD: " + reason);
  process.stdout.write(
    JSON.stringify({
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: reason,
      },
    })
  );
  process.exit(2);
};

// مسدود کردن اپراتورهای زنجیره‌ای، پایپ و ریدایرکت
if (/[;|&>]|\$\(/i.test(cmd)) {
  deny("استفاده از پایپ، ریدایرکت یا چند دستور هم‌زمان برای ناظر qa-verifier ممنوع است.");
}

// دستورهای مجاز فقط‌خواندنی ناظر
const allowedPrefixes = [
  "node scripts/loop/gate.mjs",
  "node scripts/loop/probe-one.mjs",
  "git status",
  "git diff",
  "git log"
];

const isAllowed = allowedPrefixes.some((prefix) => cmd.startsWith(prefix));
if (!isAllowed) {
  deny("ناظر qa-verifier فقط مجاز به اجرای node scripts/loop/gate.mjs، node scripts/loop/probe-one.mjs و دستورات git status/diff/log است.");
}

process.exit(0);
