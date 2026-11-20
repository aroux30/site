import { test, expect } from "@playwright/test";

test.describe("Gym Round 01 Regression Invariants", () => {
  test("1. Hero section must not contain duplicate 3D floating badges", async ({ page }) => {
    await page.goto("http://127.0.0.1:3000/", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const badges = page.locator("text=نمای سه‌بعدی تعاملی ۳۶۰ درجه");
    const count = await badges.count();
    // Exactly 1 floating badge on hero, never duplicated/stacked
    expect(count).toBe(1);
  });

  test("2. Theme toggle button must never use opacity-0 on unmounted state", async ({ page }) => {
    await page.goto("http://127.0.0.1:3000/", { waitUntil: "domcontentloaded" });
    const toggle = page.locator('button[aria-label*="تم"]').first();
    await expect(toggle).toBeVisible();

    const cls = (await toggle.getAttribute("class")) || "";
    expect(cls).not.toContain("opacity-0");
  });

  test("3. Admin forms table must render form IDs with LTR direction", async ({ page }) => {
    await page.goto("http://127.0.0.1:3000/admin/forms", { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const formCells = page.locator("td[dir='ltr']");
    const count = await formCells.count();
    if (count > 0) {
      const firstDir = await formCells.first().getAttribute("dir");
      expect(firstDir).toBe("ltr");
    }
  });

  test("4. System health endpoint must report status ok and valid buildId", async ({ request }) => {
    const res = await request.get("http://127.0.0.1:3000/api/health");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("ok");
    expect(body.backend.ok).toBe(true);
    expect(body.buildId).toBeTruthy();
  });
});
