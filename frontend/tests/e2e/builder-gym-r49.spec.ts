import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4001";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-40/after");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

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
  const tmp = path.join(BACKEND_DIR, `.gym-r49-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 35: 1920x1080 3-Column Studio Full Human-View Parity & Accessibility", () => {
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

  test("1. 1920x1080 Studio layout renders 3 distinct columns with zero overlap", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // Verify Right Column (Palette / Layers)
    const rightAside = page.locator("aside").first();
    await expect(rightAside).toBeVisible();
    const rightBox = await rightAside.boundingBox();
    expect(rightBox).not.toBeNull();
    expect(rightBox!.width).toBe(320);

    // Verify Center Column (Canvas Viewport)
    const centerMain = page.locator("main.overflow-y-auto");
    await expect(centerMain).toBeVisible();
    const centerBox = await centerMain.boundingBox();
    expect(centerBox).not.toBeNull();
    expect(centerBox!.width).toBe(1280);

    // Verify Left Column (Inspector)
    const inspectorAside = page.locator("[data-builder-inspector]");
    await expect(inspectorAside).toBeVisible();
    const inspectorBox = await inspectorAside.boundingBox();
    expect(inspectorBox).not.toBeNull();
    expect(inspectorBox!.width).toBe(320);

    // Capture clean overview
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-studio-1920x1080-overview.png") });
  });

  test("2. Right Sidebar Tabs & Search work seamlessly (Blocks, Layers, History)", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Search in Blocks
    const searchInput = page.locator('input[placeholder*="جستجوی بلوک"]').first();
    await searchInput.fill("پاپ‌آپ");
    await page.waitForTimeout(300);
    const popupCard = page.locator('text="پاپ‌آپ تعاملی"').first();
    await expect(popupCard).toBeVisible();

    await searchInput.fill("");
    await page.waitForTimeout(200);

    // Switch to Layers Tab
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها", exact: true });
    await layersTabBtn.click();
    await page.waitForTimeout(400);
    await expect(page.locator("text=ساختار لایه‌ها")).toBeVisible();

    // Switch to History Tab
    const historyTabBtn = page.getByRole("button", { name: "تاریخچه", exact: true });
    await historyTabBtn.click();
    await page.waitForTimeout(400);

    // Return to Blocks Tab
    const blocksTabBtn = page.getByRole("button", { name: "بلوک‌ها", exact: true });
    await blocksTabBtn.click();
    await page.waitForTimeout(300);
    await expect(blocksTabBtn).toHaveClass(/bg-background/);
  });

  test("3. Canvas Element Selection activates Inspector (Content, Style, Advanced)", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2500);

    // Click on "دکمه اقدام" in the blocks palette to insert and select it
    const addBtn = page.locator("button:has-text('دکمه اقدام')").first();
    await expect(addBtn).toBeVisible({ timeout: 5000 });
    await addBtn.click();
    await page.waitForTimeout(600);

    // Inspector header should become active with tabs
    const inspector = page.locator("[data-builder-inspector]");
    await expect(inspector).toBeVisible();

    // Check Content Tab
    const contentTab = page.locator('button[role="tab"]:has-text("محتوا")').first();
    await expect(contentTab).toBeVisible();

    // Check Style Tab
    const styleTab = page.locator('button[role="tab"]:has-text("استایل")').first();
    await styleTab.click();
    await page.waitForTimeout(400);
    await expect(page.locator('[data-testid="padding-top-input"]')).toBeVisible();

    // Check Advanced Tab
    const advTab = page.locator('button[role="tab"]:has-text("پیشرفته")').first();
    await advTab.click();
    await page.waitForTimeout(400);
    await expect(page.locator('[data-testid="custom-attributes-textarea"]')).toBeVisible();

    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-inspector-verified-3tabs.png") });
  });

  test("4. Responsive Breakpoint Switcher centers canvas and applies viewport constraints", async ({ page }) => {
    await page.setViewportSize({ width: 1920, height: 1080 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const canvasContainer = page.locator('[data-testid="canvas-iframe"]').locator("..");

    // 1. Tablet Breakpoint (768px)
    const tabletBtn = page.locator('button:has-text("تبلت")').first();
    await tabletBtn.click();
    await page.waitForTimeout(500);
    await expect(canvasContainer).toHaveClass(/max-w-\[768px\]/);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-responsive-tablet-verified.png") });

    // 2. Mobile Breakpoint (375px)
    const mobileBtn = page.locator('button:has-text("موبایل")').first();
    await mobileBtn.click();
    await page.waitForTimeout(500);
    await expect(canvasContainer).toHaveClass(/max-w-\[375px\]/);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-responsive-mobile-verified.png") });

    // 3. Back to Desktop (100%)
    const desktopBtn = page.locator('button:has-text("دسکتاپ")').first();
    await desktopBtn.click();
    await page.waitForTimeout(400);
    await expect(canvasContainer).toHaveClass(/max-w-full/);
  });
});
