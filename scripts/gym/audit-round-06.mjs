import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-06/${STAGE}`);
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r06-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound06Audit() {
  console.log(`>>> [Gym Round 06: +10kg Infinite Overload] Deep UX, Focus Rings, Keyboard & Toasts [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();
  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    tests: {},
  };

  try {
    // 1. Test Skip to Content Link on initial Tab press
    console.log("    1. Testing Skip-to-content focus visibility on Tab key...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    await page.keyboard.press("Tab");
    await page.waitForTimeout(300);

    const skipLink = page.locator("a[href='#main-content']");
    const isSkipFocused = await skipLink.evaluate((el) => document.activeElement === el);
    findings.tests.skipLinkFocus = { isFocused: isSkipFocused };

    const shotSkip = path.join(ARTIFACTS_DIR, "01-keyboard-skip-link.png");
    await page.screenshot({ path: shotSkip });

    // 2. Tab into Header Navigation controls
    console.log("    2. Tabbing across Header Navigation to verify Focus Rings...");
    for (let i = 0; i < 5; i++) {
      await page.keyboard.press("Tab");
      await page.waitForTimeout(150);
    }

    const activeEl = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el) return null;
      const style = window.getComputedStyle(el);
      return {
        tag: el.tagName,
        outline: style.outline,
        boxShadow: style.boxShadow,
        hasVisibleFocus: style.outlineStyle !== "none" || style.boxShadow !== "none",
      };
    });
    findings.tests.headerFocus = activeEl;

    const shotHeaderFocus = path.join(ARTIFACTS_DIR, "02-header-focus-rings.png");
    await page.screenshot({ path: shotHeaderFocus });

    // 3. Test LayersTree in Studio
    console.log("    3. Auditing LayersTree in Builder Studio...");
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" });
    if (await layersTabBtn.isVisible()) {
      await layersTabBtn.click();
      await page.waitForTimeout(800);
    }

    const shotLayers = path.join(ARTIFACTS_DIR, "03-layers-tree-keyboard-nav.png");
    await page.locator("aside").first().screenshot({ path: shotLayers });

    // 4. Test Toast notification appearance and contrast
    console.log("    4. Triggering Toast notification...");
    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    if (await draftSaveBtn.isVisible()) {
      await draftSaveBtn.click();
      await page.waitForTimeout(1000);
    }

    const shotToast = path.join(ARTIFACTS_DIR, "04-toast-notification.png");
    await page.screenshot({ path: shotToast });

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 06 audit complete. Saved to: ${reportPath}`);
}

runRound06Audit().catch((err) => {
  console.error("Round 06 audit failure:", err);
  process.exit(1);
});
