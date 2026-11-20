import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-07/before");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r07-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
  });

  const token = getAdminToken();
  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }
  await context.setExtraHTTPHeaders({
    "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
  });
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  console.log("Navigating to builder studio for round 07 audit...");
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Studio initial state
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-studio-clean.png") });

  // 2. Open Global Styles Dialog
  const globalStylesBtn = page.getByRole("button", { name: /استایل سراسری/i });
  if (await globalStylesBtn.isVisible()) {
    await globalStylesBtn.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-global-styles-dialog.png") });
    // Close dialog
    const closeBtn = page.locator("button[aria-label='Close'], button:has-text('انصراف'), button:has-text('بستن')").first();
    if (await closeBtn.isVisible()) {
      await closeBtn.click();
      await page.waitForTimeout(400);
    } else {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(400);
    }
  }

  // 3. Open Save Page Template dialog
  const savePageTplBtn = page.getByRole("button", { name: /قالب برگه/i });
  if (await savePageTplBtn.isVisible()) {
    await savePageTplBtn.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-save-page-template-dialog.png") });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
  }

  // 4. Test selecting an element and checking Style tab controls (Typography, Spacing, Border, Background)
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const firstEl = frame.locator("[data-element-id]").first();
  if (await firstEl.isVisible()) {
    await firstEl.click();
    await page.waitForTimeout(400);

    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-inspector-style-tab.png") });

    // Scroll style tab to see background & border
    const stylePanel = page.locator("div[role='tabpanel']").first();
    await page.evaluate(() => {
      const panel = document.querySelector("div[role='tabpanel']");
      if (panel) panel.scrollTop = 400;
    });
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "05-inspector-style-scrolled.png") });
  }

  // 5. Open published page /e2e-isolated-scratchpad (without ?builder=1) for WYSIWYG parity check
  const pubPage = await context.newPage();
  await pubPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
  await pubPage.waitForTimeout(1500);
  await pubPage.screenshot({ path: path.join(ARTIFACTS_DIR, "06-storefront-rendered-page.png") });
  await pubPage.close();

  fs.writeFileSync(path.join(ARTIFACTS_DIR, "audit-report.json"), JSON.stringify({ consoleErrors }, null, 2));
  console.log("Round 07 audit complete.");

  await browser.close();
}

run().catch((err) => {
  console.error("Run failed:", err);
  process.exit(1);
});
