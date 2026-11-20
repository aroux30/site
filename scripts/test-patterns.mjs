import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-06/before");

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

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);

  // Switch to patterns tab
  const patternsTab = page.getByRole("button", { name: /الگوها/i });
  await patternsTab.click();
  await page.waitForTimeout(500);

  // Get list of all pattern slugs
  const slugs = await page.evaluate(() => {
    const cards = Array.from(document.querySelectorAll("[data-pattern-slug]"));
    return cards.map(c => ({
      slug: c.getAttribute("data-pattern-slug"),
      text: c.textContent?.trim()
    }));
  });
  console.log("Found slugs in palette:", slugs);

  // Let's test inserting:
  // 1. features pattern
  // 2. comparison table pattern
  // 3. faq pattern
  // 4. cta or lead capture
  const targetSlugs = ["features-grid", "comparison-table", "faq-accordion", "lead-capture-form", "cta-simple"];
  for (const s of targetSlugs) {
    const card = page.locator(`[data-pattern-slug="${s}"]`).first();
    if (await card.isVisible()) {
      console.log(`Inserting pattern: ${s}`);
      await card.click();
      await page.waitForTimeout(800);
    } else {
      console.log(`Pattern ${s} not directly visible, searching...`);
    }
  }

  // Take screenshot of canvas with multiple patterns
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "05-canvas-landing-patterns.png") });

  // Now test nested container selection and layout modification
  const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  // Find a container inside canvas
  const containers = canvasFrame.locator('div[data-element-id]');
  const count = await containers.count();
  console.log(`Found ${count} elements in canvas frame`);

  // Let's test modifying layout of a nested container
  const nestedContainer = canvasFrame.locator('div[data-element-id] div[data-element-id]').first();
  if (await nestedContainer.isVisible()) {
    await nestedContainer.click();
    await page.waitForTimeout(400);

    // Inspector should now show container controls
    const layoutSelect = page.locator('button[role="combobox"]').first();
    console.log("Selected nested container for testing layout updates");
  }

  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "06-nested-element-selected.png") });

  fs.writeFileSync(path.join(ARTIFACTS_DIR, "patterns-test-report.json"), JSON.stringify({ slugs, consoleErrors }, null, 2));

  await browser.close();
}

run().catch((err) => {
  console.error("Run failed:", err);
  process.exit(1);
});
