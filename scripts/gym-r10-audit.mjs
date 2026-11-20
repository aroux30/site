import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-10/before");

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
  const tmp = path.join(BACKEND_DIR, `.gym-r10-tok-${Date.now()}.py`);
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

  console.log("Navigating to builder studio for round 10 audit on port 3200...");
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Initial Studio View
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "01-studio-clean.png") });

  // 2. Add Product Variants Block
  const basicBlocksSubTab = page.getByRole("button", { name: /بلوک‌ها/i });
  await basicBlocksSubTab.click();
  await page.waitForTimeout(400);

  const searchInput = page.getByPlaceholder("جستجوی بلوک پایه...");
  await searchInput.fill("تنوع محصول");
  await page.waitForTimeout(300);

  const variantsCard = page.locator("button", { hasText: "تنوع محصول" }).first();
  if (await variantsCard.isVisible()) {
    await variantsCard.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "02-variants-inspector.png") });
  }

  // 3. Add Star Rating Block
  await searchInput.fill("امتیاز ستاره‌ای");
  await page.waitForTimeout(300);

  const starCard = page.locator("button", { hasText: "امتیاز ستاره‌ای" }).first();
  if (await starCard.isVisible()) {
    await starCard.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "03-star-rating-inspector.png") });
  }

  // 4. Add Cart Summary Block
  await searchInput.fill("خلاصه سبد خرید");
  await page.waitForTimeout(300);

  const cartSummaryCard = page.locator("button", { hasText: "خلاصه سبد خرید" }).first();
  if (await cartSummaryCard.isVisible()) {
    await cartSummaryCard.click();
    await page.waitForTimeout(600);
    await page.screenshot({ path: path.join(ARTIFACTS_DIR, "04-cart-summary-inspector.png") });
  }

  // 5. Canvas with ecommerce blocks
  await page.screenshot({ path: path.join(ARTIFACTS_DIR, "05-canvas-ecommerce-blocks.png") });

  fs.writeFileSync(path.join(ARTIFACTS_DIR, "audit-report.json"), JSON.stringify({ consoleErrors }, null, 2));
  console.log("Round 10 audit complete.");

  await browser.close();
}

run().catch((err) => {
  console.error("Run failed:", err);
  process.exit(1);
});
