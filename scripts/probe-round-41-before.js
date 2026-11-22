const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const BEFORE_DIR = path.resolve(".loop/artifacts/builder-gym/round-41/before");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r41-before-${Date.now()}.py`);
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
  console.log("Starting Round 41 Probe Before (1920x1080 viewport)...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
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

  // 1. Capture 1920x1080 Studio layout
  await page.screenshot({ path: path.join(BEFORE_DIR, "01-studio-1920x1080.png") });
  console.log("Captured 01-studio-1920x1080.png");

  // 2. Search for "تاگل" in palette
  const searchInput = page.locator('input[placeholder*="جستجو"]').first();
  await searchInput.fill("تاگل");
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(BEFORE_DIR, "02-palette-search-toggle.png") });
  console.log("Captured 02-palette-search-toggle.png");

  // 3. Search for "نقطه کانونی" in palette
  await searchInput.fill("نقطه کانونی");
  await page.waitForTimeout(400);
  await page.screenshot({ path: path.join(BEFORE_DIR, "03-palette-search-hotspot.png") });
  console.log("Captured 03-palette-search-hotspot.png");

  const report = {
    url: `${BASE_URL}/e2e-isolated-scratchpad?builder=1`,
    viewport: { width: 1920, height: 1080 },
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
