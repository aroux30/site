import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "after";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", "round-03", STAGE);
const BACKEND_DIR = path.join(PROJECT_ROOT, "backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r03-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 03] Auditing Inspector Controls & Global Styles [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

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
    weight: "Weight 3: InspectorPanel (Content, Style, Advanced) & Global Styles",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(500);

    // 1. Audit Inspector Content Tab
    console.log("    1. Auditing Inspector Content Tab...");
    const contentTab = page.getByRole("tab", { name: "محتوا" });
    await contentTab.click();
    await page.waitForTimeout(500);

    const shotContent = path.join(ARTIFACTS_DIR, "01-inspector-content-tab.png");
    await page.locator("div.border-s.border-border").first().screenshot({ path: shotContent });
    findings.checks.contentScreenshot = shotContent;

    // 2. Audit Inspector Style Tab
    console.log("    2. Auditing Inspector Style Tab & Token Pickers...");
    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(500);

    const shotStyle = path.join(ARTIFACTS_DIR, "02-inspector-style-tab.png");
    await page.locator("div.border-s.border-border").first().screenshot({ path: shotStyle });
    findings.checks.styleScreenshot = shotStyle;

    // 3. Audit Inspector Advanced Tab
    console.log("    3. Auditing Inspector Advanced Tab (Visibility & Animations)...");
    const advTab = page.getByRole("tab", { name: "پیشرفته" });
    await advTab.click();
    await page.waitForTimeout(500);

    const shotAdv = path.join(ARTIFACTS_DIR, "03-inspector-advanced-tab.png");
    await page.locator("div.border-s.border-border").first().screenshot({ path: shotAdv });
    findings.checks.advancedScreenshot = shotAdv;

    // 4. Audit Global Styles Dialog
    console.log("    4. Auditing Global Styles Dialog...");
    const globalStylesBtn = page.getByRole("button", { name: "استایل سراسری" });
    if (await globalStylesBtn.isVisible()) {
      await globalStylesBtn.click();
      await page.waitForTimeout(800);

      const shotGlobalDialog = path.join(ARTIFACTS_DIR, "04-global-styles-dialog.png");
      const dialogContent = page.locator("div[role='dialog']").first();
      if (await dialogContent.isVisible()) {
        await dialogContent.screenshot({ path: shotGlobalDialog });
        findings.checks.globalStylesScreenshot = shotGlobalDialog;
      }

      // Close dialog
      await page.keyboard.press("Escape");
      await page.waitForTimeout(500);
    }

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 03 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 03 audit failed:", err);
  process.exit(1);
});
