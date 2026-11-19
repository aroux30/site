import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-02/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r02-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound02Audit() {
  console.log(`>>> [Gym Round 02: 10kg] Auditing Visual Builder Controls [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09123456789", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  const networkErrors = [];
  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    tests: {},
    consoleErrors,
    networkErrors,
  };

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push({ url: page.url(), text: msg.text() });
    }
  });

  page.on("response", (res) => {
    if (res.status() >= 400 && !res.url().includes("favicon")) {
      networkErrors.push({ url: res.url(), status: res.status() });
    }
  });

  try {
    console.log("    1. Navigating to Builder Studio...");
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, {
      waitUntil: "domcontentloaded",
      timeout: 45000,
    });
    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    // ── Test 1: BlocksPalette Tabs & Search ────────────────────────────────
    console.log("    2. Testing BlocksPalette sub-tabs (Patterns & Templates)...");
    const blocksTab = page.getByRole("button", { name: "افزودن بلوک" });
    await blocksTab.click();
    await page.waitForTimeout(500);

    // Click Patterns sub-tab
    const patternsSubTab = page.locator("button:has-text('الگوها')").first();
    if (await patternsSubTab.isVisible()) {
      await patternsSubTab.click();
      await page.waitForTimeout(800);
      const shotPatterns = path.join(ARTIFACTS_DIR, "01-blocks-palette-patterns.png");
      await page.locator("aside").first().screenshot({ path: shotPatterns });
      findings.tests.patternsTab = { shot: shotPatterns, visible: true };
    }

    // Click Templates sub-tab
    const templatesSubTab = page.locator("button:has-text('قالب‌های من')").first();
    if (await templatesSubTab.isVisible()) {
      await templatesSubTab.click();
      await page.waitForTimeout(800);
      const shotTemplates = path.join(ARTIFACTS_DIR, "02-blocks-palette-templates.png");
      await page.locator("aside").first().screenshot({ path: shotTemplates });
      findings.tests.templatesTab = { shot: shotTemplates, visible: true };
    }

    // Return to Basic Blocks
    const basicSubTab = page.locator("button:has-text('بلوک‌ها')").first();
    if (await basicSubTab.isVisible()) {
      await basicSubTab.click();
      await page.waitForTimeout(500);
    }

    // ── Test 2: Inspector Panel Tabs & Inputs ─────────────────────────────
    console.log("    3. Testing Inspector Panel tabs (Content, Style, Advanced)...");
    const canvasElement = frame.locator("[data-element-id]").first();
    if (await canvasElement.isVisible()) {
      await canvasElement.click();
      await page.waitForTimeout(600);

      const inspector = page.locator("div.border-s.border-border").first();

      // Content Tab
      const contentTab = page.getByRole("tab", { name: "محتوا" });
      if (await contentTab.isVisible()) {
        await contentTab.click();
        await page.waitForTimeout(400);
        const shotContent = path.join(ARTIFACTS_DIR, "03-inspector-content-tab.png");
        await inspector.screenshot({ path: shotContent });
        findings.tests.inspectorContent = { shot: shotContent, visible: true };
      }

      // Style Tab
      const styleTab = page.getByRole("tab", { name: "استایل" });
      if (await styleTab.isVisible()) {
        await styleTab.click();
        await page.waitForTimeout(400);
        const shotStyle = path.join(ARTIFACTS_DIR, "04-inspector-style-tab.png");
        await inspector.screenshot({ path: shotStyle });
        findings.tests.inspectorStyle = { shot: shotStyle, visible: true };
      }

      // Advanced Tab
      const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
      if (await advancedTab.isVisible()) {
        await advancedTab.click();
        await page.waitForTimeout(400);
        const shotAdvanced = path.join(ARTIFACTS_DIR, "05-inspector-advanced-tab.png");
        await inspector.screenshot({ path: shotAdvanced });
        findings.tests.inspectorAdvanced = { shot: shotAdvanced, visible: true };
      }

      // Capture floating toolbar on selected element
      const shotCanvasSelected = path.join(ARTIFACTS_DIR, "07-canvas-element-selected.png");
      await page.locator("main.flex-1").first().screenshot({ path: shotCanvasSelected });
      findings.tests.canvasSelected = { shot: shotCanvasSelected };
    }

    // ── Test 3: Global Styles Modal / Popover ─────────────────────────────
    console.log("    4. Testing Global Styles dialog in studio header...");
    const globalStylesBtn = page.getByRole("button", { name: "استایل سراسری" });
    if (await globalStylesBtn.isVisible()) {
      await globalStylesBtn.click();
      await page.waitForTimeout(600);
      const shotGlobal = path.join(ARTIFACTS_DIR, "06-global-styles-dialog.png");
      await page.screenshot({ path: shotGlobal });
      findings.tests.globalStyles = { shot: shotGlobal, opened: true };

      // Close modal / dialog if open
      const closeBtn = page.locator("button[aria-label='Close'], button:has-text('بستن')").first();
      if (await closeBtn.isVisible()) {
        await closeBtn.click();
        await page.waitForTimeout(300);
      } else {
        await page.keyboard.press("Escape");
        await page.waitForTimeout(300);
      }
    }

    // ── Test 4: Undo / Redo & Draft Save & Reload ─────────────────────────
    console.log("    5. Testing Draft Save & Reload persistence...");
    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    if (await draftSaveBtn.isVisible()) {
      await draftSaveBtn.click();
      await page.waitForTimeout(1000);
      findings.tests.draftSave = { clicked: true };
    }

    // Reload page to verify persistence
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);
    const canvasAfterReload = frame.locator("[data-element-id]").first();
    const isRestored = await canvasAfterReload.isVisible().catch(() => false);
    findings.tests.reloadPersistence = { isRestored };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 02 audit complete. Saved to: ${reportPath}`);
}

runRound02Audit().catch((err) => {
  console.error("Round 02 audit failure:", err);
  process.exit(1);
});
