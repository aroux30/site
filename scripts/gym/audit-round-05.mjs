import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-05/${STAGE}`);
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

// Generate 50+ elements nested fixture
function generateHeavyPageAST() {
  const rootElements = [];
  let totalCount = 0;

  for (let c = 1; c <= 6; c++) {
    const children = [];
    for (let w = 1; w <= 8; w++) {
      totalCount++;
      children.push({
        id: `el_stress_${c}_${w}`,
        name: `ویجت ردیف ${c} شماره ${w}`,
        type: "widget",
        widgetType: w % 2 === 0 ? "heading" : "text_editor",
        widgetProps: {
          text: `عنوان استرس تست ${c}-${w} متن تستی فارسی جهت ارزیابی کارایی رندر در درخت ۵۰+ المان`,
          content: `<p>پاراگراف نمونه برای ویجت شماره ${totalCount} جهت ارزیابی سرعت رندرینگ و نبود نشت حافظه.</p>`,
        },
        styles: { mobile: {} },
        children: [],
      });
    }
    rootElements.push({
      id: `el_cont_stress_${c}`,
      name: `کانتینر بخش ${c}`,
      type: "container",
      layout: { kind: "flex", direction: "column", gap: { value: 12, unit: "px" } },
      styles: { mobile: {} },
      children,
    });
    totalCount++;
  }

  return {
    schemaVersion: 1,
    title: "E2E Heavy Stress Test (50+ Elements)",
    slug: "e2e-isolated-scratchpad",
    globalStyles: {},
    rootElements,
  };
}

async function runRound05Audit() {
  console.log(`>>> [Gym Round 05: 50kg] Stress Test (50+ Elements), Network Resilience, Edge Cases [Stage: ${STAGE}]...`);
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
    // 1. Inject heavy page with 50+ elements
    console.log("    1. Injecting 50+ elements heavy AST fixture...");
    const heavyAst = generateHeavyPageAST();

    const patchRes = await page.request.patch(`${BASE_URL}/api/v1/content/admin/pages/aa5e98ad-e380-4e6f-90ad-5d8c9ef7d7a7`, {
      data: { builder_data: heavyAst, status: "published" },
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    });
    findings.tests.heavyAstInjection = { status: patchRes.status(), ok: patchRes.ok() };

    // 2. Measure render performance in Studio
    console.log("    2. Measuring render latency of 50+ elements page in Builder Studio...");
    const t0 = Date.now();
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
    const tRender = Date.now() - t0;
    findings.tests.renderLatencyMs = tRender;
    console.log(`       Render time: ${tRender}ms`);

    await page.waitForTimeout(2000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    const elementCount = await frame.locator("[data-element-id]").count();
    findings.tests.renderedElementCount = elementCount;
    console.log(`       Rendered DOM nodes in canvas: ${elementCount}`);

    const shotHeavy = path.join(ARTIFACTS_DIR, "01-heavy-page-stress.png");
    await page.screenshot({ path: shotHeavy });

    // 3. Check LayersTree under 50+ elements stress
    console.log("    3. Auditing LayersTree under 50+ elements stress...");
    const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" });
    if (await layersTabBtn.isVisible()) {
      await layersTabBtn.click();
      await page.waitForTimeout(1000);
      const layersCount = await page.locator("[data-layer-row]").count();
      findings.tests.layersRowCount = layersCount;
      console.log(`       LayersTree row count: ${layersCount}`);

      const shotLayers = path.join(ARTIFACTS_DIR, "02-layers-tree-stress.png");
      await page.locator("aside").first().screenshot({ path: shotLayers });
    }

    // 4. Test Extreme Long Persian Text Wrapping without spaces
    console.log("    4. Testing extreme long Persian string wrapping...");
    const extremeText = "یک_متن_بسیار_طولانی_بدون_فاصله_جهت_بررسی_سرریز_افقی_و_شکست_کلمات_فارسی_در_بوم_ویرایشگر_صفحه_ساز_دیداری_پلتفرم_ایکامرس_ایران_که_نباید_کادر_را_بشکند_و_باید_به_طور_کامل_در_عرض_والد_بشکند";
    const headingEl = frame.locator("h2").first();
    if (await headingEl.isVisible()) {
      await headingEl.click();
      await page.waitForTimeout(500);

      const textInput = page.locator("input[class*='h-8']").first();
      if (await textInput.isVisible()) {
        await textInput.fill(extremeText);
        await page.waitForTimeout(600);

        // Check if canvas element horizontal scroll width matches client width
        const overflow = await headingEl.evaluate((el) => el.scrollWidth > el.clientWidth + 5);
        findings.tests.extremeTextOverflow = overflow;

        const shotWrapping = path.join(ARTIFACTS_DIR, "03-long-text-wrapping.png");
        await page.locator("main.flex-1").first().screenshot({ path: shotWrapping });
      }
    }

    // 5. Test Autosave Network Failure Resilience
    console.log("    5. Testing Autosave network failure resilience (isDirty retention)...");
    await page.route("**/api/v1/content/admin/pages/**", (route) => {
      console.log("       Intercepted and aborted autosave request to simulate network drop.");
      route.abort();
    });

    // Make an edit to trigger autosave attempt
    const draftSaveBtn = page.getByRole("button", { name: "ذخیره پیش‌نویس" });
    if (await draftSaveBtn.isVisible()) {
      await draftSaveBtn.click();
      await page.waitForTimeout(1500);
    }

    const shotAutosave = path.join(ARTIFACTS_DIR, "04-autosave-error-resilience.png");
    await page.screenshot({ path: shotAutosave });

    // 6. Test Admin Themes Revisions View
    console.log("    6. Auditing /admin/themes revisions and clones...");
    await page.unrouteAll({ behavior: "ignoreErrors" });
    await page.goto(`${BASE_URL}/admin/themes`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotThemes = path.join(ARTIFACTS_DIR, "05-themes-revisions.png");
    await page.screenshot({ path: shotThemes });

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 05 audit complete. Saved to: ${reportPath}`);
}

runRound05Audit().catch((err) => {
  console.error("Round 05 audit failure:", err);
  process.exit(1);
});
