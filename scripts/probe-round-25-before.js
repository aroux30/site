const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const BEFORE_DIR = path.resolve(".loop/artifacts/builder-gym/round-25/before");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r25-probe-${Date.now()}.py`);
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
  console.log("Starting Round 25 Probe Before...");
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

  // 1. Capture studio layout
  await page.screenshot({ path: path.join(BEFORE_DIR, "01-studio-overview.png") });
  console.log("Captured 01-studio-overview.png");

  // 2. Insert and select a cart_summary block from palette
  const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(400);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("سبد");
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(BEFORE_DIR, "02-palette-search-cart.png") });
    console.log("Captured 02-palette-search-cart.png");

    const cartSummaryCard = page.locator('text="خلاصه سبد خرید"').first();
    if (await cartSummaryCard.isVisible()) {
      await cartSummaryCard.click();
      await page.waitForTimeout(600);
    }
  }

  // 3. Inspect the newly inserted element
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const cartSummaryEl = frame.locator('text="جمع اقلام:"').first();
  if (await cartSummaryEl.isVisible()) {
    await cartSummaryEl.click();
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(BEFORE_DIR, "03-cart-summary-selected.png") });
    console.log("Captured 03-cart-summary-selected.png");

    // Nudge cart summary title and button label
    const inspector = page.locator('[data-builder-inspector]');
    const titleInput = inspector.locator('input[value*="خلاصه سبد"]').first();
    if (await titleInput.isVisible()) {
      await titleInput.fill("فاکتور نهایی و تسویه");
      await page.waitForTimeout(300);
    }
    const btnInput = inspector.locator('input[value*="ادامه فرآیند"]').first();
    if (await btnInput.isVisible()) {
      await btnInput.fill("پرداخت اینترنتی سفارش");
      await page.waitForTimeout(300);
    }
    await page.screenshot({ path: path.join(BEFORE_DIR, "04-cart-summary-nudged.png") });
    console.log("Captured 04-cart-summary-nudged.png");
  }

  // Record findings
  const report = {
    url: `${BASE_URL}/e2e-isolated-scratchpad?builder=1`,
    consoleErrors,
    timestamp: new Date().toISOString(),
  };
  fs.writeFileSync(path.join(BEFORE_DIR, "report.json"), JSON.stringify(report, null, 2), "utf8");
  console.log("Saved report.json");

  await browser.close();
  console.log("Probe Before complete!");
}

run().catch((err) => {
  console.error("Probe before failed:", err);
  process.exit(1);
});
