const { chromium } = require("C:/Users/Administrator/Desktop/site/frontend/node_modules/playwright");
const path = require("path");
const fs = require("fs");
const { execSync } = require("child_process");

const OUT_DIR = path.resolve("C:/Users/Administrator/Desktop/site/.claude/worktrees/trusting-booth-4a3d0e/.loop/artifacts/builder-gym/round-21/after");
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
  const tmp = path.join(BACKEND_DIR, `.gym-probe21-after-tok-${Date.now()}.py`);
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
  console.log(">>> Starting Round 21 After Probing...");
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

  // 1. Full studio overview
  await page.screenshot({ path: path.join(OUT_DIR, "01-studio-overview.png") });
  console.log("Saved: 01-studio-overview.png");

  // 2. Search for off-canvas and popup
  const searchInput = page.locator('input[placeholder*="جستجو"]');
  if (await searchInput.isVisible()) {
    await searchInput.fill("کشوی کناری");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "02-palette-off-canvas.png") });
    console.log("Saved: 02-palette-off-canvas.png");

    await searchInput.fill("پاپ‌آپ");
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(OUT_DIR, "03-palette-popup.png") });
    console.log("Saved: 03-palette-popup.png");
  }

  await browser.close();
  console.log(">>> Round 21 After Probing completed successfully!");
})();
