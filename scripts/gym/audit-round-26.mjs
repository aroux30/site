import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-26/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r26-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound26Audit() {
  console.log(`>>> [Gym Round 26: Data Exchange, Export, FAQ, Reviews & Reports] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.97.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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
    // 1. Visit Admin Data Exchange (Import) /admin/data-exchange
    console.log("    1. Navigating to Admin Data Exchange /admin/data-exchange...");
    await page.goto(`${BASE_URL}/admin/data-exchange`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotDataExchange = path.join(ARTIFACTS_DIR, "01-admin-data-exchange.png");
    await page.screenshot({ path: shotDataExchange });
    findings.tests.dataExchange = { shot: shotDataExchange };

    // 2. Visit Admin Data Exchange Export /admin/data-exchange/export
    console.log("    2. Navigating to Admin Data Exchange Export /admin/data-exchange/export...");
    await page.goto(`${BASE_URL}/admin/data-exchange/export`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotExport = path.join(ARTIFACTS_DIR, "02-admin-data-exchange-export.png");
    await page.screenshot({ path: shotExport });
    findings.tests.export = { shot: shotExport };

    // 3. Visit Admin FAQ /admin/faq
    console.log("    3. Navigating to Admin FAQ /admin/faq...");
    await page.goto(`${BASE_URL}/admin/faq`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotFaq = path.join(ARTIFACTS_DIR, "03-admin-faq.png");
    await page.screenshot({ path: shotFaq });
    findings.tests.faq = { shot: shotFaq };

    // 4. Visit Admin Reviews /admin/reviews
    console.log("    4. Navigating to Admin Reviews /admin/reviews...");
    await page.goto(`${BASE_URL}/admin/reviews`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotReviews = path.join(ARTIFACTS_DIR, "04-admin-reviews.png");
    await page.screenshot({ path: shotReviews });
    findings.tests.reviews = { shot: shotReviews };

    // 5. Visit Admin Reports /admin/reports
    console.log("    5. Navigating to Admin Reports /admin/reports...");
    await page.goto(`${BASE_URL}/admin/reports`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotReports = path.join(ARTIFACTS_DIR, "05-admin-reports.png");
    await page.screenshot({ path: shotReports });
    findings.tests.reports = { shot: shotReports };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-26]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound26Audit();
