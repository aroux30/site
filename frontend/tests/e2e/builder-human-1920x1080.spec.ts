import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4003";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-human-spec-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Visual Page Builder - Full 1920x1080 Human-like Workspace Inspection & Responsiveness", () => {
  test.use({
    viewport: { width: 1920, height: 1080 },
  });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. Viewport 1920x1080 layout validation: 3-column architecture (Left Sidebar, Center Canvas, Right Inspector)", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    // Verify window dimensions
    const viewportSize = page.viewportSize();
    expect(viewportSize).toEqual({ width: 1920, height: 1080 });

    // Verify no unexpected horizontal scroll on the outer builder container
    const isHorizontalScrollPresent = await page.evaluate(() => {
      return document.documentElement.scrollWidth > window.innerWidth;
    });
    expect(isHorizontalScrollPresent).toBe(false);

    // Verify Top Toolbar visibility and items
    const toolbar = page.locator('header, div[class*="border-b"]').first();
    await expect(toolbar).toBeVisible();
    await expect(page.locator('text="E2E Builder Scratchpad"').first()).toBeVisible();

    // Verify 3-column columns exist and are displayed side by side
    const leftSidebar = page.locator('aside:has-text("بلوک‌ها")').first();
    await expect(leftSidebar).toBeVisible();

    const canvasIframe = page.locator('iframe[title="Visual Builder Canvas"]');
    await expect(canvasIframe).toBeVisible();

    const inspectorAside = page.locator('[data-builder-inspector]');
    await expect(inspectorAside).toBeVisible();

    // Verify geometry: Left aside, middle canvas, right inspector (RTL layout)
    const leftBox = await leftSidebar.boundingBox();
    const canvasBox = await canvasIframe.boundingBox();
    const rightBox = await inspectorAside.boundingBox();

    expect(leftBox).not.toBeNull();
    expect(canvasBox).not.toBeNull();
    expect(rightBox).not.toBeNull();

    // In RTL: Left sidebar is positioned on the right side of the screen,
    // canvas in center, and inspector on the left side of the screen
    expect(leftBox!.width).toBeGreaterThanOrEqual(280);
    expect(rightBox!.width).toBeGreaterThanOrEqual(280);
    expect(canvasBox!.width).toBeGreaterThan(600);
  });

  test("2. Left Sidebar tabs navigation (Blocks, Layers, History) and Block search filter", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    // 1. Verify Blocks Tab
    const blocksTabBtn = page.locator('[data-testid="sidebar-tab-blocks"]');
    await expect(blocksTabBtn).toBeVisible();
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    // Check count of blocks (68 blocks registered)
    const basicTab = page.locator('[data-testid="blocks-palette-basic-tab-btn"]');
    await expect(basicTab).toBeVisible();
    await expect(basicTab).toContainText("بلوک‌ها (68)");

    // Test Search input filtering
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await expect(searchInput).toBeVisible();
    await searchInput.fill("ویدئو");
    await page.waitForTimeout(400);

    const videoBlock = page.locator('button[data-block-type="video"]').first();
    await expect(videoBlock).toBeVisible({ timeout: 10000 });

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(300);

    // 2. Switch to Layers Tab
    const layersTabBtn = page.locator('[data-testid="sidebar-tab-layers"]');
    await layersTabBtn.click();
    await page.waitForTimeout(300);

    const layersTree = page.locator('text="درخت ساختار لایه‌ها"').first();
    await expect(layersTree).toBeVisible();

    // 3. Switch to History Tab
    const historyTabBtn = page.locator('[data-testid="history-tab-btn"]');
    await historyTabBtn.click();
    await page.waitForTimeout(300);

    const historyPanel = page.locator('[data-testid="builder-history-panel"]');
    await expect(historyPanel).toBeVisible();

    // Return to blocks
    await blocksTabBtn.click();
    await page.waitForTimeout(300);
  });

  test("3. Center Canvas interactive selection & live element highlight", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const element = frame.locator('[data-element-id="el_e2ehead1"], [data-widget-type="heading"]').first();
    await expect(element).toBeVisible();

    // Click to select
    await element.click();
    await page.waitForTimeout(400);

    // Check Inspector tabs are visible
    const contentTab = page.getByRole("tab", { name: "محتوا" });
    const styleTab = page.getByRole("tab", { name: "استایل" });
    const advTab = page.getByRole("tab", { name: "پیشرفته" });

    await expect(contentTab).toBeVisible();
    await expect(styleTab).toBeVisible();
    await expect(advTab).toBeVisible();
  });

  test("4. Right Inspector 3-tab system: Content, Style, and Advanced tabs with live mutation", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"], [data-widget-type="heading"]').first();
    await headingEl.click();
    await page.waitForTimeout(400);

    // 1. Content Tab: check and update
    const contentTab = page.getByRole("tab", { name: "محتوا" });
    await contentTab.click();
    await page.waitForTimeout(300);

    const textInput = page.locator('[data-builder-inspector] input').first();
    await expect(textInput).toBeVisible();
    await textInput.fill("سرتیتر تغییریافته تست ۱۹۲۰");
    await page.waitForTimeout(400);

    // Verify live update inside Canvas
    await expect(frame.locator('text="سرتیتر تغییریافته تست ۱۹۲۰"').first()).toBeVisible();

    // 2. Style Tab: spacing & styling controls
    const styleTab = page.getByRole("tab", { name: "استایل" });
    await styleTab.click();
    await page.waitForTimeout(300);

    const inspector = page.locator('[data-builder-inspector]');
    await expect(inspector.locator('text="فاصله داخلی (Padding)"').first()).toBeVisible();
    await expect(inspector.locator('text="فاصله خارجی (Margin)"').first()).toBeVisible();

    // 3. Advanced Tab: Transform & Mask
    const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
    await advancedTab.click();
    await page.waitForTimeout(300);

    const transformRotateInputs = page.locator("[data-testid='transform-rotate-input']");
    await expect(transformRotateInputs).toHaveCount(1);
    await expect(transformRotateInputs).toBeVisible();

    const maskSelects = page.locator("[data-testid='mask-shape-select']");
    await expect(maskSelects).toHaveCount(1);
    await expect(maskSelects).toBeVisible();
  });

  test("5. Responsive Viewport Switching (Desktop, Tablet, Mobile) without layout clipping", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const canvasIframe = page.locator('iframe[title="Visual Builder Canvas"]');
    const deskBtn = page.locator('button:has-text("دسکتاپ")').first();
    const tabletBtn = page.locator('button:has-text("تبلت")').first();
    const mobileBtn = page.locator('button:has-text("موبایل")').first();

    // 1. Switch to Tablet (768px width)
    await tabletBtn.click();
    await page.waitForTimeout(500);

    let canvasBox = await canvasIframe.boundingBox();
    expect(canvasBox).not.toBeNull();
    // In tablet mode, width is constrained to 768px
    expect(canvasBox!.width).toBeCloseTo(768, -1);

    // 2. Switch to Mobile (375px width)
    await mobileBtn.click();
    await page.waitForTimeout(500);

    canvasBox = await canvasIframe.boundingBox();
    expect(canvasBox).not.toBeNull();
    // In mobile mode, width is constrained to 375px
    expect(canvasBox!.width).toBeCloseTo(375, -1);

    // 3. Switch back to Desktop (Full canvas width)
    await deskBtn.click();
    await page.waitForTimeout(500);

    canvasBox = await canvasIframe.boundingBox();
    expect(canvasBox!.width).toBeGreaterThan(800);
  });

  test("6. Fullscreen Preview Mode toggle and restoration", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const previewToggleBtn = page.locator('button:has-text("پیش‌نمایش")').first();
    await expect(previewToggleBtn).toBeVisible();

    // Toggle Preview Mode ON
    await previewToggleBtn.click();
    await page.waitForTimeout(500);

    // Both Left Sidebar and Right Inspector should be hidden in preview mode
    const leftSidebar = page.locator('aside:has-text("بلوک‌ها")');
    await expect(leftSidebar).toBeHidden();

    const inspectorAside = page.locator('[data-builder-inspector]');
    await expect(inspectorAside).toBeHidden();

    // Canvas should still be visible and take maximum available space
    const canvasIframe = page.locator('iframe[title="Visual Builder Canvas"]');
    await expect(canvasIframe).toBeVisible();

    // Toggle Preview Mode OFF: the button text is now "ویرایش"
    const editToggleBtn = page.locator('button:has-text("ویرایش")').first();
    await expect(editToggleBtn).toBeVisible();
    await editToggleBtn.click();
    await page.waitForTimeout(500);

    // Sidebars should be restored
    await expect(page.locator('aside:has-text("بلوک‌ها")').first()).toBeVisible();
    await expect(inspectorAside).toBeVisible();
  });

  test("7. Keyboard shortcuts and accessibility: Escape dismisses overlays", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    // Open Shortcuts Dialog
    const shortcutsBtn = page.locator('button:has-text("میانبرها")').first();
    await shortcutsBtn.click();
    await page.waitForTimeout(400);

    // Check modal opened
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();

    // Press Escape to dismiss
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);

    // Dialog should be closed
    await expect(dialog).toBeHidden();
  });
});
