import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-06", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r06-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 06] Deep Visual Audit of Block Patterns (Batch 1: Patterns 1-7) [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }

  const page = await context.newPage();
  page.on("console", (msg) => console.log(`[BROWSER CONSOLE ${msg.type()}]`, msg.text()));
  page.on("pageerror", (err) => console.log(`[BROWSER PAGEERROR]`, err));
  page.on("requestfailed", (req) => console.log(`[REQUEST FAILED]`, req.url(), req.failure()?.errorText));

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
    weight: "Weight 2: Deep Visual Audit of Block Patterns (Patterns 1 to 7) & Widget Custom Classes (10kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    // 1. Audit Patterns Palette List
    console.log("    1. Auditing Patterns Palette list...");
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();
    await page.waitForTimeout(1000);

    const shotPalette = path.join(ARTIFACTS_DIR, "01-patterns-palette-list.png");
    await page.locator("aside").first().screenshot({ path: shotPalette });
    findings.checks.patternsPaletteScreenshot = shotPalette;

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    // 2. Insert Hero Banner & Feature Grid
    console.log("    2. Inserting hero-banner and feature-grid...");
    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await heroCard.waitFor({ state: "visible", timeout: 10000 });
    await heroCard.click();
    await page.waitForTimeout(1200);

    const featureCard = page.locator("div[data-pattern-slug='feature-grid']").first();
    await featureCard.waitFor({ state: "visible", timeout: 10000 });
    await featureCard.click();
    await page.waitForTimeout(1200);

    const canvasMain = page.locator("div.fixed.inset-0 main").first();
    const shotBatch1 = path.join(ARTIFACTS_DIR, "02-pattern-hero-and-features.png");
    await canvasMain.screenshot({ path: shotBatch1 });
    findings.checks.heroAndFeaturesScreenshot = shotBatch1;

    // Check custom classes on hero heading inside iframe
    const heroHeading = frame.locator("h1:has-text('کالکشن جدید رسید')").first();
    await heroHeading.waitFor({ state: "visible", timeout: 10000 });
    const heroHeadingClasses = await heroHeading.getAttribute("class");
    findings.checks.heroHeadingClasses = {
      classes: heroHeadingClasses,
      hasText3xl: heroHeadingClasses?.includes("text-3xl") || false,
      hasMdText5xl: heroHeadingClasses?.includes("md:text-5xl") || false,
    };

    // 3. Insert Product Showcase & Testimonials
    console.log("    3. Inserting product-showcase-cta and testimonials...");
    const showcaseCard = page.locator("div[data-pattern-slug='product-showcase-cta']").first();
    await showcaseCard.waitFor({ state: "visible", timeout: 10000 });
    await showcaseCard.click();
    await page.waitForTimeout(1200);

    const testimonialsCard = page.locator("div[data-pattern-slug='testimonials']").first();
    await testimonialsCard.waitFor({ state: "visible", timeout: 10000 });
    await testimonialsCard.click();
    await page.waitForTimeout(1200);

    const shotBatch2 = path.join(ARTIFACTS_DIR, "03-pattern-product-showcase-testimonials.png");
    await canvasMain.screenshot({ path: shotBatch2 });
    findings.checks.showcaseAndTestimonialsScreenshot = shotBatch2;

    // 4. Insert FAQ Accordion, Image-Text and Countdown Offer
    console.log("    4. Inserting faq-accordion, image-text and countdown-offer...");
    const faqCard = page.locator("div[data-pattern-slug='faq-accordion']").first();
    await faqCard.waitFor({ state: "visible", timeout: 10000 });
    await faqCard.click();
    await page.waitForTimeout(1200);

    const imageTextCard = page.locator("div[data-pattern-slug='image-text']").first();
    await imageTextCard.waitFor({ state: "visible", timeout: 10000 });
    await imageTextCard.click();
    await page.waitForTimeout(1200);

    const countdownCard = page.locator("div[data-pattern-slug='countdown-offer']").first();
    await countdownCard.waitFor({ state: "visible", timeout: 10000 });
    await countdownCard.click();
    await page.waitForTimeout(1200);

    const shotBatch3 = path.join(ARTIFACTS_DIR, "04-pattern-faq-image-countdown.png");
    await canvasMain.screenshot({ path: shotBatch3 });
    findings.checks.faqImageCountdownScreenshot = shotBatch3;

    // Check countdown heading color override
    const countdownHeading = frame.locator("h3:has-text('مهلت:')").first();
    let countdownHeadingClasses = "";
    if (await countdownHeading.isVisible()) {
      countdownHeadingClasses = (await countdownHeading.getAttribute("class")) || "";
    }
    findings.checks.countdownHeadingClasses = {
      classes: countdownHeadingClasses,
      hasTextPrimary: countdownHeadingClasses.includes("text-primary"),
    };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 06 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 06 audit failed:", err);
  process.exit(1);
});
