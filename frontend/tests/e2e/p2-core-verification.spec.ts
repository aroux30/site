import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E, resetE2EPage } from "./helpers/admin-token";

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

async function openIsolatedStudio(page: Page): Promise<FrameLocator> {
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
  await page.goto("/e2e-isolated-scratchpad?visual_editor=true");
  await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });
  const frame = page.frameLocator(CANVAS);
  await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });
  return frame;
}

test.describe("Phase P2.0 Core E2E Verification Suite", () => {
  test("Global Styles dialog opens, updates brand colors and radius, and injects into iframe", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Click Global Styles button in toolbar
    const globalStylesBtn = page.getByRole("button", { name: "استایل سراسری" });
    await expect(globalStylesBtn).toBeVisible();
    await globalStylesBtn.click();

    // 2. Verify dialog opened
    await expect(page.locator("text=تنظیمات استایل سراسری برگه")).toBeVisible();

    // 3. Pick a preset color (e.g. آبی درباری #2563eb)
    const bluePreset = page.locator("button[title*='آبی']");
    await expect(bluePreset).toBeVisible();
    await bluePreset.click();

    // 4. Change border radius
    await page.locator("text=استاندارد (12px)").click();
    await page.locator("div[role='option']:has-text('بزرگ (16px)')").click();

    // 5. Apply changes
    await page.getByRole("button", { name: "اعمال تغییرات" }).click();
    await expect(page.locator("text=تنظیمات استایل سراسری برگه")).not.toBeVisible();

    // 6. Verify CSS variables are injected into iframe document element
    const iframeStyles = await page.locator(CANVAS).evaluate((iframe: HTMLIFrameElement) => {
      const doc = iframe.contentDocument;
      return {
        primary: doc?.documentElement?.style.getPropertyValue("--primary"),
        radius: doc?.documentElement?.style.getPropertyValue("--radius"),
      };
    });

    expect(iframeStyles.primary).toBe("#2563eb");
    expect(iframeStyles.radius).toBe("16px");

    // 7. Verify parent document does NOT have these styles (isolated iframe)
    const parentPrimary = await page.evaluate(() => {
      return document.documentElement.style.getPropertyValue("--primary");
    });
    expect(parentPrimary).not.toBe("#2563eb");
  });

  test("Image Inspector includes Media Library picker alongside manual URL", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Add Image block from palette
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator("button:has-text('تصویر')").first().click();

    // 2. Select the image element on canvas
    const imgElement = frame.locator("[data-element-id]:has(img)").last();
    await expect(imgElement).toBeVisible();
    await imgElement.click();

    // 3. Verify Inspector displays Media Library picker button
    await expect(page.locator("text=انتخاب از کتابخانه رسانه")).toBeVisible();
    await expect(page.getByRole("button", { name: "انتخاب", exact: true })).toBeVisible();

    // 4. Verify manual URL field is also available and working
    const manualUrlInput = page.locator("input[placeholder*='https://']");
    await expect(manualUrlInput).toBeVisible();
    await manualUrlInput.fill("/custom-test-image.jpg");

    // 5. Verify image on canvas updates
    await expect(frame.locator("img[src*='custom-test-image.jpg']")).toBeVisible();
  });

  test("Global Styles persist after save draft and full page reload", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Set a custom primary color via Global Styles
    await page.getByRole("button", { name: "استایل سراسری" }).click();
    const purplePreset = page.locator("button[title*='بنفش']");
    await purplePreset.click();
    await page.getByRole("button", { name: "اعمال تغییرات" }).click();

    // 2. Save draft
    await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click();
    await expect(page.locator("text=پیش‌نویس ذخیره شد")).toBeVisible({ timeout: 10_000 });

    // 3. Reload page
    await page.reload();
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({ timeout: 30_000 });
    const reloadedFrame = page.frameLocator(CANVAS);
    await expect(reloadedFrame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({ timeout: 20_000 });

    // 4. Verify iframe re-hydrated with persisted primary color
    await expect.poll(async () => {
      return await page.locator(CANVAS).evaluate((iframe: HTMLIFrameElement) => {
        return iframe.contentDocument?.documentElement?.style.getPropertyValue("--primary");
      });
    }, { timeout: 10_000 }).toBe("#7c3aed");
  });
});
