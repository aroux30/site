import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-14/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r14-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound14Audit() {
  console.log(`>>> [Gym Round 14: PDP & Product Detail Overload] Stage: [${STAGE}]...`);
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
    // 1. Visit PDP /products/1800-yvsy
    console.log("    1. Navigating to Product Detail Page /products/1800-yvsy...");
    await page.goto(`${BASE_URL}/products/1800-yvsy`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotPdpTop = path.join(ARTIFACTS_DIR, "01-pdp-hero-and-pricing.png");
    await page.screenshot({ path: shotPdpTop });
    findings.tests.pdpTop = { shot: shotPdpTop };

    // 2. Scroll to Specifications / Description / Reviews Tabs
    console.log("    2. Auditing PDP tabs and reviews section...");
    const tabs = page.locator("div[role='tablist']").first();
    if (await tabs.isVisible()) {
      await tabs.scrollIntoViewIfNeeded();
      await page.waitForTimeout(500);
    }

    const shotPdpTabs = path.join(ARTIFACTS_DIR, "02-pdp-specs-and-reviews.png");
    await page.screenshot({ path: shotPdpTabs });
    findings.tests.pdpTabs = { shot: shotPdpTabs };

    // 3. Check mobile view of PDP (375px)
    console.log("    3. Auditing PDP in mobile viewport (375px)...");
    await page.setViewportSize({ width: 375, height: 812 });
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotPdpMobile = path.join(ARTIFACTS_DIR, "03-pdp-mobile-view.png");
    await page.screenshot({ path: shotPdpMobile });
    findings.tests.pdpMobile = { shot: shotPdpMobile };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 14 audit capture complete. Saved to: ${reportPath}`);
}

runRound14Audit().catch((err) => {
  console.error("Round 14 audit failure:", err);
  process.exit(1);
});
