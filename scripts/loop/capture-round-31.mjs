import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:4003";
const BACKEND_DIR = "C:/Users/Administrator/Desktop/site/backend";
const ROOT_DIR = process.cwd();

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
  const tmp = path.join(BACKEND_DIR, `.gym-r31-tok-${Date.now()}.py`);
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
  const stage = process.argv[2] || "before";
  const outDir = path.join(ROOT_DIR, `.loop/artifacts/builder-gym/round-31/${stage}`);
  fs.mkdirSync(outDir, { recursive: true });

  console.log(`>>> Capturing Round 31 artifacts (${stage}) on ${BASE_URL}...`);

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
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
      })
    );
  });

  const page = await context.newPage();
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Studio full
  await page.screenshot({ path: path.join(outDir, "01-builder-studio.png") });

  // 2. Blocks palette with new widgets (Image Box, Toggle)
  const blocksTab = page.locator('button:has-text("بلوک‌ها")').first();
  if (await blocksTab.isVisible()) {
    await blocksTab.click();
    await page.waitForTimeout(400);
  }
  await page.screenshot({ path: path.join(outDir, "02-blocks-palette-expanded.png") });

  // 3. Canvas iframe selection
  const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const firstElem = canvasFrame.locator("[data-element-id]").first();
  if (await firstElem.isVisible()) {
    await firstElem.click();
    await page.waitForTimeout(400);
  }
  await page.screenshot({ path: path.join(outDir, "03-inspector-active.png") });

  fs.writeFileSync(
    path.join(outDir, "report.json"),
    JSON.stringify({ timestamp: new Date().toISOString(), stage, status: "captured" }, null, 2),
    "utf8"
  );
  console.log(`>>> Round 31 ${stage} screenshots captured in ${outDir}`);
  await browser.close();
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
