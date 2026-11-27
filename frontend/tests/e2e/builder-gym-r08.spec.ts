import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { resetE2EPage } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

function getAdminToken() {
  const out = execSync(
    'python -c "import datetime, uuid; from app.core.security.jwt import create_access_token; print(\'TOK:\' + create_access_token(str(uuid.UUID(\'47f274da-3abd-4d91-bc9c-83ba913fc66f\')), extra_claims={\'roles\':[\'super_admin\'],\'is_superuser\':True,\'permissions\':[\'*\']}, expires_delta=datetime.timedelta(hours=2)))"',
    { cwd: BACKEND_DIR, encoding: "utf-8" }
  );
  return out.split("\n").find((l) => l.includes("TOK:"))?.replace("TOK:", "").trim() || "";
}

test.describe("Builder Gym Round 08: Elementor Wave 1 Complete Parity (Typography, Shapes, Hover, Sticky, Motion, Custom CSS)", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    await resetE2EPage("e2e-isolated-scratchpad");
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
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

  test("1. Nudge Wave 1 Typography, CSS Filters, Hover Border/Bg, 30 Shape Dividers, Sticky, Motion & Scoped Custom CSS with SSR Parity", async ({ page }) => {
    test.setTimeout(120000);
    const errors: string[] = [];
    const failedUrls: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("response", (res) => {
      if (res.status() >= 400 && !res.url().includes("favicon") && !res.url().includes("/auth/me")) {
        failedUrls.push(`${res.status()} ${res.url()}`);
      }
    });

    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="builder-toolbar-header"]', { timeout: 15000 });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });

    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');
    await frame.locator('[data-element-id="el_e2econt1"]').waitFor({ timeout: 15000 });

    // 1. Navigator expand/collapse all buttons + filter search work
    await page.getByTestId("sidebar-tab-layers").click();
    await expect(page.getByTestId("expand-all-layers-btn")).toBeVisible();
    await expect(page.getByTestId("collapse-all-layers-btn")).toBeVisible();
    await page.getByTestId("expand-all-layers-btn").click();

    // 2. Select container via Navigator first layer row and nudge Gradient + 30 Shape Dividers
    await page.locator("[data-layer-row]").first().click();
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('button[role="tab"]:has-text("استایل")').click();

    // Verify 30 shape options (29 SVG + none) and select clouds top & zigzag bottom
    const shapeTopTrigger = page.getByTestId("shape-divider-top-select");
    await shapeTopTrigger.scrollIntoViewIfNeeded();
    await shapeTopTrigger.click();
    const shapeCount = await page.locator('[role="option"]').count();
    expect(shapeCount).toBe(30);
    await page.locator('[role="option"]').filter({ hasText: "ابرها" }).first().click();

    const shapeBottomTrigger = page.getByTestId("shape-divider-bottom-select");
    await shapeBottomTrigger.click();
    await page.locator('[role="option"]').filter({ hasText: "زیگزاگ" }).first().click();
    await page.getByTestId("shape-divider-color-input").fill("#10b981");

    // Set gradient background
    await page.getByTestId("bg-type-gradient").scrollIntoViewIfNeeded();
    await page.getByTestId("bg-type-gradient").click();
    await page.getByTestId("gradient-angle-input").fill("135");

    // Verify clouds & zigzag render as colored inline SVGs (not broken images!) inside Canvas
    await expect(frame.locator('[data-element-id="el_e2econt1"] [data-testid="shape-divider-top"] svg path').first()).toHaveAttribute("fill", "#10b981");
    await expect(frame.locator('[data-element-id="el_e2econt1"] [data-testid="shape-divider-bottom"] svg path').first()).toHaveAttribute("fill", "#10b981");

    // 3. Advanced Tab: Sticky, Motion Parallax & Scoped Custom CSS (`selector`)
    await page.locator('button[role="tab"]:has-text("پیشرفته")').click();
    await page.getByTestId("sticky-mode-select").scrollIntoViewIfNeeded();
    await page.getByTestId("sticky-mode-select").click();
    await page.locator('[role="option"]').filter({ hasText: "چسبان به بالا" }).first().click();
    await page.getByTestId("sticky-offset-input").fill("16");
    await page.getByTestId("motion-parallax-switch").click();
    await page.getByTestId("custom-css-textarea").scrollIntoViewIfNeeded();
    await page.getByTestId("custom-css-textarea").fill("selector { outline: 3px solid rgb(245, 158, 11); }");

    // Verify Custom CSS outline & Navigator badges update live
    await expect(frame.locator('[data-element-id="el_e2econt1"]')).toHaveCSS("outline-style", "solid");
    await expect(page.getByTestId("layer-sticky-badge-el_e2econt1")).toBeVisible();
    await expect(page.getByTestId("layer-motion-badge-el_e2econt1")).toBeVisible();

    // 4. Select heading and nudge Typography Wave 1 controls (fontStyle, textDecoration, wordSpacing, textStroke, FontSize unit)
    await frame.locator('[data-element-id="el_e2ehead1"]').click();
    await page.locator('button[role="tab"]:has-text("استایل")').click();
    await page.getByTestId("typography-fontsize-unit").scrollIntoViewIfNeeded();
    await page.getByTestId("typography-fontsize-unit").selectOption("rem");
    await page.getByTestId("typography-fontsize-input").fill("2");
    await page.getByTestId("typography-fontstyle-select").click();
    await page.locator('[role="option"]').filter({ hasText: "مورب" }).first().click();
    await page.getByTestId("typography-wordspacing-input").fill("6");
    await page.getByTestId("typography-text-stroke-input").fill("1");
    await page.getByTestId("typography-text-stroke-color-input").fill("#10b981");

    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("font-style", "italic");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("word-spacing", "6px");

    // 5. Publish and verify 1:1 SSR parity at /e2e-isolated-scratchpad
    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/pages/") && r.request().method() === "PATCH" && r.status() < 400),
      page.waitForResponse((r) => r.url().includes("/api/cms-revalidate") && r.status() < 400),
      page.getByTestId("publish-page-btn").click(),
    ]);

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector("#el_e2econt1", { timeout: 15000 });

    await expect(page.locator("#el_e2econt1 .builder-shape-divider-top svg path").first()).toHaveAttribute("fill", "#10b981");
    await expect(page.locator("#el_e2econt1 .builder-shape-divider-bottom svg path").first()).toHaveAttribute("fill", "#10b981");
    expect(await page.locator("#el_e2econt1 .builder-shape-divider img").count()).toBe(0);
    await expect(page.locator("#el_e2econt1")).toHaveCSS("outline-style", "solid");
    await expect(page.locator("#el_e2econt1")).toHaveCSS("position", "sticky");
    await expect(page.locator("#el_e2econt1")).toHaveCSS("top", "16px");
    await expect(page.locator("#el_e2econt1")).toHaveAttribute("data-motion", /scrollParallax/);

    await expect(page.locator("#el_e2ehead1")).toHaveCSS("font-style", "italic");
    await expect(page.locator("#el_e2ehead1")).toHaveCSS("word-spacing", "6px");

    expect(failedUrls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
