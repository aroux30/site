import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-21/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r21-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound21Audit() {
  console.log(`>>> [Gym Round 21: Notices, Titles-Meta & Telegram Notify] Stage: [${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    extraHTTPHeaders: {
      "X-Forwarded-For": `10.86.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
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
    // 1. Visit Admin Notices /admin/notices
    console.log("    1. Navigating to Admin Notices /admin/notices...");
    await page.goto(`${BASE_URL}/admin/notices`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotNotices = path.join(ARTIFACTS_DIR, "01-admin-notices.png");
    await page.screenshot({ path: shotNotices });
    findings.tests.notices = { shot: shotNotices };

    // Also switch to SMS tab in notices
    const smsTab = page.locator("button[role='tab']:has-text('ارسال پیامک')");
    if (await smsTab.isVisible()) {
      await smsTab.click();
      await page.waitForTimeout(1000);
      const shotSms = path.join(ARTIFACTS_DIR, "01-b-admin-notices-sms.png");
      await page.screenshot({ path: shotSms });
      findings.tests.noticesSms = { shot: shotSms };
    }

    // 2. Visit Admin SEO Titles & Meta /admin/seo/titles-meta
    console.log("    2. Navigating to Admin SEO Titles & Meta /admin/seo/titles-meta...");
    await page.goto(`${BASE_URL}/admin/seo/titles-meta`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotTitlesMeta = path.join(ARTIFACTS_DIR, "02-seo-titles-meta.png");
    await page.screenshot({ path: shotTitlesMeta });
    findings.tests.titlesMeta = { shot: shotTitlesMeta };

    // 3. Visit Admin Telegram Notify /admin/telegram-notify
    console.log("    3. Navigating to Admin Telegram Notify /admin/telegram-notify...");
    await page.goto(`${BASE_URL}/admin/telegram-notify`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotTelegramNotify = path.join(ARTIFACTS_DIR, "03-admin-telegram-notify.png");
    await page.screenshot({ path: shotTelegramNotify });
    findings.tests.telegramNotify = { shot: shotTelegramNotify };

    // 4. Visit Admin SEO Indexing /admin/seo/indexing
    console.log("    4. Navigating to Admin SEO Indexing /admin/seo/indexing...");
    await page.goto(`${BASE_URL}/admin/seo/indexing`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const shotIndexing = path.join(ARTIFACTS_DIR, "04-seo-indexing.png");
    await page.screenshot({ path: shotIndexing });
    findings.tests.indexing = { shot: shotIndexing };

    fs.writeFileSync(path.join(ARTIFACTS_DIR, "findings.json"), JSON.stringify(findings, null, 2), "utf8");
    console.log(`>>> [OK] Saved screenshots to ${ARTIFACTS_DIR}`);
  } catch (err) {
    console.error(">>> [ERROR in audit-round-21]", err);
    throw err;
  } finally {
    await browser.close();
  }
}

runRound21Audit();
