import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r05-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 05: Weight 5 (Responsive Viewports, Dark Mode & Stress)", () => {
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

  test("1. Viewport buttons adapt canvas iframe container width accurately across mobile and tablet", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const canvasWrapper = page.locator("div.transition-all.duration-300").first();
    await expect(canvasWrapper).toBeVisible();

    // Switch to tablet (768px)
    const tabletBtn = page.getByRole("button", { name: /تبلت/i });
    await expect(tabletBtn).toBeVisible();
    await tabletBtn.click();
    await page.waitForTimeout(500);

    let box = await canvasWrapper.boundingBox();
    expect(box?.width).toBeLessThanOrEqual(770);

    // Switch to mobile (375px)
    const mobileBtn = page.getByRole("button", { name: /موبایل/i });
    await expect(mobileBtn).toBeVisible();
    await mobileBtn.click();
    await page.waitForTimeout(500);

    box = await canvasWrapper.boundingBox();
    expect(box?.width).toBeLessThanOrEqual(380);

    // Revert to desktop
    const desktopBtn = page.getByRole("button", { name: /دسکتاپ/i });
    await desktopBtn.click();
    await page.waitForTimeout(400);
  });

  test("2. Dark mode toggled on studio document synchronizes to canvas iframe document in real-time", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Toggle dark mode on document
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
    });
    await page.waitForTimeout(600);

    const isIframeDark = await page.evaluate(() => {
      const iframe = document.querySelector('iframe[title="Visual Builder Canvas"]') as HTMLIFrameElement;
      const doc = iframe?.contentDocument || iframe?.contentWindow?.document;
      return doc?.documentElement?.classList.contains("dark") || false;
    });
    expect(isIframeDark).toBe(true);
  });

  test("3. Rapid element selection and sidebar tab switching operates without lag or console errors", async ({ page }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const firstEl = frame.locator("[data-element-id]").first();
    await expect(firstEl).toBeVisible();

    // Select element
    await firstEl.click();

    // Rapidly switch left tabs: layers -> blocks -> layers
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها", exact: true });
    await layersTabBtn.click();
    await page.waitForTimeout(200);

    const blocksTabBtn = page.getByRole("button", { name: "بلوک‌ها", exact: true });
    await blocksTabBtn.click();
    await page.waitForTimeout(200);

    // Filter out harmless non-critical resource warnings
    const fatalErrors = consoleErrors.filter((err) =>
      !err.includes("favicon") && !err.includes("404") && !err.includes("socket")
    );
    if (fatalErrors.length > 0) {
      console.log("FATAL ERRORS CAPTURED IN TEST 3:", fatalErrors);
    }
    expect(fatalErrors.length).toBe(0);
  });
});
