import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3100";
const STAGE = process.argv[2] || "before";
const WORKTREE_ROOT = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/lucid-cartwright-fe0984");
const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-gym", "round-12", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r12-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 12] Weight 6: Toolbar Reordering Arrows & Element Placement [Stage: ${STAGE}]...`);
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
    weight: "Weight 6: Toolbar Reordering Arrows & Element Placement (80kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstBlock = frame.locator("[data-element-id]").first();
    await firstBlock.click();
    await page.waitForTimeout(400);

    // 1. Capture Floating Toolbar with new Move Up / Move Down buttons
    console.log("    1. Capturing Floating Action Toolbar with reorder buttons...");
    const canvasMain = page.locator("div.fixed.inset-0 main").first();
    const shotToolbar = path.join(ARTIFACTS_DIR, "01-floating-toolbar-reorder-buttons.png");
    await canvasMain.screenshot({ path: shotToolbar });
    findings.checks.toolbarScreenshot = shotToolbar;

    const moveUpVisible = await frame.locator("[data-testid='move-up-btn']").first().isVisible().catch(() => false);
    const moveDownVisible = await frame.locator("[data-testid='move-down-btn']").first().isVisible().catch(() => false);
    findings.checks.moveButtons = {
      moveUp: moveUpVisible,
      moveDown: moveDownVisible,
    };

    // 2. Insert Hero & FAQ, reorder them
    console.log("    2. Inserting Hero & FAQ for reordering...");
    const patternsTab = page.locator("button:has-text('الگوها')").first();
    await patternsTab.waitFor({ state: "visible", timeout: 15000 });
    await patternsTab.click();
    await page.waitForTimeout(800);

    const heroCard = page.locator("div[data-pattern-slug='hero-banner']").first();
    await heroCard.waitFor({ state: "visible", timeout: 15000 });
    await heroCard.click();
    await page.waitForTimeout(600);

    const faqCard = page.locator("div[data-pattern-slug='faq-accordion']").first();
    await faqCard.waitFor({ state: "visible", timeout: 15000 });
    await faqCard.click();
    await page.waitForTimeout(600);

    const shotBeforeReorder = path.join(ARTIFACTS_DIR, "02-canvas-sections-before-reorder.png");
    await canvasMain.screenshot({ path: shotBeforeReorder });
    findings.checks.beforeReorderScreenshot = shotBeforeReorder;

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 12 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 12 audit failed:", err);
  process.exit(1);
});
