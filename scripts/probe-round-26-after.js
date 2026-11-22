const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const AFTER_DIR = path.resolve(".loop/artifacts/builder-gym/round-26/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r26-after-${Date.now()}.py`);
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
  console.log("Starting Round 26 Probe After...");
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
  await page.screenshot({ path: path.join(AFTER_DIR, "01-studio-overview.png") });
  console.log("Captured 01-studio-overview.png");

  // 2. Insert video widget from palette
  const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("ویدئو");
    await page.waitForTimeout(300);

    const videoCard = page.locator('text="پخش‌کننده ویدئو"').first();
    if (await videoCard.isVisible()) {
      await videoCard.click();
      await page.waitForTimeout(600);
    }
  }

  // 3. Inspect video element with URL & Poster controls
  const inspector = page.locator('[data-builder-inspector]');
  const urlInput = inspector.locator('[data-testid="video-url-input"]');
  if (await urlInput.isVisible()) {
    await urlInput.fill("https://www.aparat.com/video/video/embed/videohash/test123");
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(AFTER_DIR, "02-video-inspected.png") });
    console.log("Captured 02-video-inspected.png");
  }

  // 4. Insert Star Rating and verify size controls
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(300);
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("امتیاز");
    await page.waitForTimeout(300);
    const starCard = page.locator('text="امتیاز ستاره‌ای"').first();
    if (await starCard.isVisible()) {
      await starCard.click();
      await page.waitForTimeout(500);
    }
  }

  const ratingValueInput = inspector.locator('[data-testid="star-rating-value-input"]');
  if (await ratingValueInput.isVisible()) {
    await ratingValueInput.fill("4.9");
    await page.waitForTimeout(400);
    await page.screenshot({ path: path.join(AFTER_DIR, "03-star-rating-nudged.png") });
    console.log("Captured 03-star-rating-nudged.png");
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
