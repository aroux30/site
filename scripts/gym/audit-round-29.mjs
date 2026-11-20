import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-29/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r29-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound23Audit() {
  console.log(`>>> [Gym Round 29: SEO Settings, Search Visibility, Content AI, Link Audit & Counter] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.91.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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
    // 1. Visit Admin SEO Settings /admin/seo/settings
    console.log("    1. Navigating to Admin SEO Settings /admin/seo/settings...");
    await page.goto(`${BASE_URL}/admin/seo/settings`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotSettings = path.join(ARTIFACTS_DIR, "01-seo-settings.png");
    await page.screenshot({ path: shotSettings });
    findings.tests.seoSettings = { shot: shotSettings };

    // 2. Visit Admin Search Visibility /admin/seo/visibility
    console.log("    2. Navigating to Admin Search Visibility /admin/seo/visibility...");
    await page.goto(`${BASE_URL}/admin/seo/visibility`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotVisibility = path.join(ARTIFACTS_DIR, "02-seo-visibility.png");
    await page.screenshot({ path: shotVisibility });
    findings.tests.searchVisibility = { shot: shotVisibility };

    // 3. Visit Admin Content AI /admin/seo/content-ai
    console.log("    3. Navigating to Admin Content AI /admin/seo/content-ai...");
    await page.goto(`${BASE_URL}/admin/seo/content-ai`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotContentAi = path.join(ARTIFACTS_DIR, "03-seo-content-ai.png");
    await page.screenshot({ path: shotContentAi });
    findings.tests.contentAi = { shot: shotContentAi };

    // 4. Visit Admin Link Audit /admin/seo/link-audit
    console.log("    4. Navigating to Admin Link Audit /admin/seo/link-audit...");
    await page.goto(`${BASE_URL}/admin/seo/link-audit`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotLinkAudit = path.join(ARTIFACTS_DIR, "04-seo-link-audit.png");
    await page.screenshot({ path: shotLinkAudit });
    findings.tests.linkAudit = { shot: shotLinkAudit };

    // 5. Visit Admin Link Counter /admin/seo/link-counter
    console.log("    5. Navigating to Admin Link Counter /admin/seo/link-counter...");
    await page.goto(`${BASE_URL}/admin/seo/link-counter`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotLinkCounter = path.join(ARTIFACTS_DIR, "05-seo-link-counter.png");
    await page.screenshot({ path: shotLinkCounter });
    findings.tests.linkCounter = { shot: shotLinkCounter };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-29]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound23Audit();
