import { test, expect } from "@playwright/test";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 13 Regression Invariants (Product Comparison & Matrix Fallback)", () => {
  test("1. Empty compare page displays clear guidance card with add button", async ({ page }) => {
    await page.goto(`${BASE_URL}/compare`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const emptyTitle = page.locator("h1:has-text('لیست مقایسه شما خالی است')");
    await expect(emptyTitle).toBeVisible();

    const addBtn = page.locator("a[href='/products'] button");
    await expect(addBtn).toBeVisible();
  });

  test("2. Compare matrix displays fallback package placeholder when item has no image", async ({ page }) => {
    await page.goto(`${BASE_URL}/compare`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => {
      localStorage.setItem(
        "compare-storage",
        JSON.stringify({
          state: {
            products: [
              {
                id: "c3f93ad5-8ee5-47cd-977b-8284d079b18b",
                title: "۱۸۰۰ یوسی",
                price: 2000000,
                rating: 4.8,
                stock: 10,
                slug: "1800-yvsy",
                sku: "UC-1800",
                images: [],
                tags: [],
                variants: [],
                attributes: [],
                createdAt: "",
                updatedAt: "",
                categoryId: "",
              },
            ],
          },
        })
      );
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const matrixHeading = page.locator("h1:has-text('مقایسه هوشمند محصولات')");
    await expect(matrixHeading).toBeVisible();

    // Verify package fallback placeholder is rendered
    const fallbackBox = page.locator(".aspect-square svg").first();
    await expect(fallbackBox).toBeVisible();
  });
});
