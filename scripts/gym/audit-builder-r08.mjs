import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-08", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r08-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 08] Deep Visual Audit of Block Patterns (Batch 3: Patterns 15-21) [Stage: ${STAGE}]...`);
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
    weight: "Weight 2: Deep Visual Audit of Block Patterns Batch 3 (Patterns 15-21: Pricing, Author Bio & Quotes) (10kg)",
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

    // 1. Insert mega-menu-categories and pricing-table
    console.log("    1. Inserting mega-menu-categories & pricing-table...");
    const megaMenuCard = page.locator("div[data-pattern-slug='mega-menu-categories']").first();
    await megaMenuCard.waitFor({ state: "visible", timeout: 15000 });
    await megaMenuCard.click();
    await page.waitForTimeout(1200);

    const pricingCard = page.locator("div[data-pattern-slug='pricing-table']").first();
    await pricingCard.waitFor({ state: "visible", timeout: 15000 });
    await pricingCard.click();
    await page.waitForTimeout(1200);

    const shotBatch1 = path.join(ARTIFACTS_DIR, "01-pattern-megamenu-pricing.png");
    await canvasMain.screenshot({ path: shotBatch1 });
    findings.checks.megamenuPricingScreenshot = shotBatch1;

    // Check if plan 2 description is rendered in pricing table
    const plan2Desc = frame.locator("text=/بهترین انتخاب برای تیم‌ها/").first();
    const hasPlan2Desc = await plan2Desc.isVisible().catch(() => false);
    findings.checks.pricingPlan2Desc = {
      rendered: hasPlan2Desc,
    };

    // 2. Insert price-list and icon-box-grid
    console.log("    2. Inserting price-list & icon-box-grid...");
    const priceListCard = page.locator("div[data-pattern-slug='price-list']").first();
    await priceListCard.waitFor({ state: "visible", timeout: 15000 });
    await priceListCard.click();
    await page.waitForTimeout(1200);

    const iconBoxCard = page.locator("div[data-pattern-slug='icon-box-grid']").first();
    await iconBoxCard.waitFor({ state: "visible", timeout: 15000 });
    await iconBoxCard.click();
    await page.waitForTimeout(1200);

    const shotBatch2 = path.join(ARTIFACTS_DIR, "02-pattern-pricelist-iconbox.png");
    await canvasMain.screenshot({ path: shotBatch2 });
    findings.checks.priceListIconBoxScreenshot = shotBatch2;

    // 3. Insert author-bio, pull-quote and support-callout
    console.log("    3. Inserting author-bio, pull-quote & support-callout...");
    const bioCard = page.locator("div[data-pattern-slug='author-bio']").first();
    await bioCard.waitFor({ state: "visible", timeout: 15000 });
    await bioCard.click();
    await page.waitForTimeout(1200);

    const quoteCard = page.locator("div[data-pattern-slug='pull-quote']").first();
    await quoteCard.waitFor({ state: "visible", timeout: 15000 });
    await quoteCard.click();
    await page.waitForTimeout(1200);

    const supportCard = page.locator("div[data-pattern-slug='support-callout']").first();
    await supportCard.waitFor({ state: "visible", timeout: 15000 });
    await supportCard.click();
    await page.waitForTimeout(1200);

    const shotBatch3 = path.join(ARTIFACTS_DIR, "03-pattern-bio-quote-support.png");
    await canvasMain.screenshot({ path: shotBatch3 });
    findings.checks.bioQuoteSupportScreenshot = shotBatch3;

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 08 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 08 audit failed:", err);
  process.exit(1);
});
