import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-13/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r13-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound13Audit() {
  console.log(`>>> [Gym Round 13: Product Comparison & Matrix Overload] Stage: [${STAGE}]...`);
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
    // 1. Visit /compare (Empty state)
    console.log("    1. Navigating to /compare (empty state)...");
    await page.goto(`${BASE_URL}/compare`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const shotCompareEmpty = path.join(ARTIFACTS_DIR, "01-compare-empty.png");
    await page.screenshot({ path: shotCompareEmpty });
    findings.tests.compareEmpty = { shot: shotCompareEmpty };

    // 2. Add product to compare list via localStorage
    console.log("    2. Adding sample items to compare store and testing matrix...");
    await page.evaluate(() => {
      localStorage.setItem(
        "compare-storage",
        JSON.stringify({
          state: {
            products: [
              {
                id: "c3f93ad5-8ee5-47cd-977b-8284d079b18b",
                title: "۱۸۰۰ یوسی",
                price: 2000000,
                originalPrice: 2200000,
                rating: 4.8,
                inStock: true,
                stock: 10,
                slug: "1800-yvsy",
                sku: "UC-1800",
                images: [],
                tags: [],
                variants: [],
                attributes: [],
                createdAt: "",
                updatedAt: "",
                categoryId: "",
                specifications: { "نوع تحویل": "آنی", "پلتفرم": "موبایل" },
              },
              {
                id: "ef6f7dd7-37d9-4472-82ae-85c1a8ed412c",
                title: "۳۸۵۰ یوسی",
                price: 3850000,
                originalPrice: 4100000,
                rating: 4.9,
                inStock: true,
                stock: 5,
                slug: "3850-yvsy",
                sku: "UC-3850",
                images: [],
                tags: [],
                variants: [],
                attributes: [],
                createdAt: "",
                updatedAt: "",
                categoryId: "",
                specifications: { "نوع تحویل": "آنی", "پلتفرم": "موبایل / تبلت" },
              },
            ],
          },
        })
      );
    });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotComparePopulated = path.join(ARTIFACTS_DIR, "02-compare-matrix-populated.png");
    await page.screenshot({ path: shotComparePopulated });
    findings.tests.comparePopulated = { shot: shotComparePopulated };

    // 3. Check FloatingCompareBar on storefront with active compare items
    console.log("    3. Checking FloatingCompareBar on storefront...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotFloatingCompare = path.join(ARTIFACTS_DIR, "03-floating-compare-dock.png");
    await page.screenshot({ path: shotFloatingCompare });
    findings.tests.floatingCompare = { shot: shotFloatingCompare };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 13 audit capture complete. Saved to: ${reportPath}`);
}

runRound13Audit().catch((err) => {
  console.error("Round 13 audit failure:", err);
  process.exit(1);
});
