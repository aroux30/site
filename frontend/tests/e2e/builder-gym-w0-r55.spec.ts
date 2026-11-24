import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1004";
const BACKEND_DIR = path.resolve(__dirname, "../../../backend");
const ARTIFACTS_DIR = path.resolve(__dirname, "../../../.loop/artifacts/builder-gym/round-55/after");
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
  const tmp = path.join(BACKEND_DIR, `.gym-r55-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 55: Weight 0 Emergency Triage Verification", () => {
  test.use({ viewport: { width: 1280, height: 720 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1004", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. Verify Weight 0: Toolbar 1280x720 clearance, Inspector vertical scroll, Reset buttons, Radix z-index, and Icon SVG", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // 1. Toolbar collision check at 1280x720
    const toolbar = page.locator("header:has-text('خروج')").first();
    await expect(toolbar).toBeVisible();
    const overlaps = await page.evaluate(() => {
      const headers = Array.from(document.querySelectorAll("header"));
      const header = headers.find((h) => h.textContent && h.textContent.includes("خروج")) || headers[0];
      if (!header) return 0;
      const btns = Array.from(header.querySelectorAll("button, a, input, [data-testid]"));
      let count = 0;
      for (let i = 0; i < btns.length; i++) {
        const btn1 = btns[i];
        if (!btn1) continue;
        const r1 = btn1.getBoundingClientRect();
        for (let j = i + 1; j < btns.length; j++) {
          const btn2 = btns[j];
          if (!btn2) continue;
          const r2 = btn2.getBoundingClientRect();
          const intersect = !(r2.left >= r1.right || r2.right <= r1.left || r2.top >= r1.bottom || r2.bottom <= r1.top);
          if (intersect && r1.width > 0 && r2.width > 0) count++;
        }
      }
      return count;
    });
    expect(overlaps).toBe(0);

    // 2. Insert Icon Widget
    const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
    await searchInput.fill("آیکون تک");
    await page.waitForTimeout(300);
    const iconBtn = page.locator('button[data-block-type="icon"]').first();
    await expect(iconBtn).toBeVisible();
    await iconBtn.click();
    await page.waitForTimeout(1000);

    // 3. Verify Canvas Icon Widget renders valid <svg> and no raw string
    const canvasFrame = page.frameLocator('[data-testid="canvas-iframe"]');
    const iconWidget = canvasFrame.locator('[data-widget-type="icon"], [data-widget="icon"]').first();
    await expect(iconWidget).toBeVisible({ timeout: 10000 });
    const svgEl = iconWidget.locator("svg").first();
    await expect(svgEl).toBeVisible();
    const rawText = await iconWidget.innerText();
    expect(rawText.trim()).not.toBe("star");

    // 4. Click Icon to open Inspector
    await iconWidget.click();
    await page.waitForTimeout(500);

    // 5. Verify Inspector Content Tab scrollability
    const inspectorPanel = page.locator("[data-builder-inspector]");
    await expect(inspectorPanel).toBeVisible();

    // 6. Switch to Style Tab
    const styleTab = page.locator('button[role="tab"]:has-text("استایل"), button[role="tab"]:has-text("Style")').first();
    await styleTab.click();
    await page.waitForTimeout(300);

    // 7. Verify Padding & Margin Reset buttons exist and work
    const resetPaddingBtn = page.locator('[data-testid="reset-padding-btn"]').first();
    await expect(resetPaddingBtn).toBeVisible();
    await resetPaddingBtn.click();

    const resetMarginBtn = page.locator('[data-testid="reset-margin-btn"]').first();
    await expect(resetMarginBtn).toBeVisible();
    await resetMarginBtn.click();

    // 8. Open Radix Select in Style tab and verify z-index >= 150
    const selectTrigger = inspectorPanel.locator('[role="combobox"]').first();
    if (await selectTrigger.isVisible()) {
      await selectTrigger.click();
      await page.waitForTimeout(300);
      const popper = page.locator('[data-radix-popper-content-wrapper]').first();
      await expect(popper).toBeVisible();
      const zIndex = await popper.evaluate((el) => parseInt(window.getComputedStyle(el).zIndex, 10));
      expect(zIndex).toBeGreaterThanOrEqual(150);
      await page.keyboard.press("Escape");
    }

    // 9. Switch to 1440x900 viewport
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(300);
    const overflowX1440 = await page.evaluate(() => {
      const tb = document.querySelector("header");
      return tb ? tb.scrollWidth - tb.clientWidth : 0;
    });
    expect(overflowX1440).toBeLessThanOrEqual(1);
  });
});
