const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

const BASE_URL = "http://127.0.0.1:4002";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-diag-tok-${Date.now()}.py`);
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
  const logs = [];
  page.on("console", (msg) => logs.push({ type: msg.type(), text: msg.text() }));
  page.on("pageerror", (err) => logs.push({ type: "pageerror", text: err.message }));

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // Search and click Slides
  const searchInput = page.locator('input[placeholder*="جستجو"]').first();
  await searchInput.fill("اسلاید پیشرفته");
  await page.waitForTimeout(400);

  const slidesCard = page.locator('button:has-text("اسلاید پیشرفته")').first();
  if (await slidesCard.isVisible()) {
    await slidesCard.click();
    await page.waitForTimeout(600);
  }

  // Take screenshot of left inspector
  const inspector = page.locator('[data-builder-inspector]');
  if (await inspector.isVisible()) {
    await inspector.screenshot({ path: path.resolve(".loop/artifacts/left-panel-diag.png") });
    console.log("Captured left-panel-diag.png");
  }

  // Get inner HTML and text of inspector
  const inspectorText = await inspector.innerText();
  console.log("=== INSPECTOR TEXT ===");
  console.log(inspectorText);

  console.log("=== CONSOLE LOGS ===");
  console.log(JSON.stringify(logs.filter(l => l.type === "error" || l.type === "pageerror" || l.type === "warn"), null, 2));

  await page.screenshot({ path: path.resolve(".loop/artifacts/studio-diag-full.png") });
  console.log("Captured studio-diag-full.png");

  await browser.close();
}

run().catch(console.error);
