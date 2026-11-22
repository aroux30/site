const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const AFTER_DIR = path.resolve(".loop/artifacts/builder-gym/round-24/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r24-after-${Date.now()}.py`);
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
  console.log("Starting Round 24 Probe After...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
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
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Capture studio layout (single shortcuts button in toolbar)
  await page.screenshot({ path: path.join(AFTER_DIR, "01-studio-layout.png") });
  console.log("Captured 01-studio-layout.png");

  // 2. Select heading and inspect
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const heading = frame.locator('[data-element-id="el_e2ehead1"]').first();
  if (await heading.isVisible()) {
    await heading.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(AFTER_DIR, "02-heading-selected.png") });
    console.log("Captured 02-heading-selected.png");

    const inspector = page.locator('[data-builder-inspector]');

    // Nudge Content tab
    const headingInput = inspector.locator('[data-testid="heading-text-input"]');
    if (await headingInput.isVisible()) {
      await headingInput.fill("سرتیتر تغییریافته ۳۶۰ درجه و زنده");
      await page.waitForTimeout(400);
      await page.screenshot({ path: path.join(AFTER_DIR, "03-heading-nudged-content.png") });
      console.log("Captured 03-heading-nudged-content.png");
    }

    // Switch to Style tab
    const styleTab = inspector.locator('button[role="tab"]:has-text("استایل")').first();
    if (await styleTab.isVisible()) {
      await styleTab.click();
      await page.waitForTimeout(400);
      const padTop = inspector.locator('[data-testid="padding-top-input"]').first();
      if (await padTop.isVisible()) {
        await padTop.fill("28");
        await page.waitForTimeout(400);
      }
      await page.screenshot({ path: path.join(AFTER_DIR, "04-heading-style-padding.png") });
      console.log("Captured 04-heading-style-padding.png");
    }

    // Switch to Advanced tab (single Transform and single Mask group)
    const advTab = inspector.locator('button[role="tab"]:has-text("پیشرفته")').first();
    if (await advTab.isVisible()) {
      await advTab.click();
      await page.waitForTimeout(400);
      const rotateInput = inspector.locator('[data-testid="transform-rotate-input"]').first();
      if (await rotateInput.isVisible()) {
        await rotateInput.fill("5");
        await page.waitForTimeout(400);
      }
      await page.screenshot({ path: path.join(AFTER_DIR, "05-heading-advanced-transform.png") });
      console.log("Captured 05-heading-advanced-transform.png");
    }
  }

  // 3. Check blocks palette basic tab blocks count
  const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(AFTER_DIR, "06-blocks-palette-list.png") });
    console.log("Captured 06-blocks-palette-list.png");

    // Search for new widgets
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("پیشرفت");
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(AFTER_DIR, "07-blocks-search-progress.png") });
    console.log("Captured 07-blocks-search-progress.png");
  }

  // Record findings
  const report = {
    url: `${BASE_URL}/e2e-isolated-scratchpad?builder=1`,
    consoleErrors,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(AFTER_DIR, "report.json"), JSON.stringify(report, null, 2), "utf8");
  console.log("Saved report.json");

  await browser.close();
  console.log("Probe After complete!");
}

run().catch((err) => {
  console.error("Probe after failed:", err);
  process.exit(1);
});
