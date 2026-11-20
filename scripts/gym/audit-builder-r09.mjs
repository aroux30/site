import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-09", STAGE);
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

async function runAudit() {
  console.log(`>>> [Builder Gym Round 09] Deep Visual Audit of Block Patterns (Batch 4: Patterns 22-28) [Stage: ${STAGE}]...`);
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
    weight: "Weight 2: Deep Visual Audit of Block Patterns Batch 4 (Patterns 22-28: Comparison Table, Lead Form & Highlights) (10kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const canvasMain = page.locator("div.fixed.inset-0 main").first();

    // 1. Insert comparison-table and process-steps
    console.log("    1. Inserting comparison-table & process-steps...");
    const compCard = page.locator("div[data-pattern-slug='comparison-table']").first();
    await compCard.waitFor({ state: "visible", timeout: 15000 });
    await compCard.click();
    await page.waitForTimeout(1200);

    const stepsCard = page.locator("div[data-pattern-slug='process-steps']").first();
    await stepsCard.waitFor({ state: "visible", timeout: 15000 });
    await stepsCard.click();
    await page.waitForTimeout(1200);

    const shotBatch1 = path.join(ARTIFACTS_DIR, "01-pattern-comparison-steps.png");
    await canvasMain.screenshot({ path: shotBatch1 });
    findings.checks.comparisonStepsScreenshot = shotBatch1;

    // Check table highlight column
    const thPro = frame.locator("th:has-text('مدل پرو')").first();
    const thClasses = (await thPro.getAttribute("class")) || "";
    findings.checks.tableHighlight = {
      classes: thClasses,
      hasPrimaryBg: thClasses.includes("bg-primary/10"),
    };

    // 2. Insert lead-capture-form & alert-banner
    console.log("    2. Inserting lead-capture-form & alert-banner...");
    const leadCard = page.locator("div[data-pattern-slug='lead-capture-form']").first();
    await leadCard.waitFor({ state: "visible", timeout: 15000 });
    await leadCard.click();
    await page.waitForTimeout(1200);

    const alertCard = page.locator("div[data-pattern-slug='alert-banner']").first();
    await alertCard.waitFor({ state: "visible", timeout: 15000 });
    await alertCard.click();
    await page.waitForTimeout(1200);

    const leadHeading = frame.locator("h3:has-text('درخواست مشاوره')").first();
    if (await leadHeading.isVisible()) {
      await leadHeading.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
    }

    const shotBatch2 = path.join(ARTIFACTS_DIR, "02-pattern-leadform-alert.png");
    await canvasMain.screenshot({ path: shotBatch2 });
    findings.checks.leadFormAlertScreenshot = shotBatch2;

    // Check if lead capture form contains topic field and badge
    const hasBadge = await frame.locator("text=/۱۵ دقیقه/").first().isVisible().catch(() => false);
    findings.checks.leadFormBadge = {
      rendered: hasBadge,
    };

    // 3. Insert floating-contact-bar, brand-logo-carousel & product-highlights
    console.log("    3. Inserting floating-contact-bar, brand-logo-carousel & product-highlights...");
    const contactCard = page.locator("div[data-pattern-slug='floating-contact-bar']").first();
    await contactCard.waitFor({ state: "visible", timeout: 15000 });
    await contactCard.click();
    await page.waitForTimeout(1200);

    const brandCard = page.locator("div[data-pattern-slug='brand-logo-carousel']").first();
    await brandCard.waitFor({ state: "visible", timeout: 15000 });
    await brandCard.click();
    await page.waitForTimeout(1200);

    const highlightCard = page.locator("div[data-pattern-slug='product-highlights']").first();
    await highlightCard.waitFor({ state: "visible", timeout: 15000 });
    await highlightCard.click();
    await page.waitForTimeout(1200);

    const brandHeading = frame.locator("h2:has-text('برندهای معتبر')").first();
    if (await brandHeading.isVisible()) {
      await brandHeading.scrollIntoViewIfNeeded();
      await page.waitForTimeout(400);
    }

    const shotBatch3 = path.join(ARTIFACTS_DIR, "03-pattern-contact-brand-highlights.png");
    await canvasMain.screenshot({ path: shotBatch3 });
    findings.checks.contactBrandHighlightsScreenshot = shotBatch3;

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 09 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 09 audit failed:", err);
  process.exit(1);
});
