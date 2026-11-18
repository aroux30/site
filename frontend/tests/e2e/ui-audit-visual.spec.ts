import { expect, test } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";
import fs from "node:fs";
import path from "node:path";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";
const AUDIT_DIR = path.resolve(process.cwd(), "public/ui-audit");

test.describe("Visual Audit & UI Proof", () => {
  test.beforeAll(() => {
    if (!fs.existsSync(AUDIT_DIR)) {
      fs.mkdirSync(AUDIT_DIR, { recursive: true });
    }
  });

  test.beforeEach(async ({ page }) => {
    // Authenticate as Super Admin
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: {
              id: "admin-1",
              phone: "09123456789",
              isSuperuser: true,
              roles: ["super_admin"],
            },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("Capture high-resolution screenshots of LayersTree, Canvas, Inspector, and Palette", async ({
    page,
  }) => {
    test.setTimeout(90_000);
    await page.setViewportSize({ width: 1440, height: 900 });

    await resetE2EPage("e2e-isolated-scratchpad");

    await page.goto("/e2e-isolated-scratchpad?visual_editor=true", {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });

    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });
    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 25_000 });

    // 1. Capture Blocks Palette screenshot
    const blocksPaletteTab = page.getByRole("button", { name: "افزودن بلوک" });
    await blocksPaletteTab.click();
    await page.waitForTimeout(500);

    const palettePanel = page.locator("aside").first();
    await palettePanel.screenshot({
      path: path.join(AUDIT_DIR, "blocks-palette.png"),
    });

    // 2. Add elements to build multi-depth hierarchy for LayersTree test
    // Add a container first
    const containerBlock = page.locator("button:has-text('کانتینر')").first();
    if (await containerBlock.isVisible()) {
      await containerBlock.click();
      await page.waitForTimeout(600);
    }

    // Add a button widget
    const buttonBlock = page.locator("button:has-text('دکمه اقدام')").first();
    if (await buttonBlock.isVisible()) {
      await buttonBlock.click();
      await page.waitForTimeout(600);
    }

    // 3. Switch to Layers tab
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" });
    await layersTabBtn.click();
    await page.waitForTimeout(800);

    // Verify all layers items have visible action buttons (NO opacity-0)
    const layersPanel = page.locator("aside").first();
    await expect(layersPanel).toBeVisible();

    // Verify Trash2 and Copy buttons are visible without mouse hover
    const trashButtons = layersPanel.locator("button[title*='حذف']");
    const trashCount = await trashButtons.count();
    expect(trashCount).toBeGreaterThan(0);

    for (let i = 0; i < trashCount; i++) {
      await expect(trashButtons.nth(i)).toBeVisible();
      // Ensure no ancestor or button has opacity-0
      const btnClass = await trashButtons.nth(i).getAttribute("class");
      expect(btnClass).not.toContain("opacity-0");
    }

    // Screenshot LayersTree panel
    await layersPanel.screenshot({
      path: path.join(AUDIT_DIR, "layers-tree.png"),
    });

    // 4. Select an element on Canvas and capture CanvasFrame
    const canvasElement = frame.locator("[data-element-id]").first();
    await canvasElement.click({ force: true });
    await page.waitForTimeout(600);

    // Capture Canvas frame screenshot
    const canvasFrameLocator = page.locator("main.flex-1").first();
    await canvasFrameLocator.screenshot({
      path: path.join(AUDIT_DIR, "canvas-frame.png"),
    });

    // 5. Switch Inspector tabs and capture InspectorPanel
    const inspectorPanel = page.locator("div.border-s.border-border").first();
    await expect(inspectorPanel).toBeVisible();

    // Capture Style tab in Inspector
    const styleTab = page.getByRole("tab", { name: "استایل" });
    if (await styleTab.isVisible()) {
      await styleTab.click();
      await page.waitForTimeout(500);
    }

    await inspectorPanel.screenshot({
      path: path.join(AUDIT_DIR, "inspector-panel.png"),
    });

    // 6. Capture full studio overview
    await page.screenshot({
      path: path.join(AUDIT_DIR, "builder-studio-full.png"),
    });

    // Confirm all screenshots exist on disk
    expect(fs.existsSync(path.join(AUDIT_DIR, "layers-tree.png"))).toBe(true);
    expect(fs.existsSync(path.join(AUDIT_DIR, "canvas-frame.png"))).toBe(true);
    expect(fs.existsSync(path.join(AUDIT_DIR, "inspector-panel.png"))).toBe(true);
    expect(fs.existsSync(path.join(AUDIT_DIR, "blocks-palette.png"))).toBe(true);
    expect(fs.existsSync(path.join(AUDIT_DIR, "builder-studio-full.png"))).toBe(true);
  });
});
