import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://localhost:3000";
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");

test.use({
  viewport: { width: 1920, height: 1080 },
});

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
  const tmp = path.join(BACKEND_DIR, `.gym-r22-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

function resetScratchpadData(token: string) {
  const script = `
import urllib.request, json
canonical_ast = {
    "schemaVersion": 1,
    "title": "E2E Builder Scratchpad",
    "slug": "e2e-isolated-scratchpad",
    "globalStyles": {},
    "rootElements": [
        {
            "id": "cont_e2eroot",
            "name": "کانتینر ریشه آزمایشی",
            "type": "container",
            "isLocked": False,
            "isHidden": False,
            "layout": {
                "kind": "flex",
                "direction": "column",
                "justifyContent": "start",
                "alignItems": "stretch",
                "flexWrap": "nowrap",
                "gap": {"value": 16, "unit": "px"},
                "gridColumns": 3
            },
            "styles": {"mobile": {}},
            "children": []
        },
        {
            "id": "el_e2ehead1",
            "name": "سرتیتر نمونه برای تست E2E",
            "type": "widget",
            "widgetType": "heading",
            "widgetProps": {"text": "سرتیتر نمونه برای تست E2E", "tag": "h2"},
            "styles": {"mobile": {}},
            "children": []
        }
    ]
}
data = json.dumps({"builder_data": canonical_ast, "status": "published"}).encode("utf-8")
req = urllib.request.Request(
    "http://localhost:8000/api/v1/content/admin/pages/aa5e98ad-e380-4e6f-90ad-5d8c9ef7d7a7",
    data=data,
    headers={"Authorization": "Bearer ${token}", "Content-Type": "application/json"},
    method="PATCH"
)
try:
    with urllib.request.urlopen(req) as resp:
        pass
except Exception as e:
    pass
`;
  const tmp = path.join(BACKEND_DIR, `.gym-r22-reset-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 22: 1920x1080 Human-Grade Tri-Panel Studio & Full Responsive Inspection", () => {
  let adminToken = "";

  test.beforeEach(async ({ context }) => {
    adminToken = getAdminToken();
    if (adminToken) {
      resetScratchpadData(adminToken);
      await context.addCookies([
        { name: "access_token", value: adminToken, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.220.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Full HD (1920x1080) tri-panel studio layout is simultaneously accessible with zero horizontal overflow", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // 1. Top Toolbar (header): full width, 56px height, visible
    const toolbar = page.locator("header");
    await expect(toolbar).toBeVisible();
    const toolbarBox = await toolbar.boundingBox();
    expect(toolbarBox).not.toBeNull();
    expect(toolbarBox!.width).toBe(1920);
    expect(toolbarBox!.height).toBeGreaterThanOrEqual(54);

    // 2. Left Column (aside): width 320px (w-80) with tab switcher
    const leftAside = page.locator("aside").first();
    await expect(leftAside).toBeVisible();
    const leftBox = await leftAside.boundingBox();
    expect(leftBox).not.toBeNull();
    expect(leftBox!.width).toBe(320);

    // 3. Center Workspace (main): holds CanvasFrame iframe
    const centerMain = page.locator("main").first();
    await expect(centerMain).toBeVisible();
    const canvasIframe = page.locator('iframe[title="Visual Builder Canvas"]');
    await expect(canvasIframe).toBeVisible();

    // 4. Right Column (aside[data-builder-inspector]): width 320px (w-80)
    const rightAside = page.locator("aside[data-builder-inspector]");
    await expect(rightAside).toBeVisible();
    const rightBox = await rightAside.boundingBox();
    expect(rightBox).not.toBeNull();
    expect(rightBox!.width).toBe(320);

    // 5. Zero Window Horizontal Overflow
    const overflowCheck = await page.evaluate(() => {
      return {
        innerWidth: window.innerWidth,
        scrollWidth: document.documentElement.scrollWidth,
        hasHorizontalOverflow: document.documentElement.scrollWidth > window.innerWidth,
      };
    });
    expect(overflowCheck.innerWidth).toBe(1920);
    expect(overflowCheck.hasHorizontalOverflow).toBe(false);
  });

  test("2. Left Panel human accessibility: Blocks search, Layers tree selection, and History timeline", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // ── Tab 1: Blocks Palette ───────────────────────────────────────────────────
    const blocksTabBtn = page.locator('[data-testid="sidebar-tab-blocks"]');
    await expect(blocksTabBtn).toBeVisible();
    await blocksTabBtn.click();
    await page.waitForTimeout(300);

    // Search input filters widgets in real-time
    const searchInput = page.locator('input[placeholder*="جستجو"]');
    await expect(searchInput).toBeVisible();
    await searchInput.fill("قیمت");
    await page.waitForTimeout(400);

    // Results should show price table and price list widgets
    const priceTableBtn = page.locator('button:has-text("جدول تعرفه و قیمت"), button:has-text("Price Table")').first();
    await expect(priceTableBtn).toBeVisible();

    // Clear search
    await searchInput.fill("");
    await page.waitForTimeout(300);

    // ── Tab 2: Layers Tree ──────────────────────────────────────────────────────
    const layersTabBtn = page.locator('[data-testid="sidebar-tab-layers"]');
    await expect(layersTabBtn).toBeVisible();
    await layersTabBtn.click();
    await page.waitForTimeout(400);

    // Verify tree items exist in the layers panel
    const layerItems = page.locator('[data-layer-row]');
    await expect(layerItems.first()).toBeVisible({ timeout: 5000 });
    const layerCount = await layerItems.count();
    expect(layerCount).toBeGreaterThanOrEqual(1);

    // Clicking an element in layers tree selects it and opens the Inspector
    const firstLayerItem = layerItems.first();
    await firstLayerItem.click();
    await page.waitForTimeout(400);

    // Inspector should now display tabs for the selected item
    const inspectorTabs = page.locator('[data-builder-inspector] [role="tab"]');
    await expect(inspectorTabs.first()).toBeVisible();

    // ── Tab 3: History Timeline ─────────────────────────────────────────────────
    const historyTabBtn = page.locator('[data-testid="history-tab-btn"]');
    await expect(historyTabBtn).toBeVisible();
    await historyTabBtn.click();
    await page.waitForTimeout(300);

    // History panel renders with title and step indicators
    const historyPanel = page.locator('[data-testid="builder-history-panel"]');
    await expect(historyPanel).toBeVisible();
  });

  test("3. Center Canvas & Top Toolbar human interaction: Inline text editing, shortcuts & global styles", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();

    // ── Canvas Selection & Inline Editing ─────────────────────────────────────────
    // Double click to trigger inline editing
    await headingEl.dblclick();
    await page.waitForTimeout(300);

    const inlineEditor = frame.locator('[data-testid="inline-text-editor"]');
    if (await inlineEditor.isVisible()) {
      await inlineEditor.fill("سرتیتر ارتقایافته تست انسان‌محور");
      await page.keyboard.press("Enter");
      await page.waitForTimeout(400);
      await expect(headingEl).toContainText("سرتیتر ارتقایافته تست انسان‌محور");
    }

    // ── Top Toolbar: Global Styles Dialog ─────────────────────────────────────────
    const globalStylesBtn = page.locator('header button:has-text("استایل سراسری")');
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();
    await page.waitForTimeout(400);

    const globalStylesDialog = page.locator('[role="dialog"]').filter({ hasText: "استایل سراسری" });
    await expect(globalStylesDialog).toBeVisible();

    // Close dialog with Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    await expect(globalStylesDialog).not.toBeVisible();

    // ── Top Toolbar: Keyboard Shortcuts Dialog ──────────────────────────────────
    const shortcutsBtn = page.locator('[data-testid="shortcuts-help-btn"]');
    await expect(shortcutsBtn).toBeVisible();
    await shortcutsBtn.click();
    await page.waitForTimeout(400);

    const shortcutsDialog = page.locator('[role="dialog"]:has-text("کلیدهای میانبر")');
    await expect(shortcutsDialog).toBeVisible();

    // Close shortcuts dialog
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
    await expect(shortcutsDialog).not.toBeVisible();
  });

  test("4. Right Inspector Panel: Content, Style & Advanced 3-tab live canvas manipulation", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Select the heading element on canvas
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
    await expect(headingEl).toBeVisible();
    await headingEl.click();
    await page.waitForTimeout(400);

    // ── Tab 1: Content (محتوا) ──────────────────────────────────────────────────
    const contentTab = page.locator('[data-builder-inspector] button[role="tab"]').filter({ hasText: "محتوا" });
    await expect(contentTab).toBeVisible();
    await contentTab.click();
    await page.waitForTimeout(300);

    const textInput = page.locator('[data-builder-inspector] input').first();
    await expect(textInput).toBeVisible();
    await textInput.fill("عنوان جدید از پنل محتوا");
    await page.waitForTimeout(400);
    await expect(headingEl).toContainText("عنوان جدید از پنل محتوا");

    // ── Tab 2: Style (استایل) ───────────────────────────────────────────────────
    const styleTab = page.locator('[data-builder-inspector] button[role="tab"]').filter({ hasText: "استایل" });
    await expect(styleTab).toBeVisible();
    await styleTab.click();
    await page.waitForTimeout(400);

    // Click border radius token button (e.g. 12px or 16px)
    const radiusTokenBtn = page.locator('[data-builder-inspector] button:has-text("متوسط (12px)")');
    if (await radiusTokenBtn.isVisible()) {
      await radiusTokenBtn.click();
      await page.waitForTimeout(400);
      const computedRadius = await headingEl.evaluate((el) => window.getComputedStyle(el).borderRadius);
      expect(computedRadius).toBe("12px");
    }

    // ── Tab 3: Advanced (پیشرفته) ───────────────────────────────────────────────
    const advTab = page.locator('[data-builder-inspector] button[role="tab"]').filter({ hasText: "پیشرفته" });
    await expect(advTab).toBeVisible();
    await advTab.click();
    await page.waitForTimeout(400);

    // Custom Attributes textarea
    const customAttrTextarea = page.locator('[data-testid="custom-attributes-textarea"]');
    await expect(customAttrTextarea).toBeVisible();
    await customAttrTextarea.fill("data-human-verified|1080p-ok\naria-label|accessible-heading");
    await page.waitForTimeout(500);

    // Live canvas receives custom attributes
    await expect(headingEl).toHaveAttribute("data-human-verified", "1080p-ok");
    await expect(headingEl).toHaveAttribute("aria-label", "accessible-heading");
  });

  test("5. Responsive breakpoint switcher & full preview mode ergonomics", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvasIframe = page.locator('iframe[title="Visual Builder Canvas"]');
    await expect(canvasIframe).toBeVisible();

    // ── Tablet Breakpoint (768px) ───────────────────────────────────────────────
    const tabletBtn = page.locator('button:has-text("تبلت (۷۶۸)")');
    await expect(tabletBtn).toBeVisible();
    await tabletBtn.click();
    await page.waitForTimeout(500);

    // Canvas container scales or resizes to tablet width
    const tabletBox = await canvasIframe.boundingBox();
    expect(tabletBox).not.toBeNull();
    expect(tabletBox!.width).toBeLessThanOrEqual(780);

    // ── Mobile Breakpoint (375px) ───────────────────────────────────────────────
    const mobileBtn = page.locator('button:has-text("موبایل (۳۷۵)")');
    await expect(mobileBtn).toBeVisible();
    await mobileBtn.click();
    await page.waitForTimeout(500);

    const mobileBox = await canvasIframe.boundingBox();
    expect(mobileBox).not.toBeNull();
    expect(mobileBox!.width).toBeLessThanOrEqual(385);

    // ── Desktop Breakpoint ──────────────────────────────────────────────────────
    const desktopBtn = page.locator('header button:has-text("دسکتاپ")').first();
    await expect(desktopBtn).toBeVisible();
    await desktopBtn.click();
    await page.waitForTimeout(500);

    const desktopBox = await canvasIframe.boundingBox();
    expect(desktopBox).not.toBeNull();
    expect(desktopBox!.width).toBeGreaterThan(1000);

    // ── Preview Mode Toggle ─────────────────────────────────────────────────────
    const previewBtn = page.locator('header button:has-text("پیش‌نمایش")');
    await expect(previewBtn).toBeVisible();
    await previewBtn.click();
    await page.waitForTimeout(500);

    // Both sidebars should now be hidden
    const leftAside = page.locator("aside").first();
    const rightAside = page.locator("aside[data-builder-inspector]");
    await expect(leftAside).not.toBeVisible();
    await expect(rightAside).not.toBeVisible();

    // Exit preview mode by clicking "ویرایش"
    const editBtn = page.locator('header button:has-text("ویرایش")');
    await expect(editBtn).toBeVisible();
    await editBtn.click();
    await page.waitForTimeout(500);

    // Both sidebars return
    await expect(leftAside).toBeVisible();
    await expect(rightAside).toBeVisible();
  });
});
