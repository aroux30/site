import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-22/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r22-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound22Audit() {
  console.log(`>>> [Gym Round 22: Local SEO, Breadcrumbs, Image SEO & Status] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.88.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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
    // 1. Visit Admin Local SEO /admin/seo/local
    console.log("    1. Navigating to Admin Local SEO /admin/seo/local...");
    await page.goto(`${BASE_URL}/admin/seo/local`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotLocal = path.join(ARTIFACTS_DIR, "01-seo-local.png");
    await page.screenshot({ path: shotLocal });
    findings.tests.localSeo = { shot: shotLocal };

    // 2. Visit Admin Breadcrumbs /admin/seo/breadcrumbs
    console.log("    2. Navigating to Admin Breadcrumbs /admin/seo/breadcrumbs...");
    await page.goto(`${BASE_URL}/admin/seo/breadcrumbs`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotBreadcrumbs = path.join(ARTIFACTS_DIR, "02-seo-breadcrumbs.png");
    await page.screenshot({ path: shotBreadcrumbs });
    findings.tests.breadcrumbs = { shot: shotBreadcrumbs };

    // 3. Visit Admin Image SEO /admin/seo/image
    console.log("    3. Navigating to Admin Image SEO /admin/seo/image...");
    await page.goto(`${BASE_URL}/admin/seo/image`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotImageSeo = path.join(ARTIFACTS_DIR, "03-seo-image.png");
    await page.screenshot({ path: shotImageSeo });
    findings.tests.imageSeo = { shot: shotImageSeo };

    // 4. Visit Admin SEO Status /admin/seo/status
    console.log("    4. Navigating to Admin SEO Status /admin/seo/status...");
    await page.goto(`${BASE_URL}/admin/seo/status`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotStatus = path.join(ARTIFACTS_DIR, "04-seo-status.png");
    await page.screenshot({ path: shotStatus });
    findings.tests.seoStatus = { shot: shotStatus };

    // 5. Visit Admin 404 Monitor /admin/seo/404
    console.log("    5. Navigating to Admin 404 Monitor /admin/seo/404...");
    await page.goto(`${BASE_URL}/admin/seo/404`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shot404 = path.join(ARTIFACTS_DIR, "05-seo-404.png");
    await page.screenshot({ path: shot404 });
    findings.tests.seo404 = { shot: shot404 };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-22]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound22Audit();
