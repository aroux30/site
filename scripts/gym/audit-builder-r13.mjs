import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-13", STAGE);
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

function getAdminToken() {
  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token
async def main():
    user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
    print("TOKEN_START:" + create_access_token(
        user_id,
        extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
        expires_delta=datetime.timedelta(hours=2),
    ))
asyncio.run(main())
`;
  const tmp = path.join(BACKEND_DIR, `.gym-r13-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runAudit() {
  console.log(`>>> [Builder Gym Round 13] Weight 6: Template Dialog Synchronization & Theme Reset [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  const probeIp = `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}`;
  await context.setExtraHTTPHeaders({
    "X-Forwarded-For": `${probeIp}, 10.0.0.1`,
  });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }

  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    weight: "Weight 6: Template Dialog Synchronization & Theme Reset (90kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    // 1. Capture Save Page Template Dialog
    console.log("    1. Capturing Save Page Template dialog...");
    const savePageTplBtn = page.locator("button:has-text('قالب برگه')").first();
    await savePageTplBtn.waitFor({ state: "visible", timeout: 15000 });
    await savePageTplBtn.click();
    await page.waitForTimeout(600);

    const shotSavePage = path.join(ARTIFACTS_DIR, "01-save-page-template-dialog.png");
    await page.screenshot({ path: shotSavePage });
    findings.checks.savePageTemplateScreenshot = shotSavePage;

    // Close dialog
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    // 2. Capture Global Styles Dialog
    console.log("    2. Capturing Global Styles Dialog...");
    const globalStylesBtn = page.locator("button:has-text('استایل سراسری')").first();
    await globalStylesBtn.waitFor({ state: "visible", timeout: 15000 });
    await globalStylesBtn.click();
    await page.waitForTimeout(600);

    const shotGlobalStyles = path.join(ARTIFACTS_DIR, "02-global-styles-reset-dialog.png");
    await page.screenshot({ path: shotGlobalStyles });
    findings.checks.globalStylesScreenshot = shotGlobalStyles;

    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 13 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 13 audit failed:", err);
  process.exit(1);
});
