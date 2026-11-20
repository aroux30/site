import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-08/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r08-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function run() {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
  });

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
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  console.log("Navigating to builder studio for round 08 after screenshots...");
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Studio initial state
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-studio-clean.png") });

  // 2. Insert accordion and capture inspector with delete buttons
  const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
  await basicBlocksSubTab.click();
  await page.waitForTimeout(400);

  const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
  await searchInput.fill("آکاردئون");
  await page.waitForTimeout(300);

  const accordionCard = page.locator("button", { hasText: "آکاردئون" }).first();
  if (await accordionCard.isVisible()) {
    await accordionCard.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-accordion-inspector-delete-controls.png") });
  }

  // 3. Open Save Page Template dialog and verify dynamic title
  const savePageTplBtn = page.getByRole("button", { name: /قالب برگه/i });
  if (await savePageTplBtn.isVisible()) {
    await savePageTplBtn.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-save-page-template-dialog-synced.png") });
    await page.keyboard.press("Escape");
    await page.waitForTimeout(400);
  }

  // 4. Capture canvas showing open accordion item 1
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-canvas-accordion-open.png") });

  fs.writeFileSync(path.join(ARTIFACTS_DIR, "audit-report.json"), JSON.stringify({ consoleErrors }, null, 2));
  console.log("Round 08 after audit complete.");

  await browser.close();
}

run().catch((err) => {
  console.error("Run failed:", err);
  process.exit(1);
});
