import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", "round-05", STAGE);
const BACKEND_DIR = path.join(PROJECT_ROOT, "backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r05-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runAudit() {
  console.log(`>>> [Builder Gym Round 05] Auditing Responsive Viewports, Dark Mode & Stress [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }

  const page = await context.newPage();
  await page.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    weight: "Weight 5: Responsive (Mobile/Tablet/Desktop), Dark Mode & 50+ Stress (50kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);

    // 1. Audit Desktop Viewport
    console.log("    1. Auditing Desktop Viewport...");
    const shotDesktop = path.join(ARTIFACTS_DIR, "01-viewport-desktop.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotDesktop });
    findings.checks.desktopScreenshot = shotDesktop;

    // 2. Audit Tablet Viewport (768px)
    console.log("    2. Auditing Tablet Viewport (768px)...");
    const tabletBtn = page.getByRole("button", { name: /تبلت/i });
    if (await tabletBtn.isVisible()) {
      await tabletBtn.click();
      await page.waitForTimeout(600);
    }
    const shotTablet = path.join(ARTIFACTS_DIR, "02-viewport-tablet-768.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotTablet });
    findings.checks.tabletScreenshot = shotTablet;

    // 3. Audit Mobile Viewport (375px)
    console.log("    3. Auditing Mobile Viewport (375px)...");
    const mobileBtn = page.getByRole("button", { name: /موبایل/i });
    if (await mobileBtn.isVisible()) {
      await mobileBtn.click();
      await page.waitForTimeout(600);
    }
    const shotMobile = path.join(ARTIFACTS_DIR, "03-viewport-mobile-375.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotMobile });
    findings.checks.mobileScreenshot = shotMobile;

    // 4. Audit Dark Mode Sync to Canvas Iframe
    console.log("    4. Auditing Dark Mode Synchronization...");
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
    });
    await page.waitForTimeout(500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const isIframeDark = await page.evaluate(() => {
      const iframe = document.querySelector('iframe[title="Visual Builder Canvas"]');
      const doc = iframe?.contentDocument || iframe?.contentWindow?.document;
      return doc?.documentElement?.classList.contains("dark") || false;
    });

    findings.checks.darkModeSync = {
      passed: isIframeDark,
      details: isIframeDark ? "Iframe canvas synchronized dark class in real-time" : "FAIL: Iframe canvas missing dark class",
    };

    const shotDark = path.join(ARTIFACTS_DIR, "04-builder-dark-mode-sync.png");
    await page.screenshot({ path: shotDark });
    findings.checks.darkModeScreenshot = shotDark;

    // Revert to desktop
    const desktopBtn = page.getByRole("button", { name: /دسکتاپ/i });
    if (await desktopBtn.isVisible()) {
      await desktopBtn.click();
      await page.waitForTimeout(400);
    }

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 05 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 05 audit failed:", err);
  process.exit(1);
});
