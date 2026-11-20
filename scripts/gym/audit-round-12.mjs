import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const req = createRequire("C:/Users/Administrator/Desktop/site/frontend/package.json");
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const STAGE = process.argv[2] || "before";
const ARTIFACTS_DIR = path.resolve(`C:/Users/Administrator/Desktop/site/.loop/artifacts/gym/round-12/${STAGE}`);
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
  const tmp = path.join(BACKEND_DIR, `.gym-r12-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runRound12Audit() {
  console.log(`>>> [Gym Round 12: Blog & Editorial Flow Overload] Stage: [${STAGE}]...`);
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
    // 1. Visit Blog Main Page /blog
    console.log("    1. Navigating to /blog...");
    await page.goto(`${BASE_URL}/blog`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotBlog = path.join(ARTIFACTS_DIR, "01-blog-main.png");
    await page.screenshot({ path: shotBlog });
    findings.tests.blogMain = { shot: shotBlog };

    // 2. Visit Admin Blog Management /admin/blog
    console.log("    2. Navigating to /admin/blog...");
    await page.goto(`${BASE_URL}/admin/blog`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotAdminBlog = path.join(ARTIFACTS_DIR, "02-admin-blog.png");
    await page.screenshot({ path: shotAdminBlog });
    findings.tests.adminBlog = { shot: shotAdminBlog };

    // 3. Visit Author Archive /author/test-author
    console.log("    3. Navigating to /author/test-author...");
    await page.goto(`${BASE_URL}/author/test-author`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const shotAuthor = path.join(ARTIFACTS_DIR, "03-author-archive.png");
    await page.screenshot({ path: shotAuthor });
    findings.tests.authorArchive = { shot: shotAuthor };

  } finally {
    await browser.close();
  }

  const reportPath = path.join(ARTIFACTS_DIR, "findings.json");
  fs.writeFileSync(reportPath, JSON.stringify(findings, null, 2), "utf8");
  console.log(`>>> Round 12 audit capture complete. Saved to: ${reportPath}`);
}

runRound12Audit().catch((err) => {
  console.error("Round 12 audit failure:", err);
  process.exit(1);
});
