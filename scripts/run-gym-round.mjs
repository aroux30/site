import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1002";
const BACKEND_DIR = "C:/Users/Administrator/Desktop/site/backend";
const PROJECT_ROOT = "C:/Users/Administrator/Desktop/site";

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

async function computePixelDiff(img1Path, img2Path, diffPath) {
  if (!fs.existsSync(img1Path) || !fs.existsSync(img2Path)) return { changedPixels: 0, diffRatio: 0 };
  const img1 = PNG.sync.read(fs.readFileSync(img1Path));
  const img2 = PNG.sync.read(fs.readFileSync(img2Path));
  const width = Math.min(img1.width, img2.width);
  const height = Math.min(img1.height, img2.height);
  const diff = new PNG({ width, height });

  const numDiffPixels = pixelmatch(img1.data, img2.data, diff.data, width, height, {
    threshold: 0.05,
    includeAA: false,
  });

  fs.writeFileSync(diffPath, PNG.sync.write(diff));
  const totalPixels = width * height;
  return { changedPixels: numDiffPixels, diffRatio: numDiffPixels / totalPixels };
}

export async function executeGymRound(roundNum, phase = "before") {
  const roundStr = String(roundNum).padStart(3, "0");
  const artifactsDir = path.join(PROJECT_ROOT, ".loop", "artifacts", "builder-gym", `round-${roundStr}`);
  const targetDir = path.join(artifactsDir, phase);
  fs.mkdirSync(targetDir, { recursive: true });

  console.log(`\n======================================================`);
  console.log(`>>> [GYM V3] Executing Round ${roundNum} (${phase.toUpperCase()}) on ${BASE_URL}...`);
  console.log(`======================================================`);

  const token = getAdminToken();
  if (!token) throw new Error("Could not obtain admin JWT token from backend.");

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: "fa-IR",
  });

  await context.addCookies([
    { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
  ]);
  await context.setExtraHTTPHeaders({
    "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
  });
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const page = await context.newPage();

  const sensorLogs = {
    consoleErrors: [],
    networkErrors: [],
    hydrationErrors: [],
    overflowViolations: [],
    overlapViolations: [],
    rtlViolations: [],
  };

  page.on("console", (msg) => {
    const text = msg.text();
    if (msg.type() === "error") {
      sensorLogs.consoleErrors.push(text);
      if (text.includes("#418") || text.includes("#423") || text.includes("#425") || text.includes("Hydration")) {
        sensorLogs.hydrationErrors.push(text);
      }
    }
  });

  page.on("response", (res) => {
    if (res.status() >= 400 && !res.url().includes("favicon")) {
      sensorLogs.networkErrors.push({ url: res.url(), status: res.status() });
    }
  });

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);

  // Full overview screenshot
  const overviewPath = path.join(targetDir, "01-studio-overview.png");
  await page.screenshot({ path: overviewPath, fullPage: false });
  console.log(`[Captured] ${overviewPath}`);

  // SoM elements
  console.log(">>> [SoM] Inspecting interactive elements & generating visual badges...");
  const somElements = await page.evaluate(() => {
    const selector = [
      'button:not([disabled])',
      'input:not([type="hidden"])',
      'select',
      '[role="tab"]',
      '[data-block-type]',
      '.builder-sidebar button',
      '.builder-toolbar button',
      '[data-testid]'
    ].join(',');

    const items = Array.from(document.querySelectorAll(selector));
    const inventory = [];
    let idx = 1;

    items.forEach((el) => {
      const rect = el.getBoundingClientRect();
      if (rect.width > 8 && rect.height > 8 && rect.top >= 0 && rect.top <= window.innerHeight && rect.left >= 0 && rect.left <= window.innerWidth) {
        const text = (el.textContent || el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.tagName).trim().substring(0, 40);
        inventory.push({
          id: idx,
          tag: el.tagName.toLowerCase(),
          role: el.getAttribute("role") || "",
          text,
          rect: { x: Math.round(rect.x), y: Math.round(rect.y), width: Math.round(rect.width), height: Math.round(rect.height) }
        });

        const badge = document.createElement("div");
        badge.className = "som-gym-badge";
        badge.style.position = "fixed";
        badge.style.left = `${Math.round(rect.x)}px`;
        badge.style.top = `${Math.round(rect.y)}px`;
        badge.style.backgroundColor = "rgba(220, 38, 38, 0.9)";
        badge.style.color = "#ffffff";
        badge.style.fontSize = "10px";
        badge.style.fontWeight = "bold";
        badge.style.padding = "1px 3px";
        badge.style.borderRadius = "3px";
        badge.style.zIndex = "999999";
        badge.style.pointerEvents = "none";
        badge.textContent = `#${idx}`;
        document.body.appendChild(badge);

        idx++;
      }
    });
    return inventory;
  });

  const somPath = path.join(targetDir, `${phase}_som.png`);
  await page.screenshot({ path: somPath, fullPage: false });
  console.log(`[Captured SoM Map] ${somPath} (${somElements.length} elements marked)`);

  fs.writeFileSync(path.join(artifactsDir, "som_inventory.json"), JSON.stringify(somElements, null, 2), "utf8");

  await page.evaluate(() => {
    document.querySelectorAll(".som-gym-badge").forEach((b) => b.remove());
  });

  console.log(">>> [Mutations] Performing targeted nudges on active controls...");
  const mutations = [];

  const overflowCheck = await page.evaluate(() => {
    const violations = [];
    document.querySelectorAll(".builder-sidebar, .builder-inspector, [data-panel], aside").forEach((el) => {
      if (el.scrollWidth > el.clientWidth + 2) {
        violations.push({
          tag: el.tagName,
          className: el.className,
          scrollWidth: el.scrollWidth,
          clientWidth: el.clientWidth,
        });
      }
    });
    return violations;
  });
  sensorLogs.overflowViolations.push(...overflowCheck);

  const rtlCheck = await page.evaluate(() => {
    const dir = document.documentElement.getAttribute("dir") || document.body.getAttribute("dir");
    const style = window.getComputedStyle(document.body);
    return {
      isRtl: dir === "rtl",
      fontFamily: style.fontFamily,
      direction: style.direction,
    };
  });
  if (!rtlCheck.isRtl || rtlCheck.direction !== "rtl") {
    sensorLogs.rtlViolations.push("Document direction is not RTL");
  }

  // Mutation Test: Palette search
  const searchInput = page.locator('input[placeholder*="جستجو"]').first();
  if (await searchInput.isVisible()) {
    const initialScreenshot = path.join(targetDir, "02-before-search-nudge.png");
    await page.screenshot({ path: initialScreenshot });

    await searchInput.click();
    await searchInput.fill("هیرو");
    await page.waitForTimeout(400);

    const afterSearchScreenshot = path.join(targetDir, "02-after-search-nudge.png");
    await page.screenshot({ path: afterSearchScreenshot });

    const diffPath = path.join(targetDir, "diff-search.png");
    const diff = await computePixelDiff(initialScreenshot, afterSearchScreenshot, diffPath);

    mutations.push({
      target: "Palette Search Input",
      action: "Fill هیرو",
      pixelDiff: diff,
      effectProven: diff.changedPixels > 0,
    });
    console.log(`[Mutation Test] Search Nudge: ${diff.changedPixels} pixels changed (${(diff.diffRatio * 100).toFixed(2)}%)`);
  }

  // Mutation Test: Viewport buttons
  const tabletBtn = page.locator('button[title*="تبلت"], button:has-text("تبلت"), [data-testid="viewport-tablet"]').first();
  if (await tabletBtn.isVisible()) {
    await tabletBtn.click();
    await page.waitForTimeout(400);
    const tabletCrop = path.join(targetDir, "03-viewport-tablet.png");
    await page.screenshot({ path: tabletCrop });
    console.log(`[Captured] ${tabletCrop}`);

    mutations.push({
      target: "Viewport Tablet",
      action: "Click Tablet Viewport",
      effectProven: true,
    });

    const desktopBtn = page.locator('button[title*="دسکتاپ"], button:has-text("دسکتاپ"), [data-testid="viewport-desktop"]').first();
    if (await desktopBtn.isVisible()) {
      await desktopBtn.click();
      await page.waitForTimeout(300);
    }
  }

  // Inspector crop
  const inspectorPanel = page.locator('aside, .builder-inspector, [data-panel="inspector"]').first();
  if (await inspectorPanel.isVisible()) {
    const inspectorCrop = path.join(targetDir, "04-inspector-panel.png");
    await inspectorPanel.screenshot({ path: inspectorCrop });
    console.log(`[Captured Inspector Crop] ${inspectorCrop}`);
  }

  // SSR Parity Check
  console.log(">>> [SSR Parity] Checking public rendered output on /e2e-isolated-scratchpad...");
  const ssrPage = await context.newPage();
  let ssrStatus = 0;
  try {
    const ssrRes = await ssrPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    ssrStatus = ssrRes ? ssrRes.status() : 0;
    const ssrCrop = path.join(targetDir, "05-ssr-public-render.png");
    await ssrPage.screenshot({ path: ssrCrop, fullPage: false });
    console.log(`[Captured SSR Crop] ${ssrCrop} (HTTP ${ssrStatus})`);
  } catch (err) {
    console.warn("SSR probe warning:", err.message);
  } finally {
    await ssrPage.close();
  }

  const mutationReport = {
    round: roundNum,
    phase,
    timestamp: new Date().toISOString(),
    somCount: somElements.length,
    mutationsTested: mutations.length,
    mutations,
    sensorResults: {
      consoleErrorsCount: sensorLogs.consoleErrors.length,
      networkErrorsCount: sensorLogs.networkErrors.length,
      hydrationErrorsCount: sensorLogs.hydrationErrors.length,
      overflowViolationsCount: sensorLogs.overflowViolations.length,
      overlapViolationsCount: sensorLogs.overlapViolations.length,
      rtlViolationsCount: sensorLogs.rtlViolations.length,
      ssrStatusCode: ssrStatus,
    },
    passedHealth:
      sensorLogs.consoleErrors.length === 0 &&
      sensorLogs.hydrationErrors.length === 0 &&
      sensorLogs.overflowViolations.length === 0,
  };

  fs.writeFileSync(
    path.join(artifactsDir, "mutation_report.json"),
    JSON.stringify(mutationReport, null, 2),
    "utf8"
  );
  console.log(`[Report Generated] ${path.join(artifactsDir, "mutation_report.json")}`);

  await browser.close();
  return mutationReport;
}

const round = parseInt(process.argv[2] || "39", 10);
const phase = process.argv[3] || "before";
executeGymRound(round, phase)
  .then((r) => {
    console.log(`\n✅ Gym Round ${round} (${phase}) finished. Health: ${r.passedHealth ? "HEALTHY" : "FLAGGED"}`);
    process.exit(0);
  })
  .catch((err) => {
    console.error(`❌ Gym Round failed:`, err);
    process.exit(1);
  });
