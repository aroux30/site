import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-09/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r09-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound09Audit() {
  console.log(`>>> [Gym Round 09: Account, Orders & Wallet Overload] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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
    // 1. Account Profile / Dashboard
    console.log("    1. Auditing /account (Profile)...");
    await page.goto(`${BASE_URL}/account`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotAccount = path.join(ARTIFACTS_DIR, "01-account-profile.png");
    await page.screenshot({ path: shotAccount });
    findings.tests.profile = { shot: shotAccount };

    // 2. Orders History & Tracking
    console.log("    2. Auditing /account/orders (Orders History)...");
    await page.goto(`${BASE_URL}/account/orders`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotOrders = path.join(ARTIFACTS_DIR, "02-account-orders.png");
    await page.screenshot({ path: shotOrders });
    findings.tests.orders = { shot: shotOrders };

    // 3. Addresses Management
    console.log("    3. Auditing /account/addresses...");
    await page.goto(`${BASE_URL}/account/addresses`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotAddresses = path.join(ARTIFACTS_DIR, "03-account-addresses.png");
    await page.screenshot({ path: shotAddresses });
    findings.tests.addresses = { shot: shotAddresses };

    // 4. Wallet & Balances
    console.log("    4. Auditing /account/wallet...");
    await page.goto(`${BASE_URL}/account/wallet`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotWallet = path.join(ARTIFACTS_DIR, "04-account-wallet.png");
    await page.screenshot({ path: shotWallet });
    findings.tests.wallet = { shot: shotWallet };

    // 5. Digital Codes
    console.log("    5. Auditing /account/digital-codes...");
    await page.goto(`${BASE_URL}/account/digital-codes`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotCodes = path.join(ARTIFACTS_DIR, "05-account-digital-codes.png");
    await page.screenshot({ path: shotCodes });
    findings.tests.digitalCodes = { shot: shotCodes };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 09 audit capture complete. Saved to: ${reportPath}`);
}

runRound09Audit().catch((err) => {
  console.error("Round 09 audit failure:", err);
  process.exit(1);
});
