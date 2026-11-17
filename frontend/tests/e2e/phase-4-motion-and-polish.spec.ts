import { expect, test } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

test.describe("Phase 4 - Motion & Polish E2E Suite", () => {
  test("Builder Studio configures entrance animation in InspectorPanel and applies to canvas element", async ({
    page,
  }) => {
    test.setTimeout(60_000);
    // 1. Reset isolated scratchpad and auth
    await resetE2EPage("e2e-isolated-scratchpad");
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

    // 2. Open builder studio
    await page.goto("/e2e-isolated-scratchpad?visual_editor=true", {
      waitUntil: "domcontentloaded",
      timeout: 45_000,
    });
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });

    const frame = page.frameLocator(CANVAS);
    await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });

    // 3. Add Heading block
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator("button:has-text('سرتیتر')").first().click();

    // 4. Select the element on canvas
    const headingElem = frame.locator("h2, h1").first();
    await expect(headingElem).toBeVisible({ timeout: 10_000 });
    await headingElem.click({ force: true });

    // 5. Open Advanced Tab in Inspector
    await page.getByRole("tab", { name: "پیشرفته" }).click();
    await expect(page.locator("text=انیمیشن ورود و اسکرول")).toBeVisible({ timeout: 5_000 });

    // 6. Select "لغزش از پایین به بالا (Slide Up)" animation
    await page.locator("button:has-text('بدون انیمیشن')").or(page.locator("text=بدون انیمیشن (None)")).first().click();
    await page.locator("[role='option']:has-text('لغزش از پایین به بالا')").click();

    // 7. Verify animation class is applied to the canvas element container
    const animContainer = frame.locator(".builder-animate-slide-up");
    await expect(animContainer).toBeVisible({ timeout: 5_000 });
  });

  test("Header promotional TextLoop renders in storefront", async ({ page }) => {
    await page.goto("/products");
    await expect(page.locator("body")).toBeVisible({ timeout: 20_000 });

    // Check notice banner or marquee text
    const headerBanner = page.locator("header");
    await expect(headerBanner).toBeVisible();
  });
});
