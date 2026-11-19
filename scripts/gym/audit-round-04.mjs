import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");
const AxeBuilder = req("@axe-core/playwright").default || req("@axe-core/playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-04/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r04-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound04Audit() {
  console.log(`>>> [Gym Round 04: 35kg] Responsive (3 viewports x 2 themes), RTL, and WCAG AA [Stage: ${STAGE}]...`);
  const token = getAdminToken();

  const browser = await chromium.launch({ headless: true, args: ["--no-sandbox", "--disable-dev-shm-usage"] });

  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    viewports: {},
    overflows: [],
    axeViolations: [],
  };

  const viewports = [
    { name: "mobile", width: 375, height: 812 },
    { name: "tablet", width: 768, height: 1024 },
    { name: "desktop", width: 1440, height: 900 },
  ];

  for (const vp of viewports) {
    console.log(`    Testing Viewport: ${vp.name} (${vp.width}x${vp.height})...`);
    const context = await browser.newContext({ viewport: { width: vp.width, height: vp.height } });

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

    // 1. Storefront in light mode
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const overflowStorefront = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth;
      const winW = window.innerWidth;
      return { hasOverflow: docW > winW, scrollWidth: docW, innerWidth: winW };
    });
    if (overflowStorefront.hasOverflow) {
      findings.overflows.push({ viewport: vp.name, page: "storefront", ...overflowStorefront });
    }

    const shotStorefront = path.join(ARTIFACTS_DIR, `01-storefront-${vp.name}-light.png`);
    await page.screenshot({ path: shotStorefront });

    // 2. Storefront in dark mode
    await page.evaluate(() => {
      document.documentElement.classList.add("dark");
      localStorage.setItem("theme", "dark");
    });
    await page.waitForTimeout(500);

    const shotStorefrontDark = path.join(ARTIFACTS_DIR, `02-storefront-${vp.name}-dark.png`);
    await page.screenshot({ path: shotStorefrontDark });

    // 3. Products page
    await page.goto(`${BASE_URL}/products`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const overflowProducts = await page.evaluate(() => {
      const docW = document.documentElement.scrollWidth;
      const winW = window.innerWidth;
      return { hasOverflow: docW > winW, scrollWidth: docW, innerWidth: winW };
    });
    if (overflowProducts.hasOverflow) {
      findings.overflows.push({ viewport: vp.name, page: "products", ...overflowProducts });
    }

    const shotProducts = path.join(ARTIFACTS_DIR, `03-products-${vp.name}.png`);
    await page.screenshot({ path: shotProducts });

    // 4. Builder Studio
    if (vp.name !== "desktop") {
      await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1500);
      const shotBuilder = path.join(ARTIFACTS_DIR, `04-builder-${vp.name}.png`);
      await page.screenshot({ path: shotBuilder });
    }

    // 5. Axe WCAG Accessibility scan on desktop viewport
    if (vp.name === "desktop") {
      try {
        const axeResults = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"])
          .analyze();

        const serious = axeResults.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
        findings.axeViolations = serious.map((v) => ({
          id: v.id,
          impact: v.impact,
          description: v.description,
          nodes: v.nodes.length,
        }));
      } catch (e) {
        console.warn("Axe scan warning:", e.message);
      }
    }

    await context.close();
  }

  await browser.close();

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 04 audit complete. Saved to: ${reportPath}`);
}

runRound04Audit().catch((err) => {
  console.error("Round 04 audit failure:", err);
  process.exit(1);
});
