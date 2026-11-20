import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-10", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r10-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 10] Weight 6: Full Landing Page Construction & Studio Micro UX [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  const probeIp = `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}`;
  await context.setExtraHTTPHeaders({
    "X-Forwarded-For": `${probeIp}, 10.0.0.1`,
  });

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
    weight: "Weight 6: Full Landing Page Assembly & Studio Micro UX (60kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(800);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const canvasMain = page.locator("div.fixed.inset-0 main").first();

    // 1. Build Section 1: Hero Banner
    console.log("    1. Inserting Hero Banner...");
    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await heroCard.waitFor({ state: "visible", timeout: 15000 });
    await heroCard.click();
    await page.waitForTimeout(1000);

    // 2. Build Section 2: Features Grid
    console.log("    2. Inserting Feature Grid...");
    const featureCard = page.locator("div[data-pattern-slug='feature-grid']").first();
    await featureCard.waitFor({ state: "visible", timeout: 15000 });
    await featureCard.click();
    await page.waitForTimeout(1000);

    // 3. Build Section 3: Comparison Table
    console.log("    3. Inserting Comparison Table...");
    const compCard = page.locator("div[data-pattern-slug='comparison-table']").first();
    await compCard.waitFor({ state: "visible", timeout: 15000 });
    await compCard.click();
    await page.waitForTimeout(1000);

    // 4. Build Section 4: Lead Capture Form
    console.log("    4. Inserting Lead Capture Form...");
    const leadCard = page.locator("div[data-pattern-slug='lead-capture-form']").first();
    await leadCard.waitFor({ state: "visible", timeout: 15000 });
    await leadCard.click();
    await page.waitForTimeout(1000);

    // 5. Build Section 5: FAQ Accordion
    console.log("    5. Inserting FAQ Accordion...");
    const faqCard = page.locator("div[data-pattern-slug='faq-accordion']").first();
    await faqCard.waitFor({ state: "visible", timeout: 15000 });
    await faqCard.click();
    await page.waitForTimeout(1000);

    // 6. Build Section 6: CTA / Support Callout
    console.log("    6. Inserting Support Callout (CTA)...");
    const supportCard = page.locator("div[data-pattern-slug='support-callout']").first();
    await supportCard.waitFor({ state: "visible", timeout: 15000 });
    await supportCard.click();
    await page.waitForTimeout(1000);

    // Capture Hero & Features view
    const heroEl = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    if (await heroEl.isVisible()) {
      await heroEl.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
    }
    const shotLanding1 = path.join(ARTIFACTS_DIR, "01-landing-hero-features.png");
    await canvasMain.screenshot({ path: shotLanding1 });
    findings.checks.landingTopScreenshot = shotLanding1;

    // Capture Comparison & Lead Form view
    const compEl = frame.locator("h2:has-text('مقایسه مشخصات')").first();
    if (await compEl.isVisible()) {
      await compEl.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
    }
    const shotLanding2 = path.join(ARTIFACTS_DIR, "02-landing-comparison-leadform.png");
    await canvasMain.screenshot({ path: shotLanding2 });
    findings.checks.landingMiddleScreenshot = shotLanding2;

    // Capture FAQ & CTA view
    const faqEl = frame.locator("h2:has-text('پرسش‌های متداول')").first();
    if (await faqEl.isVisible()) {
      await faqEl.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
    }
    const shotLanding3 = path.join(ARTIFACTS_DIR, "03-landing-faq-support-cta.png");
    await canvasMain.screenshot({ path: shotLanding3 });
    findings.checks.landingBottomScreenshot = shotLanding3;

    // 7. Test Layers Tree reflection of 6 landing sections
    console.log("    7. Switching to Layers Tree tab...");
    const layersTab = page.locator("button:has-text('لایه‌ها')").first();
    await layersTab.waitFor({ state: "visible", timeout: 15000 });
    await layersTab.click();
    await page.waitForTimeout(600);

    const shotLayers = path.join(ARTIFACTS_DIR, "04-layers-tree-landing-sections.png");
    await page.locator("aside").first().screenshot({ path: shotLayers });
    findings.checks.layersScreenshot = shotLayers;

    // Count root section elements
    const rootCount = await frame.locator("body > div.builder-canvas-root > div[data-element-id]").count();
    findings.checks.rootSectionsCount = rootCount;

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 10 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 10 audit failed:", err);
  process.exit(1);
});
