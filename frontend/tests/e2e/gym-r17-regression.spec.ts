import { test, expect } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";

test.describe("Gym Round 17 Regression Invariants (Support, Tickets & Kanban)", () => {
  test.beforeEach(async ({ page }) => {
    await page.setExtraHTTPHeaders({
      "X-Forwarded-For": `10.90.${Math.floor(Math.random() * 240) + 1}.${Math.floor(Math.random() * 240) + 1}`,
    });
    const token = await createAccessTokenForE2E();
    await page.context().addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await page.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. User tickets page renders container layout with RTL direction and new ticket trigger", async ({ page }) => {
    await page.goto(`${BASE_URL}/account/tickets`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('تیکت‌های پشتیبانی')");
    await expect(heading).toBeVisible();

    const newTicketBtn = page.locator("button:has-text('ثبت تیکت جدید')").first();
    await expect(newTicketBtn).toBeVisible();
  });

  test("2. Admin tickets list view renders single search input without duplicate header search", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/tickets`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const heading = page.locator("h1:has-text('مرکز پشتیبانی و تیکت‌ها')");
    await expect(heading).toBeVisible();

    // Verify only 1 search input is visible in list view
    const searchInputs = page.locator("input[placeholder*='شماره تیکت']");
    expect(await searchInputs.count()).toBe(1);
  });

  test("3. Admin tickets board view renders kanban columns with status headers", async ({ page }) => {
    await page.goto(`${BASE_URL}/admin/tickets?view=board`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const boardTrigger = page.locator("button[role='tab'][aria-selected='true']:has-text('کانبان')");
    await expect(boardTrigger).toBeVisible();

    // Board view should render column headers
    const openColumn = page.locator("h2, h3, [role='heading']").filter({ hasText: "باز" }).first();
    await expect(openColumn).toBeVisible();
  });
});
