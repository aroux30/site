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

test.describe("Phase P2.1 Native Widgets & Template Library E2E Suite", () => {
  test("Native Table Widget: add, render in canvas, and edit cells in Inspector", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Add Table block from palette
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    const tableBtn = page.locator("button:has-text('جدول داده')").first();
    await expect(tableBtn).toBeVisible();
    await tableBtn.click();

    // 2. Verify Table renders in canvas
    await expect(frame.locator("table")).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("th:has-text('مشخصه')")).toBeVisible();
    await expect(frame.locator("td:has-text('۱۸ ماه تعویض')")).toBeVisible();

    // 3. Select table widget
    const tableNode = frame.locator("[data-element-id]:has(table)").last();
    await tableNode.click();

    // 4. Verify Inspector displays Table settings
    await expect(page.locator("text=عناوین ستون‌ها")).toBeVisible({ timeout: 5_000 });
    const headersInput = page.locator("input[placeholder*='عنوان ۱']");
    await expect(headersInput).toBeVisible();

    // Edit headers in Inspector
    await headersInput.fill("ویژگی کالا، نسخه استاندارد، نسخه پرو");

    // Verify canvas table header updates live
    await expect(frame.locator("th:has-text('نسخه پرو')")).toBeVisible({ timeout: 5_000 });
  });

  test("Native Form Widgets: add form_input and edit label in Inspector", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Add form_input block from palette
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    const inputBtn = page.locator("button:has-text('فیلد ورودی متن')").first();
    await expect(inputBtn).toBeVisible();
    await inputBtn.click();

    // 2. Verify form input renders in canvas
    await expect(frame.locator("label:has-text('نام و نام خانوادگی')")).toBeVisible({ timeout: 10_000 });
    await expect(frame.locator("input[placeholder*='علی رضایی']")).toBeVisible();

    // 3. Select input element and edit label in Inspector
    const inputNode = frame.locator("[data-element-id]:has(input)").last();
    await inputNode.click();

    await expect(page.locator("text=عنوان فیلد (Label)")).toBeVisible();
    const labelInput = page.locator("input[value*='نام و نام خانوادگی']");
    await labelInput.fill("نام و نام خانوادگی خریدار");

    // Verify canvas updates live
    await expect(frame.locator("label:has-text('نام و نام خانوادگی خریدار')")).toBeVisible({ timeout: 5_000 });
  });

  test("Section Templates: save container as template and insert from Saved Templates tab", async ({ page }) => {
    const frame = await openIsolatedStudio(page);

    // 1. Select the main container via Layers tab
    await page.getByRole("button", { name: "لایه‌ها" }).click();
    await page.locator("text=کانتینر اصلی").first().click();

    // 2. Click "Save as Template" button on floating toolbar inside the iframe
    const saveTplBtn = frame.locator("[title*='ذخیره به عنوان قالب']").first();
    await expect(saveTplBtn).toBeVisible({ timeout: 10_000 });
    await saveTplBtn.click();

    // 3. Fill template title in dialog and save (dialog portals into page document)
    await expect(page.locator("text=ذخیره به عنوان قالب بخش")).toBeVisible({ timeout: 10_000 });
    const titleInput = page.locator("input[placeholder*='هیرو بنر']");
    const uniqueTplTitle = `قالب تست بخش ${Date.now()}`;
    await titleInput.fill(uniqueTplTitle);

    await page.getByRole("button", { name: "ذخیره قالب" }).click();
    await expect(page.locator("text=قالب ذخیره شد")).toBeVisible({ timeout: 10_000 });

    // 4. Open palette and switch to "قالب‌های من" (Saved Templates) tab
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    const templatesTab = page.getByRole("button", { name: /قالب‌های من/ });
    await expect(templatesTab).toBeVisible();
    await templatesTab.click();

    // 5. Verify newly saved template card is listed
    const tplCard = page.locator(`div[draggable='true']:has-text('${uniqueTplTitle}')`).first();
    await expect(tplCard).toBeVisible({ timeout: 10_000 });

    // 6. Click to insert saved template into canvas
    const countBefore = await frame.locator("[data-element-id]").count();
    await tplCard.click();
    await expect(page.locator("text=قالب افزوده شد")).toBeVisible({ timeout: 10_000 });

    // Verify element count increased (container + children cloned onto canvas)
    const countAfter = await frame.locator("[data-element-id]").count();
    expect(countAfter).toBeGreaterThan(countBefore);
  });
});
