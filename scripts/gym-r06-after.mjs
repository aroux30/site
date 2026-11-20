import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-06/after");

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

  console.log("Navigating to builder studio for after screenshots...");
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Initial full studio screenshot
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-studio-initial.png") });

  // 2. Open Patterns tab and insert landing patterns
  const patternsTab = page.getByRole("button", { name: /الگوها/i });
  await patternsTab.click();
  await page.waitForTimeout(800);
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-patterns-palette.png") });

  // Insert hero-banner pattern
  const heroCard = page.locator('[data-pattern-slug="hero-banner"]').first();
  if (await heroCard.isVisible()) {
    await heroCard.click();
    await page.waitForTimeout(1000);
  }

  // 3. Screenshot inside canvas iframe
  const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-canvas-with-pattern.png") });

  // 4. Select the nested container inside hero banner and inspect the Inspector Panel
  const nestedContainer = canvasFrame.locator('div[data-element-id] div[data-element-id]').first();
  if (await nestedContainer.isVisible()) {
    await nestedContainer.click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-element-selected-inspector.png") });
  }

  // 5. Test inserting tabs and viewing rich tabs inspector
  const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
  await basicBlocksSubTab.click();
  await page.waitForTimeout(400);

  const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
  await searchInput.fill("تب‌های محتوا");
  await page.waitForTimeout(300);

  const tabsBlockCard = page.locator("button", { hasText: "تب‌های محتوا" }).first();
  if (await tabsBlockCard.isVisible()) {
    await tabsBlockCard.click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "05-tabs-inspector-rich-controls.png") });
  }

  // Check DOM geometry
  const report = await page.evaluate(() => {
    const rightSidebar = document.querySelector("aside") || document.querySelector(".w-80") || document.querySelector(".w-72");
    const rightOverflow = rightSidebar ? rightSidebar.scrollWidth > rightSidebar.clientWidth : false;

    const iframe = document.querySelector('iframe[title="Visual Builder Canvas"]');
    const iframeDoc = iframe?.contentDocument || iframe?.contentWindow?.document;
    const iframeOverflow = iframeDoc?.documentElement ? iframeDoc.documentElement.scrollWidth > iframeDoc.documentElement.clientWidth : false;

    return {
      rightSidebarOverflow: rightOverflow,
      iframeOverflow: iframeOverflow,
      rightWidth: rightSidebar?.clientWidth,
      iframeWidth: iframe?.clientWidth,
      url: window.location.href,
    };
  });

  fs.writeFileSync(path.join(ARTIFACTS_DIR, "audit-report.json"), JSON.stringify({ report, consoleErrors }, null, 2));
  console.log("After audit complete:", report);

  await browser.close();
}

run().catch((err) => {
  console.error("Run failed:", err);
  process.exit(1);
});
