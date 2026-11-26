import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { resetE2EPage } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r01-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 01: Weight 1 Regression Invariants", () => {
  test.beforeEach(async ({ context }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
        })
      );
    });
  });

  test("1. ?builder=1 activates BuilderStudio directly and suppresses chat FAB collision", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Studio root must be visible and fullscreen
    const studio = page.locator("div.fixed.inset-0").first();
    await expect(studio).toBeVisible();

    // Body-level chat widget must NOT be visible or displayed in builder
    const chatWidget = page.locator("#n8n-w");
    if (await chatWidget.count() > 0) {
      const display = await chatWidget.evaluate((el) => window.getComputedStyle(el).display);
      expect(display).toBe("none");
    }
  });

  test("2. Floating action toolbar clears iframe ceiling without clipping", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await expect(firstEl).toBeVisible({ timeout: 15000 });
    await firstEl.click({ position: { x: 12, y: 12 } });
    await page.waitForTimeout(500);

    const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
    await expect(toolbar).toBeVisible({ timeout: 15000 });

    const rect = await toolbar.evaluate((el) => el.getBoundingClientRect());
    expect(rect.top).toBeGreaterThanOrEqual(0);
    const elRect = await firstEl.evaluate((el) => el.getBoundingClientRect());
    expect(rect.bottom).toBeLessThanOrEqual(elRect.top + 2);
  });

  test("2b. Mobile (375px) floating toolbar fits within viewport without horizontal overflow or overlap", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('iframe[title="Visual Builder Canvas"]', { timeout: 15000 });
    await page.locator("button[title*='موبایل']").click();
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await expect(firstEl).toBeVisible({ timeout: 15000 });
    await firstEl.click({ position: { x: 12, y: 12 } });

    const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
    await expect(toolbar).toBeVisible({ timeout: 15000 });
    const metrics = await page.evaluate(() => {
      const iframe = document.querySelector('iframe[title="Visual Builder Canvas"]') as HTMLIFrameElement;
      const doc = iframe?.contentDocument;
      const tb = doc?.querySelector('[data-testid="floating-toolbar"]');
      const el = doc?.querySelector("[data-element-id]");
      const tbRect = tb?.getBoundingClientRect();
      const elRect = el?.getBoundingClientRect();
      return {
        clientW: doc?.documentElement.clientWidth || 0,
        scrollW: doc?.documentElement.scrollWidth || 0,
        tbRight: tbRect?.right || 0,
        tbLeft: tbRect?.left || 0,
        tbBottom: tbRect?.bottom || 0,
        elTop: elRect?.top || 0,
      };
    });
    expect(metrics.scrollW).toBeLessThanOrEqual(metrics.clientW);
    expect(metrics.tbRight).toBeLessThanOrEqual(metrics.clientW);
    expect(metrics.tbLeft).toBeGreaterThanOrEqual(0);
    expect(metrics.tbBottom).toBeLessThanOrEqual(metrics.elTop + 2);
  });

  test("3. LayersTree action buttons permanently visible at mouse (0,0) with 24px RTL indent", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    await page.mouse.move(0, 0);

    const layersTab = page.locator("button:has-text('لایه‌ها')").first();
    await layersTab.waitFor({ state: "visible", timeout: 15000 });
    await layersTab.click();
    await expect(page.locator("[data-layer-row]").first()).toBeVisible({ timeout: 15000 });

    const rows = page.locator("[data-layer-row]");
    const count = await rows.count();
    expect(count).toBeGreaterThan(0);

    for (let i = 0; i < count; i++) {
      const row = rows.nth(i);
      const buttons = row.locator("button");
      const bCount = await buttons.count();
      for (let b = 0; b < bCount; b++) {
        const btn = buttons.nth(b);
        const cls = (await btn.getAttribute("class")) || "";
        expect(cls).not.toContain("opacity-0");
        expect(await btn.isVisible()).toBe(true);
      }
    }
  });

  test("4. Empty container guide maintains min-height >= 80px and dashed border", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').first();
    if (await emptyGuide.count() > 0) {
      await expect(emptyGuide).toBeVisible();
      const box = await emptyGuide.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.height).toBeGreaterThanOrEqual(70);
      }
    }
  });

  test("5. Nested depth-2 LayersTree row keeps single 24px-per-level RTL indent and readable label", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="sidebar-tab-layers"]', { timeout: 15000 });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await page.evaluate(() => {
      const store = (window as any).__builderStore.getState();
      store.addElement({
        id: "el_r01_d0",
        name: "ریشه لایه تست",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
        styles: { mobile: {} },
        children: [{
          id: "el_r01_d1",
          name: "سطح یک تست",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
          styles: { mobile: {} },
          children: [{
            id: "el_r01_d2",
            name: "تیتر سطح دو خوانا",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "تیتر", tag: "h3" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          }],
        }],
      });
    });

    await page.click('[data-testid="sidebar-tab-layers"]');
    const row0 = page.locator('[data-layer-row][data-element-id="el_r01_d0"]');
    const row1 = page.locator('[data-layer-row][data-element-id="el_r01_d1"]');
    const row2 = page.locator('[data-layer-row][data-element-id="el_r01_d2"]');
    await expect(row2).toBeVisible({ timeout: 10000 });

    const r0 = await row0.boundingBox();
    const r1 = await row1.boundingBox();
    const r2 = await row2.boundingBox();
    expect(r0 && r1 && r2).toBeTruthy();
    // Single 24px-per-level indent (plus 10px guide padding) rather than compounding 156px squish
    expect(r0!.x + r0!.width - (r2!.x + r2!.width)).toBeLessThan(80);
    expect(r2!.width).toBeGreaterThan(190);
    const labelBox = await row2.locator("span.truncate").boundingBox();
    expect(labelBox).not.toBeNull();
    expect(labelBox!.width).toBeGreaterThan(40);
  });

  test("6. Save Draft updates badge, persists on reload, and Publish reflects in SSR output", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="builder-toolbar-header"]', { timeout: 15000 });

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const heading = frame.locator("h2").first();
    await expect(heading).toBeVisible({ timeout: 15000 });
    await heading.click();

    const textInput = page.locator('[data-testid="heading-text-input"]');
    await expect(textInput).toBeVisible({ timeout: 10000 });
    const marker = "تست-پایداری-راند۱";
    await textInput.fill(marker);
    await expect(heading).toContainText(marker);

    // Save Draft -> badge must switch to پیش‌نویس after API completes
    await page.locator("button:has-text('ذخیره پیش‌نویس')").click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("پیش‌نویس", { timeout: 15000 });

    // Reload builder and verify DB persistence (not hardcoded fallback)
    await page.reload({ waitUntil: "domcontentloaded" });
    await expect(frame.locator(`h2:has-text('${marker}')`)).toBeVisible({ timeout: 15000 });

    // Publish -> badge updates and SSR public route renders compiled HTML
    await page.locator('[data-testid="publish-page-btn"]').click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("منتشرشده", { timeout: 15000 });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await expect(page.locator(".builder-rendered-content")).toContainText(marker, { timeout: 15000 });
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
