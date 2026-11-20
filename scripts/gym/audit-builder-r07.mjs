import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-07", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r07-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 07] Deep Visual Audit of Block Patterns (Batch 2: Patterns 8-14) [Stage: ${STAGE}]...`);
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
    weight: "Weight 2: Deep Visual Audit of Block Patterns Batch 2 (Patterns 8-14: E-Commerce, Ratings & Stats) (10kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.click();
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const canvasMain = page.locator("div.fixed.inset-0 main").first();

    // 1. Insert star-rating-display and review-histogram
    console.log("    1. Inserting star-rating-display & review-histogram...");
    const starCard = page.locator("div[data-pattern-slug='star-rating-display']").first();
    await starCard.waitFor({ state: "visible", timeout: 15000 });
    await starCard.click();
    await page.waitForTimeout(1200);

    const histCard = page.locator("div[data-pattern-slug='review-histogram']").first();
    await histCard.waitFor({ state: "visible", timeout: 15000 });
    await histCard.click();
    await page.waitForTimeout(1200);

    const shotBatch1 = path.join(ARTIFACTS_DIR, "01-pattern-star-rating-histogram.png");
    await canvasMain.screenshot({ path: shotBatch1 });
    findings.checks.ratingsScreenshot = shotBatch1;

    // Check star-rating has amber stars
    const starHeading = frame.locator("h4:has-text('★★★★☆')").first();
    await starHeading.waitFor({ state: "visible", timeout: 15000 });
    const starHeadingClasses = (await starHeading.getAttribute("class")) || "";
    findings.checks.starHeading = {
      classes: starHeadingClasses,
      hasTextAmber400: starHeadingClasses.includes("text-amber-400"),
    };

    // 2. Insert product-card-grid & text-marquee
    console.log("    2. Inserting product-card-grid & text-marquee...");
    const prodGridCard = page.locator("div[data-pattern-slug='product-card-grid']").first();
    await prodGridCard.waitFor({ state: "visible", timeout: 15000 });
    await prodGridCard.click();
    await page.waitForTimeout(1200);

    const marqueeCard = page.locator("div[data-pattern-slug='text-marquee']").first();
    await marqueeCard.waitFor({ state: "visible", timeout: 15000 });
    await marqueeCard.click();
    await page.waitForTimeout(1200);

    const shotBatch2 = path.join(ARTIFACTS_DIR, "02-pattern-products-grid-marquee.png");
    await canvasMain.screenshot({ path: shotBatch2 });
    findings.checks.productsGridMarqueeScreenshot = shotBatch2;

    // 3. Insert stats-counter, image-gallery-showcase, discount-badge-banner
    console.log("    3. Inserting stats-counter, image-gallery-showcase & discount-badge-banner...");
    const statsCard = page.locator("div[data-pattern-slug='stats-counter']").first();
    await statsCard.waitFor({ state: "visible", timeout: 15000 });
    await statsCard.click();
    await page.waitForTimeout(1200);

    const galleryCard = page.locator("div[data-pattern-slug='image-gallery-showcase']").first();
    await galleryCard.waitFor({ state: "visible", timeout: 15000 });
    await galleryCard.click();
    await page.waitForTimeout(1200);

    const discountCard = page.locator("div[data-pattern-slug='discount-badge-banner']").first();
    await discountCard.waitFor({ state: "visible", timeout: 15000 });
    await discountCard.click();
    await page.waitForTimeout(1200);

    const shotBatch3 = path.join(ARTIFACTS_DIR, "03-pattern-stats-gallery-discount.png");
    await canvasMain.screenshot({ path: shotBatch3 });
    findings.checks.statsGalleryDiscountScreenshot = shotBatch3;

    // Check discount banner heading
    const discountHeading = frame.locator("h3:has-text('تخفیف')").first();
    await discountHeading.waitFor({ state: "visible", timeout: 15000 });
    const discountHeadingClasses = (await discountHeading.getAttribute("class")) || "";
    findings.checks.discountHeading = {
      classes: discountHeadingClasses,
      hasDestructiveForeground: discountHeadingClasses.includes("text-destructive-foreground"),
    };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 07 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 07 audit failed:", err);
  process.exit(1);
});
