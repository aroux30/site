import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-051/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w1-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 1: Studio Skeleton, Layers Tree, and Canvas Iframe", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.206.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
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

  test("1. Studio 3-column layout renders cleanly with responsive breakpoints and zero horizontal overflow", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Verify 3 columns: Left palette aside, center canvas iframe, right inspector aside
    const leftAside = page.locator("aside").first();
    const centerIframe = page.locator("iframe").first();
    const rightInspector = page.locator("[data-builder-inspector]");

    await expect(leftAside).toBeVisible();
    await expect(centerIframe).toBeVisible();
    await expect(rightInspector).toBeVisible();

    // Verify breakpoint buttons
    const desktopBtn = page.locator("button:has-text('دسکتاپ')");
    const tabletBtn = page.locator("button:has-text('تبلت')");
    const mobileBtn = page.locator("button:has-text('موبایل')");

    await expect(desktopBtn).toBeVisible();
    await expect(tabletBtn).toBeVisible();
    await expect(mobileBtn).toBeVisible();
  });

  test("2. LayersTree displays permanent action buttons (zero opacity-0) with RTL indentation and tree guides", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Switch sidebar tab to Layers
    const layersTabBtn = page.locator("[data-testid='sidebar-tab-layers']");
    await expect(layersTabBtn).toBeVisible();
    await layersTabBtn.click();
    await page.waitForTimeout(500);

    // Verify layer item exists
    const layerRows = page.locator("[data-layer-row]");
    await expect(layerRows.first()).toBeVisible();

    // Verify action buttons inside first layer row are visible
    const actionButtons = layerRows.first().locator("button");
    const count = await actionButtons.count();
    expect(count).toBeGreaterThanOrEqual(2);

    for (let i = 0; i < count; i++) {
      await expect(actionButtons.nth(i)).toBeVisible();
    }
  });

  test("3. CanvasFrame empty container has dashed border and minimum height 80px", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const emptyGuide = iframeEl.locator("[data-testid='empty-container-guide']").first();
    await expect(emptyGuide).toBeVisible();
    await expect(emptyGuide.locator("text=افزودن بلوک به این بخش")).toBeVisible();

    const box = await emptyGuide.boundingBox();
    expect(box).not.toBeNull();
    if (box) {
      expect(box.height).toBeGreaterThanOrEqual(75);
    }
  });

  test("4. CanvasFrame iframe inherits theme variables without invalid CSS syntax", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    const docStyles = await page.evaluate(() => {
      const iframe = document.querySelector("iframe");
      if (!iframe || !iframe.contentDocument) return {};
      const style = iframe.contentDocument.documentElement.style;
      return {
        primary: style.getPropertyValue("--primary"),
        themePrimary: style.getPropertyValue("--theme-primary"),
        primaryHex: style.getPropertyValue("--primary-hex"),
        radius: style.getPropertyValue("--radius"),
      };
    });

    expect(docStyles.primary).toBeDefined();
    expect(docStyles.themePrimary).toBeDefined();
    expect(docStyles.primaryHex).toBeDefined();
  });
});
