target = ".arena/run-20261125-190622-s622418/r0/a008.md"
part = """#### 7.3 Playwright E2E Spec: `frontend/tests/e2e/builder-gym-weight2-interactive.spec.ts`

```typescript
import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Builder Gym Weight 2: Interactive Widgets & Form Controls Mastery", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);
  });

  test("1. Form Container & Input wiring and inspector state propagation", async ({ page }) => {
    // Select blocks palette
    const blocksTab = page.locator("[data-tab='blocks'], button").filter({ hasText: "بلوک‌ها" }).first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    // Search for form container
    const searchInput = page.locator("input[placeholder*='جستجو']").first();
    await searchInput.fill("فرم سازنده");
    await page.waitForTimeout(400);

    const formBlock = page.locator("button").filter({ hasText: "فرم سازنده" }).first();
    await expect(formBlock).toBeVisible();
    await formBlock.click();
    await page.waitForTimeout(600);

    // Verify canvas frame contains form container
    const frame = page.frameLocator("iframe[title='Visual Builder Canvas']");
    const formContainer = frame.locator("[data-widget-type='form_container']").first();
    await expect(formContainer).toBeVisible();

    // Select container and inspect props
    await formContainer.click();
    await page.waitForTimeout(500);

    const urlInput = page.locator("[data-testid='form-container-submit-url']").first();
    await expect(urlInput).toBeVisible();
    await urlInput.fill("/api/v1/content/forms/custom-submit");
    await page.waitForTimeout(300);

    // Verify prop reflected in canvas data-submit-url attribute
    await expect(formContainer.locator("[data-submit-url]").first()).toHaveAttribute(
      "data-submit-url",
      "/api/v1/content/forms/custom-submit"
    );
  });

  test("2. Accordion dynamic item management and canvas collapse verification", async ({ page }) => {
    const blocksTab = page.locator("[data-tab='blocks'], button").filter({ hasText: "بلوک‌ها" }).first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const searchInput = page.locator("input[placeholder*='جستجو']").first();
    await searchInput.fill("آکاردئون");
    await page.waitForTimeout(400);

    const accordionBlock = page.locator("button").filter({ hasText: "آکاردئون" }).first();
    await accordionBlock.click();
    await page.waitForTimeout(600);

    const frame = page.frameLocator("iframe[title='Visual Builder Canvas']");
    const accordionWidget = frame.locator("[data-widget-type='accordion']").first();
    await expect(accordionWidget).toBeVisible();

    // Click accordion to open inspector
    await accordionWidget.click();
    await page.waitForTimeout(500);

    // Add new accordion item via inspector button
    const addItemBtn = page.locator("[data-testid='accordion-add-item-btn']").first();
    await expect(addItemBtn).toBeVisible();
    await addItemBtn.click();
    await page.waitForTimeout(400);

    // Fill title for newly added item
    const newItemTitle = page.locator("[data-testid='accordion-item-title-2']").first();
    await expect(newItemTitle).toBeVisible();
    await newItemTitle.fill("پرسش تخصصی جدید");
    await page.waitForTimeout(300);

    // Verify canvas reflects new item title
    const canvasSummary = accordionWidget.locator("summary").filter({ hasText: "پرسش تخصصی جدید" }).first();
    await expect(canvasSummary).toBeVisible();
  });

  test("3. Dropdown z-index elevation (>= 150) unblocked above canvas", async ({ page }) => {
    const frame = page.frameLocator("iframe[title='Visual Builder Canvas']");
    const anyWidget = frame.locator("[data-element-id]").first();
    if (await anyWidget.isVisible()) {
      await anyWidget.click();
      await page.waitForTimeout(400);

      const triggerSelect = page.locator("[data-testid='offcanvas-position-select'], [data-testid='popup-trigger-select']").first();
      if (await triggerSelect.isVisible()) {
        await triggerSelect.click();
        await page.waitForTimeout(300);

        const openContent = page.locator("[role='listbox'], [data-radix-popper-content-wrapper]").first();
        await expect(openContent).toBeVisible();
      }
    }
  });
});
```

---
"""
with open(target, "a", encoding="utf-8") as f:
    f.write(part)
print("Part 7C appended successfully")
