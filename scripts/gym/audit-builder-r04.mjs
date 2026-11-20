import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", "round-04", STAGE);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r04-tok-${Date.now()}.py`);
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
  console.log(`>>> [Builder Gym Round 04] Auditing Drag & Drop, Shortcuts & Templates [Stage: ${STAGE}]...`);
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
    weight: "Weight 4: Drag & Drop, Shortcuts, Global Components & Templates (35kg)",
    checks: {},
  };

  try {
    console.log(`    Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 45000 });
    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(500);

    // 1. Audit shortcuts (Copy & Paste)
    console.log("    1. Auditing Canvas Keyboard Shortcuts (Copy & Paste)...");
    const initialElementsCount = await frame.locator("[data-element-id]").count();

    // Click inside iframe to focus it
    await firstEl.click();
    await page.keyboard.press("Control+c");
    await page.waitForTimeout(300);
    await page.keyboard.press("Control+v");
    await page.waitForTimeout(600);

    const postPasteElementsCount = await frame.locator("[data-element-id]").count();
    findings.checks.copyPasteShortcut = {
      passed: postPasteElementsCount > initialElementsCount,
      initialCount: initialElementsCount,
      postPasteCount: postPasteElementsCount,
      details: postPasteElementsCount > initialElementsCount
        ? "Element copied and pasted via Ctrl+C/Ctrl+V successfully"
        : "FAIL: Ctrl+C / Ctrl+V shortcut failed when focused in canvas iframe",
    };

    const shotShortcuts = path.join(ARTIFACTS_DIR, "01-canvas-shortcuts-paste.png");
    await page.locator("div.fixed.inset-0 main").first().screenshot({ path: shotShortcuts });
    findings.checks.shortcutsScreenshot = shotShortcuts;

    // 2. Audit Undo (Ctrl+Z)
    console.log("    2. Auditing Canvas Undo Shortcut (Ctrl+Z)...");
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(600);

    const postUndoElementsCount = await frame.locator("[data-element-id]").count();
    findings.checks.undoShortcut = {
      passed: postUndoElementsCount === initialElementsCount,
      postUndoCount: postUndoElementsCount,
      details: postUndoElementsCount === initialElementsCount
        ? "Undo (Ctrl+Z) successfully restored previous element tree state"
        : `FAIL: Undo failed, elements count is ${postUndoElementsCount} vs expected ${initialElementsCount}`,
    };

    // 3. Audit Templates Sub-tab in Blocks Palette
    console.log("    3. Auditing Templates Tab in Blocks Palette...");
    const tplTabBtn = page.getByRole("button", { name: /قالب‌های من/i });
    if (await tplTabBtn.isVisible()) {
      await tplTabBtn.click();
      await page.waitForTimeout(600);
    }

    const shotTemplatesTab = path.join(ARTIFACTS_DIR, "02-palette-templates-tab.png");
    await page.locator("aside").first().screenshot({ path: shotTemplatesTab });
    findings.checks.templatesTabScreenshot = shotTemplatesTab;

    // 4. Audit Save Page Template Dialog
    console.log("    4. Auditing Save Page Template Dialog...");
    const savePageTplBtn = page.getByRole("button", { name: "ذخیره به عنوان قالب" });
    if (await savePageTplBtn.isVisible()) {
      await savePageTplBtn.click();
      await page.waitForTimeout(600);

      const shotPageTplDialog = path.join(ARTIFACTS_DIR, "03-save-page-template-dialog.png");
      const dialog = page.locator("div[role='dialog']").first();
      if (await dialog.isVisible()) {
        await dialog.screenshot({ path: shotPageTplDialog });
        findings.checks.pageTemplateDialogScreenshot = shotPageTplDialog;
      }
      await page.keyboard.press("Escape");
      await page.waitForTimeout(400);
    }

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 04 audit complete. Saved to: ${reportPath}`);
  return findings;
}

runAudit().catch((err) => {
  console.error("Round 04 audit failed:", err);
  process.exit(1);
});
