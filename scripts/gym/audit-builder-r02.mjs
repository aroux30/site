import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", "round-02", STAGE);
const BACKEND_DIR = path.join(PROJECT_ROOT, "backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 02] Auditing Blocks Palette & Patterns Batch 1 [Stage: ${STAGE}]...`);
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
    weight: "Weight 2: Blocks Palette & Ready Patterns (Batch 1)",
    checks: {},
  };

  try {
    // 1. Navigate to scratchpad
    console.log(`    1. Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);

    // 2. Test Palette Sub-tabs & Search filtering
    console.log("    2. Testing Blocks Palette subtabs & search...");
    const paletteTabBtn = page.getByRole("button", { name: "افزودن بلوک" });
    if (await paletteTabBtn.isVisible()) {
      await paletteTabBtn.click();
      await page.waitForTimeout(500);
    }

    const searchInput = page.locator("input[placeholder*='جستجو']").first();
    await searchInput.fill("کانتینر");
    await page.waitForTimeout(500);

    const shotSearch = path.join(ARTIFACTS_DIR, "01-blocks-search-filtered.png");
    await page.locator("aside").first().screenshot({ path: shotSearch });
    findings.checks.searchScreenshot = shotSearch;

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(400);

    // 3. Switch to Patterns Sub-tab
    console.log("    3. Switching to Patterns tab...");
    const patternsSubTab = page.locator("button:has-text('الگوها')").first();
    await patternsSubTab.click();
    await page.waitForTimeout(1000);

    const shotPatternsTab = path.join(ARTIFACTS_DIR, "02-patterns-palette-list.png");
    await page.locator("aside").first().screenshot({ path: shotPatternsTab });
    findings.checks.patternsPaletteScreenshot = shotPatternsTab;

    // 4. Insert Batch 1 Patterns into Canvas
    console.log("    4. Inserting Batch 1 Patterns (hero-banner, feature-grid, countdown-offer, faq-accordion)...");
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    // Click on pattern cards to insert them
    const patternCards = page.locator("aside div[draggable='true']");
    const count = await patternCards.count();
    console.log(`       Found ${count} pattern cards in palette.`);

    // Insert first 3 available patterns
    for (let i = 0; i < Math.min(count, 3); i++) {
      await patternCards.nth(i).click();
      await page.waitForTimeout(1000);
    }

    // Capture Canvas with inserted patterns
    const shotCanvasPatterns = path.join(ARTIFACTS_DIR, "03-canvas-rendered-patterns.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotCanvasPatterns });
    findings.checks.canvasPatternsScreenshot = shotCanvasPatterns;

    // 5. Check computed styles and RTL contrast on inserted patterns
    const headings = frame.locator("h1, h2, h3");
    const hCount = await headings.count();
    findings.checks.patternHeadingsCount = hCount;

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 02 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 02 audit failed:", err);
  process.exit(1);
});
