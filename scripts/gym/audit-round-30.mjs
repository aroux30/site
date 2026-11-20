import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-30/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r30-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound24Audit() {
  console.log(`>>> [Gym Round 30: Digital Inventory, Fintech, Gamification, Cashback & Integrations] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.93.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    },
  });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: "http://localhost:3000", httpOnly: false, sameSite: "Lax" },
    ]);
  }
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();
  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    tests: {},
  };

  try {
    // 1. Visit Admin Digital Inventory /admin/digital-inventory
    console.log("    1. Navigating to Admin Digital Inventory /admin/digital-inventory...");
    await page.goto(`${BASE_URL}/admin/digital-inventory`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotDigital = path.join(ARTIFACTS_DIR, "01-admin-digital-inventory.png");
    await page.screenshot({ path: shotDigital });
    findings.tests.digitalInventory = { shot: shotDigital };

    // 2. Visit Admin Fintech /admin/fintech
    console.log("    2. Navigating to Admin Fintech /admin/fintech...");
    await page.goto(`${BASE_URL}/admin/fintech`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotFintech = path.join(ARTIFACTS_DIR, "02-admin-fintech.png");
    await page.screenshot({ path: shotFintech });
    findings.tests.fintech = { shot: shotFintech };

    // 3. Visit Admin Gamification /admin/gamification
    console.log("    3. Navigating to Admin Gamification /admin/gamification...");
    await page.goto(`${BASE_URL}/admin/gamification`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotGamification = path.join(ARTIFACTS_DIR, "03-admin-gamification.png");
    await page.screenshot({ path: shotGamification });
    findings.tests.gamification = { shot: shotGamification };

    // 4. Visit Admin Cashback /admin/cashback
    console.log("    4. Navigating to Admin Cashback /admin/cashback...");
    await page.goto(`${BASE_URL}/admin/cashback`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotCashback = path.join(ARTIFACTS_DIR, "04-admin-cashback.png");
    await page.screenshot({ path: shotCashback });
    findings.tests.cashback = { shot: shotCashback };

    // 5. Visit Admin Integrations /admin/integrations
    console.log("    5. Navigating to Admin Integrations /admin/integrations...");
    await page.goto(`${BASE_URL}/admin/integrations`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotIntegrations = path.join(ARTIFACTS_DIR, "05-admin-integrations.png");
    await page.screenshot({ path: shotIntegrations });
    findings.tests.integrations = { shot: shotIntegrations };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-30]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound24Audit();
