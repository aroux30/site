import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1001";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-53/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r53-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 53: Motion Effects Animation & Keyframes Parity", () => {
  test.use({ viewport: { width: 1920, height: 1080 } });

  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1001", httpOnly: false, sameSite: "Lax" },
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

  test("1. Select bounce-in animation in advanced tab and verify builder-animate class in canvas", async ({ page }) => {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Verify studio loaded
    await expect(page.locator("text=ذخیره پیش‌نویس")).toBeVisible();

    // Add a container block
    const containerCard = page.locator('button[data-block-type="container"]').first();
    await expect(containerCard).toBeVisible();
    await containerCard.click();
    await page.waitForTimeout(600);

    // Switch to Advanced tab in inspector
    const advTab = page.locator('[role="tab"]:has-text("پیشرفته")').first();
    await expect(advTab).toBeVisible();
    await advTab.click();
    await page.waitForTimeout(400);

    // Select bounce-in animation
    const animSelect = page.locator('[data-testid="animation-type-select"]').first();
    await expect(animSelect).toBeVisible();
    await animSelect.click();
    await page.waitForTimeout(200);

    const bounceOpt = page.locator('[role="option"]:has-text("پرش ملایم")').first();
    await expect(bounceOpt).toBeVisible();
    await bounceOpt.click();
    await page.waitForTimeout(400);

    // Verify canvas iframe reflects builder-animate-bounce-in class
    const frame = page.frameLocator('[data-testid="canvas-iframe"]');
    const animatedEl = frame.locator('.builder-animate-bounce-in').first();
    await expect(animatedEl).toBeVisible();
  });
});
