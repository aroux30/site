import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before"; // "before" or "after"
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-01/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runAudit() {
  console.log(`>>> [Gym Round 01] Running audit capture for stage: [${STAGE}]...`);
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
        state: { user: { id: "admin-1", phone: "09123456789", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  const networkErrors = [];

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

  const findings = {
    stage: STAGE,
    timestamp: new Date().toISOString(),
    pages: {},
    consoleErrors,
    networkErrors,
    overflows: [],
  };

  const pagesToTest = [
    { name: "storefront", path: "/" },
    { name: "products", path: "/products" },
    { name: "admin_themes", path: "/admin/themes" },
    { name: "admin_forms", path: "/admin/forms" },
    { name: "builder_studio", path: "/e2e-isolated-scratchpad?visual_editor=true" },
  ];

  for (const p of pagesToTest) {
    console.log(`    Testing ${p.name} (${p.path})...`);
    try {
      await page.goto(`${BASE_URL}${p.path}`, { waitUntil: "domcontentloaded", timeout: 35000 });
      await page.waitForTimeout(1500);

      // Check horizontal overflow
      const overflow = await page.evaluate(() => {
        const docW = document.documentElement.scrollWidth;
        const winW = window.innerWidth;
        return { hasOverflow: docW > winW, scrollWidth: docW, innerWidth: winW };
      });
      if (overflow.hasOverflow) {
        findings.overflows.push({ page: p.name, ...overflow });
      }

      // Capture screenshot
      const shotPath = path.join(ARTIFACTS_DIR, `${p.name}.png`);
      await page.screenshot({ path: shotPath, fullPage: false });
      findings.pages[p.name] = { shotPath, overflow };
    } catch (err) {
      console.warn(`    Failed to capture ${p.name}:`, err.message);
      findings.pages[p.name] = { error: err.message };
    }
  }

  // Also test Dark Mode on storefront
  try {
    console.log("    Testing storefront in Dark Mode...");
    await page.goto(`${BASE_URL}/`, { waitUntil: "domcontentloaded" });
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await page.waitForTimeout(600);
    const darkShot = path.join(ARTIFACTS_DIR, "storefront-dark.png");
    await page.screenshot({ path: darkShot });
    findings.pages["storefront_dark"] = { shotPath: darkShot };
  } catch (err) {
    console.warn("Dark mode capture error:", err.message);
  }

  await browser.close();

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Audit complete for [${STAGE}]. Report written to: ${reportPath}`);
}

runAudit().catch((err) => {
  console.error("Audit failure:", err);
  process.exit(1);
});
