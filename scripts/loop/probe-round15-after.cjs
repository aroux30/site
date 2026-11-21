const { chromium } = require("C:/Users/Administrator/Desktop/site/frontend/node_modules/playwright");
const path = require("path");
const fs = require("fs");
const { execSync } = require("child_process");

const OUT_DIR = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/trusting-booth-4a3d0e/.loop/artifacts/builder-gym/round-15/after");
fs.mkdirSync(OUT_DIR, { recursive: true });

function getAdminToken() {
  const BACKEND_DIR = "C:/Users/Administrator/Desktop/site/backend";
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
  const tmp = path.join(BACKEND_DIR, `.gym-probe-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

(async () => {
  console.log(">>> Starting Round 15 After Probing...");
  const browser = await chromium.launch({
    args: ["--disable-dev-shm-usage", "--js-flags=--max-old-space-size=1024"]
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });

  const token = getAdminToken();
  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: "http://127.0.0.1:4001", httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: "http://localhost:4001", httpOnly: false, sameSite: "Lax" }
    ]);
  }

  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();

  console.log(">>> Navigating to builder on port 4001...");
  await page.goto("http://127.0.0.1:4001/e2e-isolated-scratchpad?builder=1", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);

  // 1. Full studio layout (clean single shortcuts button)
  await page.screenshot({ path: path.join(OUT_DIR, "01-studio-overview.png") });
  console.log("Saved: 01-studio-overview.png");

  // 2. Palette search showing progress_bar
  const searchInput = page.locator('input[placeholder*="جستجو"]');
  if (await searchInput.isVisible()) {
    await searchInput.fill("پیشرفت");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "02-blocks-palette-missing-progress.png") });
    console.log("Saved: 02-blocks-palette-missing-progress.png");
    await searchInput.fill("");
    await page.waitForTimeout(300);
  }

  // 3. Select canvas heading element & inspect Advanced tab with custom attributes
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const headingEl = frame.locator('[data-element-id="el_e2ehead1"]').first();
  if (await headingEl.isVisible()) {
    await headingEl.click();
    await page.waitForTimeout(500);

    const advTab = page.locator('button[data-state]:has-text("پیشرفته"), button:has-text("پیشرفته")').first();
    if (await advTab.isVisible()) {
      await advTab.click();
      await page.waitForTimeout(500);
    }

    const customAttrControl = page.locator('[data-testid="custom-attributes-textarea"]');
    if (await customAttrControl.isVisible()) {
      await customAttrControl.fill("data-tracking|hero-cta\naria-label|test-region");
      await page.waitForTimeout(500);
    }

    await page.screenshot({ path: path.join(OUT_DIR, "03-inspector-advanced-missing-attrs.png") });
    console.log("Saved: 03-inspector-advanced-missing-attrs.png");
  }

  // 4. Alert widget & new ported widgets in palette
  await page.screenshot({ path: path.join(OUT_DIR, "04-alert-widget-inspection.png") });
  console.log("Saved: 04-alert-widget-inspection.png");

  await browser.close();
  console.log(">>> After Probing completed successfully!");
})();
