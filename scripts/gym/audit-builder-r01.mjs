import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", "round-01", STAGE);
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
  console.log(`>>> [Builder Gym Round 01] Running Weight 1 Audit [Stage: ${STAGE}]...`);
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
    weight: "Weight 1: Studio Shell, LayersTree, Iframe Canvas (5kg)",
    checks: {},
  };

  try {
    // 1. Navigate using ?builder=1
    console.log(`    1. Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);

    // Check if Studio rendered or storefront leaked
    const studioRoot = page.locator("div.fixed.inset-0").first();
    const isStudioRendered = await studioRoot.isVisible().catch(() => false);
    const canvasFrameLocator = page.locator('iframe[title="Visual Builder Canvas"]');
    const isIframePresent = await canvasFrameLocator.count() > 0;

    findings.checks.builderQueryParam = {
      passed: isStudioRendered && isIframePresent,
      details: isStudioRendered ? "BuilderStudio rendered successfully on ?builder=1" : "FAIL: ?builder=1 did NOT trigger BuilderStudio (rendered public storefront instead)",
    };

    // Take overview screenshot
    const shotOverview = path.join(ARTIFACTS_DIR, "01-studio-fullscreen-layout.png");
    await page.screenshot({ path: shotOverview });
    findings.checks.overviewScreenshot = shotOverview;

    if (!isStudioRendered) {
      console.warn("    Studio not rendered on ?builder=1! Taking fallback screenshot.");
      return findings;
    }

    // 2. Geometric overflow check on sidebars
    console.log("    2. Checking sidebars geometric horizontal overflow...");
    const sidebars = page.locator("aside");
    const sidebarCount = await sidebars.count();
    let hasSidebarOverflow = false;
    for (let i = 0; i < sidebarCount; i++) {
      const overflow = await sidebars.nth(i).evaluate((el) => el.scrollWidth > el.clientWidth);
      if (overflow) hasSidebarOverflow = true;
    }
    findings.checks.sidebarOverflow = {
      passed: !hasSidebarOverflow,
      details: hasSidebarOverflow ? "Horizontal scroll detected in sidebars" : "Sidebars cleanly fit within width",
    };

    // 3. Switch to Layers tab and test permanent action buttons without hover
    console.log("    3. Checking LayersTree action buttons at mouse (0,0)...");
    await page.mouse.move(0, 0);
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" });
    if (await layersTabBtn.isVisible()) {
      await layersTabBtn.click();
      await page.waitForTimeout(600);
    }

    const shotLayers = path.join(ARTIFACTS_DIR, "02-layers-tree-visibility-indent.png");
    const layersPanel = page.locator("aside").first();
    await layersPanel.screenshot({ path: shotLayers });
    findings.checks.layersScreenshot = shotLayers;

    const layerRows = page.locator("[data-layer-row]");
    const rowCount = await layerRows.count();
    let hasHiddenButtons = false;
    let rtlIndentValid = true;

    for (let i = 0; i < rowCount; i++) {
      const row = layerRows.nth(i);
      const buttons = row.locator("button");
      const bCount = await buttons.count();
      for (let b = 0; b < bCount; b++) {
        const btn = buttons.nth(b);
        const cls = (await btn.getAttribute("class")) || "";
        const visible = await btn.isVisible();
        if (cls.includes("opacity-0") || !visible) {
          hasHiddenButtons = true;
        }
      }
      const depth = parseInt((await row.getAttribute("data-depth")) || "0", 10);
      if (depth > 0) {
        const parentMr = await row.evaluate((el) => {
          const parent = el.parentElement;
          return parent ? window.getComputedStyle(parent).marginRight : "0px";
        });
        if (parseFloat(parentMr) < 20) {
          rtlIndentValid = false;
        }
      }
    }

    findings.checks.layersButtons = {
      passed: !hasHiddenButtons && rowCount > 0,
      details: hasHiddenButtons ? "FAIL: Action buttons are hidden or have opacity-0" : `All action buttons on ${rowCount} rows visible without hover`,
    };
    findings.checks.layersRtlIndent = {
      passed: rtlIndentValid,
      details: rtlIndentValid ? "RTL tree indentation >= 20px verified" : "FAIL: RTL indentation insufficient",
    };

    // 4. Check Canvas Frame & Toolbar clearance
    console.log("    4. Checking Canvas toolbar clearance & empty container...");
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    let toolbarTop = 0;

    if (await firstEl.isVisible()) {
      await firstEl.click();
      await page.waitForTimeout(500);

      const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
      if (await toolbar.isVisible()) {
        toolbarTop = await toolbar.evaluate((el) => el.getBoundingClientRect().top);
      }
    }

    const shotCanvas = path.join(ARTIFACTS_DIR, "03-canvas-toolbar-clearance.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotCanvas });
    findings.checks.canvasScreenshot = shotCanvas;

    findings.checks.toolbarClearance = {
      passed: toolbarTop >= 0,
      details: toolbarTop >= 0 ? `Toolbar top position (${Math.round(toolbarTop)}px) is clear of ceiling` : `FAIL: Toolbar clipped at top (${toolbarTop}px)`,
    };

    // 5. Empty container guide check
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').or(frame.locator("text=افزودن بلوک به این بخش")).first();
    const hasGuide = await emptyGuide.isVisible().catch(() => false);
    findings.checks.emptyGuide = {
      passed: hasGuide,
      details: hasGuide ? "Empty container guide rendered with action button" : "FAIL: Empty container guide missing",
    };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Audit complete. Results saved to ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Audit script failed:", err);
  process.exit(1);
});
