import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-03/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r03-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound03Audit() {
  console.log(`>>> [Gym Round 03: 20kg] Auditing Interactive Store Widgets & Form Submissions [Stage: ${STAGE}]...`);
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
  const consoleErrors = [];
  const networkErrors = [];
  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    tests: {},
    consoleErrors,
    networkErrors,
  };

  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push({ url: page.url(), text: msg.text() });
    }
  });

  page.on("response", (res) => {
    if (res.status() >= 400 && !res.url().includes("favicon")) {
      networkErrors.push({ url: res.url(), status: res.status() });
    }
  });

  try {
    // ── Test 1: Storefront MegaMenu & Navigation Dropdown ──────────────────
    console.log("    1. Testing Header MegaMenu Dropdown...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const categoriesMenuBtn = page.locator("button:has-text('دسته‌بندی کالاها')").first();
    if (await categoriesMenuBtn.isVisible()) {
      await categoriesMenuBtn.click();
      await page.waitForTimeout(600);
      const shotMenu = path.join(ARTIFACTS_DIR, "05-megamenu-expanded.png");
      await page.screenshot({ path: shotMenu });
      findings.tests.megaMenu = { shot: shotMenu, opened: true };
      // Close by clicking again or outside
      await page.mouse.click(10, 10);
      await page.waitForTimeout(300);
    }

    // ── Test 2: ProductCard QuickView Modal ────────────────────────────────
    console.log("    2. Testing Product QuickView Modal on /products...");
    await page.goto(`${BASE_URL}/products`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    // Look for eye or quick-view button on product cards
    const quickViewBtn = page.locator("button[title*='مشاهده سریع'], button[aria-label*='مشاهده سریع'], button:has-text('مشاهده سریع')").first();
    if (await quickViewBtn.isVisible()) {
      await quickViewBtn.click();
      await page.waitForTimeout(800);
      const shotQuickView = path.join(ARTIFACTS_DIR, "01-quickview-modal.png");
      await page.screenshot({ path: shotQuickView });
      findings.tests.quickView = { shot: shotQuickView, opened: true };

      // Close modal
      const closeDialogBtn = page.locator("button[aria-label='Close'], button:has-text('بستن')").first();
      if (await closeDialogBtn.isVisible()) {
        await closeDialogBtn.click();
        await page.waitForTimeout(300);
      } else {
        await page.keyboard.press("Escape");
        await page.waitForTimeout(300);
      }
    } else {
      console.log("       Quick-view button selector not directly visible on initial grid, checking product quick action hover...");
    }

    // ── Test 3: Form Builder Submission on Builder Scratchpad ─────────────
    console.log("    3. Testing Form Builder Submission...");
    // Submit form via API directly to simulate real Form Builder submission
    const submitPayload = {
      form_id: "gym_r03_contact_form",
      page_slug: "e2e-isolated-scratchpad",
      data: {
        fullname: "علی محمدی (تست راند ۳)",
        email: "ali.mohammadi@example.com",
        message: "پیام تستی برای راستی‌آزمایی ویجت فرم‌ساز در راند ۳",
      },
      hp_field: "", // honeypot empty
    };

    const submitRes = await page.request.post(`${BASE_URL}/api/v1/content/forms/submit`, {
      data: submitPayload,
      headers: { "Content-Type": "application/json" },
    });
    findings.tests.formSubmit = { status: submitRes.status(), ok: submitRes.ok() };

    // ── Test 4: Verify Entry in /admin/forms ───────────────────────────────
    console.log("    4. Verifying submission in /admin/forms...");
    await page.goto(`${BASE_URL}/admin/forms`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotAdminForms = path.join(ARTIFACTS_DIR, "03-form-submissions-admin.png");
    await page.screenshot({ path: shotAdminForms });
    findings.tests.adminFormsVerification = { shot: shotAdminForms };

    // ── Test 5: Check Builder Studio Interactive Widgets in Canvas ────────
    console.log("    5. Auditing Builder Studio Interactive Widgets in Canvas...");
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    // Check if ProductGrid filter buttons exist in the canvas
    const filterBtn = frame.locator("button:has-text('پرفروش‌ترین‌ها')").first();
    const filterExists = (await filterBtn.count()) > 0;
    if (filterExists) {
      await filterBtn.click();
      await page.waitForTimeout(500);
    }
    const shotBuilderWidgets = path.join(ARTIFACTS_DIR, "04-product-grid-filtered.png");
    await page.locator("main.flex-1").first().screenshot({ path: shotBuilderWidgets });
    findings.tests.builderWidgets = { shot: shotBuilderWidgets, filterExists };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 03 audit complete. Saved to: ${reportPath}`);
}

runRound03Audit().catch((err) => {
  console.error("Round 03 audit failure:", err);
  process.exit(1);
});
