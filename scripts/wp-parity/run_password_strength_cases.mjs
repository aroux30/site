// Run the password strength evaluator against fixed cases.
//
// The evaluator is a TypeScript module that imports `cn` and pulls in React,
// so it cannot be imported directly in plain Node. What is under test is the
// scoring logic, so the function is extracted textually and evaluated on its
// own. That is deliberate: a copy of the rules in this file would test the copy.

import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

const meterPath = process.argv[2];
if (!meterPath) {
  console.error("usage: node run_password_strength_cases.mjs <meter.tsx>");
  process.exit(2);
}

const source = readFileSync(meterPath, "utf8");

// Pull out the `_TRANSLITERATE`-style constants and the function itself.
function extractConst(name) {
  const re = new RegExp(`const ${name}[^=]*=\\s*\\{([\\s\\S]*?)\\};`);
  const m = source.match(re);
  if (!m) return null;
  return m[1];
}

function extractFunction(name) {
  const start = source.indexOf(`function ${name}`);
  if (start === -1) return null;
  // Walk braces to find the end of the function body.
  let depth = 0;
  let i = source.indexOf("{", start);
  for (let j = i; j < source.length; j++) {
    if (source[j] === "{") depth++;
    else if (source[j] === "}") {
      depth--;
      if (depth === 0) {
        let body = source.slice(start, j + 1);
        // Strip TypeScript annotations so `new Function` can compile it.
        // The file is .tsx and this is plain JS runtime; stripping the types is
        // the whole cost of not pulling in a compiler.
        body = body.replace(/:\s*PasswordStrength/g, "");
        body = body.replace(/:\s*string\[\]/g, "");
        body = body.replace(/:\s*string/g, "");
        body = body.replace(/:\s*Record<[^>]*>/g, "");
        body = body.replace(/:\s*number/g, "");
        body = body.replace(/:\s*boolean/g, "");
        body = body.replace(/\s*as\s+const/g, "");
        body = body.replace(/\s+as\s+\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+\s*\|\s*\d+/g, "");
        return body;
      }
    }
  }
  return null;
}

// Pull out the array constants the function closes over. Same reasoning as the
// function: extract the real ones, not copies, so a change to the bands is a
// failing test rather than a silently stale duplicate.
function extractArray(name) {
  const re = new RegExp(`const ${name}[^=]*=\\s*\\[([\\s\\S]*?)\\]\\s*as const;`);
  const m = source.match(re);
  return m ? m[1] : null;
}

const fnSource = extractFunction("evaluatePassword");
if (!fnSource) {
  console.error("FAIL: evaluatePassword not found in the meter");
  process.exit(1);
}

const LABELS = extractArray("LABELS");
const BAR_COLORS = extractArray("BAR_COLORS");
if (!LABELS || !BAR_COLORS) {
  console.error("FAIL: LABELS or BAR_COLORS not found in the meter");
  process.exit(1);
}

// The function body only needs these identifiers, so provide them.
const _NON_SLUG = /[^a-z0-9]+/g;

const evaluatePassword = new Function(
  "_NON_SLUG", "LABELS", "BAR_COLORS",
  `${fnSource}; return evaluatePassword;`,
)(_NON_SLUG, eval(`[${LABELS}]`), eval(`[${BAR_COLORS}]`));

const cases = [
  ["12345678", 0, "eight digits"],
  ["abcdefgh", 1, "eight letters, no digits"],
  ["aaaaaaaa", 0, "one repeated character"],
  ["qwerty123", 1, "keyboard walk"],
  ["Test1234", 1, "dictionary-ish with one capital"],
  ["Tr0ub4dor&3", 3, "11 chars, diverse, dictionary shape"],
  ["Kj#9mQ!vX2pL@zW7", 4, "16 chars, all four classes"],
];

let allPass = true;
for (const [pwd, minScore, why] of cases) {
  const r = evaluatePassword(pwd);
  const pass = r.score >= minScore;
  if (!pass) allPass = false;
  console.log(
    `  ${pass ? "ok  " : "FAIL"} ${JSON.stringify(pwd).padEnd(20)} ` +
    `score=${r.score} (min ${minScore}) — ${why}`,
  );
}

if (allPass) console.log("ALL PASS");
process.exit(allPass ? 0 : 1);
