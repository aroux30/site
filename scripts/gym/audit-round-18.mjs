import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-18/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r18-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound18Audit() {
  console.log(`>>> [Gym Round 18: Discounts, User Verification & FAQ] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.89.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    },
  });

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
    // 1. Visit Admin Discounts /admin/discounts
    console.log("    1. Navigating to Admin Discounts /admin/discounts...");
    await page.goto(`${BASE_URL}/admin/discounts`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotAdminDiscounts = path.join(ARTIFACTS_DIR, "01-admin-discounts.png");
    await page.screenshot({ path: shotAdminDiscounts });
    findings.tests.adminDiscounts = { shot: shotAdminDiscounts };

    // 2. Visit Admin User Verification /admin/user-verification
    console.log("    2. Navigating to Admin User Verification /admin/user-verification...");
    await page.goto(`${BASE_URL}/admin/user-verification`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotAdminUserVerification = path.join(ARTIFACTS_DIR, "02-admin-user-verification.png");
    await page.screenshot({ path: shotAdminUserVerification });
    findings.tests.adminUserVerification = { shot: shotAdminUserVerification };

    // 3. Visit Storefront FAQ /faq
    console.log("    3. Navigating to Storefront FAQ /faq...");
    await page.goto(`${BASE_URL}/faq`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotStoreFaq = path.join(ARTIFACTS_DIR, "03-storefront-faq.png");
    await page.screenshot({ path: shotStoreFaq });
    findings.tests.storeFaq = { shot: shotStoreFaq };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 18 audit capture complete. Saved to: ${reportPath}`);
}

runRound18Audit().catch((err) => {
  console.error("Round 18 audit failure:", err);
  process.exit(1);
});
