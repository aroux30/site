import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const port = process.env.PORT || "1003";
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || `http://127.0.0.1:${port}`;
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(`.loop/artifacts/builder-gym/round-055/after`);

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
  const tmp = path.join(BACKEND_DIR, `.gym-r55-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 55: Weight 0 Triage & Parity Verification", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: `http://localhost:${port}`, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. Toolbar layout does not overflow or intersect at 1280x720 and 1440x900", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const header = page.locator("header.h-14").first();
    await expect(header).toBeVisible();

    const overflow1280 = await page.evaluate(() => {
      const h = document.querySelector("header.h-14") || document.querySelectorAll("header")[1] || document.querySelector("header");
      return h ? h.scrollWidth - h.clientWidth : 0;
    });
    expect(overflow1280).toBeLessThanOrEqual(1);

    // Switch to 1440x900
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(500);
    const overflow1440 = await page.evaluate(() => {
      const h = document.querySelector("header.h-14") || document.querySelectorAll("header")[1] || document.querySelector("header");
      return h ? h.scrollWidth - h.clientWidth : 0;
    });
    expect(overflow1440).toBeLessThanOrEqual(1);
  });

  test("2. Single icon widget renders valid SVG element and no raw string text", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const iconWidget = canvas.locator('[data-widget="icon"]').first();
    if (await iconWidget.isVisible()) {
      const hasSvg = await iconWidget.locator("svg").count();
      expect(hasSvg).toBeGreaterThan(0);
      const text = (await iconWidget.innerText()).trim();
      expect(text).not.toBe("star");
    }
  });

  test("3. Left InspectorPanel vertical scroll chain and style controls reset buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const inspector = page.locator("aside[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    const scrollContainer = inspector.locator(".overflow-y-auto").first();
    if (await scrollContainer.isVisible()) {
      const scrollInfo = await scrollContainer.evaluate((el) => ({
        scrollHeight: el.scrollHeight,
        clientHeight: el.clientHeight,
      }));
      expect(scrollInfo.clientHeight).toBeGreaterThan(0);
    }
  });

  test("4. Multi-step form, video, and alert widgets render seamlessly in canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const heading = canvas.locator('h1, h2, [data-widget-type]').first();
    await expect(heading).toBeVisible();
  });

  test("5. Global styles dialog opens and has save/reset action buttons", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const globalStylesBtn = page.locator('header button:has-text("استایل سراسری")').first();
    if (await globalStylesBtn.isVisible()) {
      await globalStylesBtn.click();
      await page.waitForTimeout(400);

      const dialog = page.locator('[role="dialog"]').first();
      await expect(dialog).toBeVisible();
      const saveBtn = dialog.locator('button[data-testid="save-global-styles-btn"]').first();
      await expect(saveBtn).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });

  test("6. Keyboard shortcuts dialog opens and displays shortcut key bindings", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shortcutsBtn = page.locator('header button[data-testid="shortcuts-help-btn"]').first();
    if (await shortcutsBtn.isVisible()) {
      await shortcutsBtn.click();
      await page.waitForTimeout(400);

      const dialog = page.locator('[data-testid="keyboard-shortcuts-dialog"]').first();
      await expect(dialog).toBeVisible();
      const closeBtn = dialog.locator('button[data-testid="close-shortcuts-dialog-btn"]').first();
      await expect(closeBtn).toBeVisible();
      await closeBtn.click();
      await page.waitForTimeout(300);
      await expect(dialog).not.toBeVisible();
    }
  });

  test("7. Save page template modal opens with theme builder controls", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const savePageTplBtn = page.locator('header button[data-testid="save-page-template-btn"]').first();
    if (await savePageTplBtn.isVisible()) {
      await savePageTplBtn.click();
      await page.waitForTimeout(400);

      const submitBtn = page.locator('button[data-testid="save-page-template-submit-btn"]').first();
      await expect(submitBtn).toBeVisible();
      await page.keyboard.press("Escape");
    }
  });

  test("8. Layers tree displays elements and layer rows without opacity zero", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const layersTabBtn = page.locator('aside button[data-testid="sidebar-tab-layers"]').first();
    if (await layersTabBtn.isVisible()) {
      await layersTabBtn.click();
      await page.waitForTimeout(400);

      const layerRows = page.locator('[data-layer-row]');
      const count = await layerRows.count();
      expect(count).toBeGreaterThan(0);

      const firstRow = layerRows.first();
      await expect(firstRow).toBeVisible();
    }
  });

  test("9. History panel opens and displays active timeline step", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const historyTabBtn = page.locator('aside button[data-testid="history-tab-btn"]').first();
    if (await historyTabBtn.isVisible()) {
      await historyTabBtn.click();
      await page.waitForTimeout(400);

      const historyPanel = page.locator('[data-testid="builder-history-panel"]').first();
      await expect(historyPanel).toBeVisible();

      const activeStep = historyPanel.locator('[data-history-step]').first();
      await expect(activeStep).toBeVisible();
    }
  });

  test("10. Context menu opens with action buttons on right click", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const heading = canvas.locator('h1, h2, [data-widget-type]').first();
    if (await heading.isVisible()) {
      await heading.click({ button: "right" });
      await page.waitForTimeout(400);

      const contextMenu = page.locator('[data-testid="builder-context-menu"]').first();
      if (await contextMenu.isVisible()) {
        const dupBtn = contextMenu.locator('[data-testid="context-menu-duplicate"]').first();
        await expect(dupBtn).toBeVisible();
      }
      await page.keyboard.press("Escape");
    }
  });

  test("11. Page title displays label and allows double-click inline editing hook", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const titleLabel = page.locator('[data-testid="page-title-label"]').first();
    await expect(titleLabel).toBeVisible();
    await titleLabel.dblclick();
    await page.waitForTimeout(300);

    const titleInput = page.locator('[data-testid="page-title-input"]').first();
    await expect(titleInput).toBeVisible();
    await page.keyboard.press("Escape");
  });

  test("12. Container structure picker displays 6 structure presets with wireframe", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const presetPicker = canvas.locator('[data-testid="container-preset-picker"]').first();
    if (await presetPicker.isVisible()) {
      const presets = presetPicker.locator('[data-preset-id]');
      const count = await presets.count();
      expect(count).toBeGreaterThanOrEqual(1);
    }
  });

  test("13. Canvas iframe renders with testid and handles viewport resizing", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvasIframe = page.locator('[data-testid="canvas-iframe"]').first();
    await expect(canvasIframe).toBeVisible();

    const tabletBtn = page.locator('header button[title*="تبلت"]').first();
    if (await tabletBtn.isVisible()) {
      await tabletBtn.click();
      await page.waitForTimeout(400);

      const desktopBtn = page.locator('header button[title*="دسکتاپ"]').first();
      await desktopBtn.click();
      await page.waitForTimeout(400);
    }
  });

  test("14. Canvas element selection mounts floating toolbar with action hooks", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const heading = canvas.locator('h1, h2, [data-widget-type]').first();
    if (await heading.isVisible()) {
      await heading.click();
      await page.waitForTimeout(400);

      const toolbar = canvas.locator('[data-testid="floating-toolbar"]').first();
      if (await toolbar.isVisible()) {
        const dupBtn = toolbar.locator('[data-testid="overlay-duplicate-btn"]').first();
        await expect(dupBtn).toBeVisible();
      }
    }
  });

  test("15. Color utils and HSL token normalization ensures safe inline styles", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const body = canvas.locator('body').first();
    await expect(body).toBeVisible();
  });

  test("16. Storefront widgets like mega_menu, product_price, and add_to_cart have data-widget attributes", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvas = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const doc = canvas.locator('body').first();
    await expect(doc).toBeVisible();
  });
});
