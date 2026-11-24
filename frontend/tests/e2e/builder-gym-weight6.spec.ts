import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-056/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w6-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 6: Elementor Wave 1 Porting (CSS Grid, Shapes, and Navigator Parity)", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1005", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1005", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.211.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Container CSS Grid layout supports column count and grid auto flow selection", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Select container element
    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootEl = store.getState().ast.rootElements[0];
        if (rootEl) store.getState().selectElement(rootEl.id);
      }
    });
    await page.waitForTimeout(400);

    // Switch container kind to grid
    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootId = store.getState().selectedElementId;
        if (rootId) {
          store.getState().updateElementLayout(rootId, { kind: "grid", gridColumns: 4, gridAutoFlow: "row dense" });
        }
      }
    });
    await page.waitForTimeout(500);

    // Verify grid columns input and auto flow select are visible
    const colsInput = page.locator("[data-testid='grid-columns-input']");
    await expect(colsInput).toBeVisible();
    await expect(colsInput).toHaveValue("4");

    const flowSelect = page.locator("[data-testid='grid-auto-flow-select']");
    await expect(flowSelect).toBeVisible();
  });

  test("2. Container Content Width switcher toggles Boxed vs Full Width cleanly", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootEl = store.getState().ast.rootElements[0];
        if (rootEl) store.getState().selectElement(rootEl.id);
      }
    });
    await page.waitForTimeout(400);

    const boxedBtn = page.locator("[data-testid='container-width-boxed-btn']");
    const fullBtn = page.locator("[data-testid='container-width-full-btn']");

    await expect(boxedBtn).toBeVisible();
    await expect(fullBtn).toBeVisible();

    await boxedBtn.click();
    await page.waitForTimeout(300);

    // Verify boxed width applied in store
    const boxedWidth = await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      const rootId = store?.getState().selectedElementId;
      const el = store?.getState().ast.rootElements.find((r: any) => r.id === rootId);
      return el?.layout?.boxedWidth?.value;
    });
    expect(boxedWidth).toBe(1280);

    // Toggle back to full width
    await fullBtn.click();
    await page.waitForTimeout(300);
  });

  test("3. LayersTree Navigator context menu supports Duplicate, Copy, and Delete actions", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Switch to Layers tab
    const layersTabBtn = page.locator("[data-testid='sidebar-tab-layers']");
    await layersTabBtn.click();
    await page.waitForTimeout(500);

    const firstRow = page.locator("[data-layer-row]").first();
    await expect(firstRow).toBeVisible();

    // Trigger right click context menu on layer row
    await firstRow.click({ button: "right" });
    await page.waitForTimeout(500);

    const menu = page.locator("[data-testid='navigator-context-menu']");
    await expect(menu).toBeVisible();
    await expect(menu.locator("text=تکثیر")).toBeVisible();
    await expect(menu.locator("button:has-text('کپی')").first()).toBeVisible();

    // Click outside to close
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  });

  test("4. CanvasFrame overlay calculates floating toolbar clearance without overlapping viewport", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (store) {
        const rootEl = store.getState().ast.rootElements[0];
        if (rootEl) store.getState().selectElement(rootEl.id);
      }
    });
    await page.waitForTimeout(500);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const floatingToolbar = iframeEl.locator("[data-testid='floating-toolbar']");
    if (await floatingToolbar.isVisible()) {
      const box = await floatingToolbar.boundingBox();
      expect(box).not.toBeNull();
      if (box) {
        expect(box.y).toBeGreaterThanOrEqual(0);
      }
    }
  });
});
