import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-25/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r25-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound25Audit() {
  console.log(`>>> [Gym Round 25: Permalinks, Widgets, Automation, Audit & BI Periodic] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.95.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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
    // 1. Visit Admin Permalinks /admin/settings/permalink
    console.log("    1. Navigating to Admin Permalinks /admin/settings/permalink...");
    await page.goto(`${BASE_URL}/admin/settings/permalink`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotPermalinks = path.join(ARTIFACTS_DIR, "01-admin-permalinks.png");
    await page.screenshot({ path: shotPermalinks });
    findings.tests.permalinks = { shot: shotPermalinks };

    // 2. Visit Admin Widgets /admin/widgets
    console.log("    2. Navigating to Admin Widgets /admin/widgets...");
    await page.goto(`${BASE_URL}/admin/widgets`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotWidgets = path.join(ARTIFACTS_DIR, "02-admin-widgets.png");
    await page.screenshot({ path: shotWidgets });
    findings.tests.widgets = { shot: shotWidgets };

    // 3. Visit Admin Automation /admin/automation
    console.log("    3. Navigating to Admin Automation /admin/automation...");
    await page.goto(`${BASE_URL}/admin/automation`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotAutomation = path.join(ARTIFACTS_DIR, "03-admin-automation.png");
    await page.screenshot({ path: shotAutomation });
    findings.tests.automation = { shot: shotAutomation };

    // 4. Visit Admin Audit /admin/audit
    console.log("    4. Navigating to Admin Audit /admin/audit...");
    await page.goto(`${BASE_URL}/admin/audit`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotAudit = path.join(ARTIFACTS_DIR, "04-admin-audit.png");
    await page.screenshot({ path: shotAudit });
    findings.tests.audit = { shot: shotAudit };

    // 5. Visit Admin BI /admin/bi
    console.log("    5. Navigating to Admin BI /admin/bi...");
    await page.goto(`${BASE_URL}/admin/bi`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const shotBi = path.join(ARTIFACTS_DIR, "05-admin-bi.png");
    await page.screenshot({ path: shotBi });
    findings.tests.bi = { shot: shotBi };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-25]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound25Audit();
