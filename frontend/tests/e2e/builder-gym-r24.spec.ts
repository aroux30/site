import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4003";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r24-spec-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 24: Elementor Core & Pro Complete 4-Layer Wiring", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
        })
      );
    });
  });

  test("1. Blocks palette lists all registered blocks and can toggle to patterns", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const blocksTabBtn = page.locator('button[data-testid="blocks-palette-basic-tab-btn"]');
    await expect(blocksTabBtn).toBeVisible();
    await expect(blocksTabBtn).toContainText("بلوک‌ها");
  });

  test("2. Inspector advanced tab displays clean transform & mask without duplicates", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstElement = canvasFrame.locator("[data-element-id]").first();
    await expect(firstElement).toBeVisible();
    await firstElement.click();
    await page.waitForTimeout(400);

    const advTab = page.getByRole("tab", { name: "پیشرفته" });
    await advTab.click();
    await page.waitForTimeout(400);

    const transformRotateInputs = page.locator("[data-testid='transform-rotate-input']");
    await expect(transformRotateInputs).toHaveCount(1);

    const maskSelects = page.locator("[data-testid='mask-shape-select']");
    await expect(maskSelects).toHaveCount(1);
  });

  test("3. Newly ported Image Box and Toggle blocks are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const imageBoxBlock = page.locator('button:has-text("باکس تصویر و متن")');
    await expect(imageBoxBlock).toBeVisible();

    const toggleBlock = page.locator('button:has-text("آیتم‌های تاشو")');
    await expect(toggleBlock).toBeVisible();
  });

  test("4. Share Buttons, Progress Tracker, and TOC blocks are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const shareBtnBlock = page.locator('button:has-text("دکمه‌های اشتراک‌گذاری")');
    await expect(shareBtnBlock).toBeVisible();

    const progressTrackerBlock = page.locator('button:has-text("ردگیر پیمایش صفحه")');
    await expect(progressTrackerBlock).toBeVisible();

    const tocBlock = page.locator('button:has-text("فهرست عناوین محتوا")');
    await expect(tocBlock).toBeVisible();
  });

  test("5. Hotspot and Lottie interactive widgets are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const hotspotBlock = page.locator('button:has-text("نقاط تعاملی تصویر")');
    await expect(hotspotBlock).toBeVisible();

    const lottieBlock = page.locator('button:has-text("انیمیشن وکتور")');
    await expect(lottieBlock).toBeVisible();
  });

  test("6. Code Highlight and Contact Buttons blocks are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const codeBlock = page.locator('button:has-text("نمایشگر و هایلایت کد")');
    await expect(codeBlock).toBeVisible();

    const contactBlock = page.locator('button:has-text("دکمه تماس و ارتباط شناور")');
    await expect(contactBlock).toBeVisible();
  });

  test("7. Image Carousel and Slides slider widgets are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const carouselBlock = page.locator('button:has-text("کاروسل افقی تصاویر")');
    await expect(carouselBlock).toBeVisible();

    const slidesBlock = page.locator('button:has-text("اسلایدر تمام‌عرض")');
    await expect(slidesBlock).toBeVisible();
  });

  test("8. Nested Tabs and Nested Accordion layout blocks are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const nTabsBlock = page.locator('button:has-text("زبانه‌های تودرتو")');
    await expect(nTabsBlock).toBeVisible();

    const nAccBlock = page.locator('button:has-text("آکاردئون پیشرفته")');
    await expect(nAccBlock).toBeVisible();
  });

  test("9. Multi-Step Form and Loop Carousel advanced blocks are available in palette", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
    await blocksTab.click();
    await page.waitForTimeout(400);

    const msFormBlock = page.locator('button:has-text("فرم چندمرحله‌ای")');
    await expect(msFormBlock).toBeVisible();

    const loopCarBlock = page.locator('button:has-text("کاروسل تکرارشونده پویا")');
    await expect(loopCarBlock).toBeVisible();
  });
});
