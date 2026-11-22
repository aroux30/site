const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const BEFORE_DIR = path.resolve(".loop/artifacts/builder-gym/round-37/before");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r37-probe-${Date.now()}.py`);
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
  console.log("Starting Round 37 Probe Before...");
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

  // 1. Capture studio overview
  await page.screenshot({ path: path.join(BEFORE_DIR, "01-studio-overview.png") });
  console.log("Captured 01-studio-overview.png");

  // 2. Open palette and search for menu_anchor
  const blocksTabBtn = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("لنگر");
    await page.waitForTimeout(300);
    await page.screenshot({ path: path.join(BEFORE_DIR, "02-palette-search-anchor.png") });
    console.log("Captured 02-palette-search-anchor.png");
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
