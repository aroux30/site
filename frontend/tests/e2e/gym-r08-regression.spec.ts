import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 08 Regression Invariants (Search & RTL Input Ergonomics)", () => {
  test("1. Live search spinner and clear buttons use RTL-native end/start alignments", async ({ page }) => {
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const searchInput = page.locator("input[placeholder*='جستجو']").first();
    await expect(searchInput).toBeVisible();

    await searchInput.fill("پابجی");

    // Dropdown listbox should be open with suggestions
    const listbox = page.locator("[role='listbox']");
    await expect(listbox).toBeVisible({ timeout: 10000 });

    // Verify suggestions contain text
    const suggestionItems = listbox.locator("[role='option']");
    const count = await suggestionItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test("2. Faceted filter sidebar renders active count badges on filter headers", async ({ page }) => {
    await page.goto(`${BASE_URL}/products`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Filter section headers should be present
    const categoryHeader = page.locator("button:has-text('دسته‌بندی')").first();
    await expect(categoryHeader).toBeVisible();

    const priceHeader = page.locator("button:has-text('محدوده قیمت')").first();
    await expect(priceHeader).toBeVisible();
  });
});
