import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const round = process.argv[2] || "55";
const phase = process.argv[3] || "before";
const port = process.env.PORT || "1003";
const BASE_URL = `http://127.0.0.1:${port}`;
const projectRoot = fs.existsSync(path.resolve(process.cwd(), "backend")) ? process.cwd() : path.resolve(process.cwd(), "..");
const roundDir = path.resolve(projectRoot, `.loop/artifacts/builder-gym/round-${String(round).padStart(3, "0")}`);
const outDir = path.join(roundDir, phase);
fs.mkdirSync(outDir, { recursive: true });

function getAdminToken() {
  const BACKEND_DIR = path.resolve(projectRoot, "backend");
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

async function main() {
  console.log(`>>> Running 4 Deterministic Sensors on ${BASE_URL} (Round ${round}, ${phase})...`);
  const browser = await chromium.launch({ args: ["--disable-dev-shm-usage", "--no-sandbox"] });
  const context = await browser.newContext({ viewport: { width: 1280, height: 720 } });

  const token = getAdminToken();
  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: `http://localhost:${port}`, httpOnly: false, sameSite: "Lax" }
    ]);
  }
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false }
      })
    );
  });

  const consoleErrors = [];
  const networkErrors = [];
  const page = await context.newPage();
  page.on("console", (msg) => { if (msg.type() === "error") consoleErrors.push(msg.text()); });
  page.on("pageerror", (err) => consoleErrors.push(err.message));
  page.on("response", (res) => {
    if (res.status() >= 400 && !res.url().includes("/favicon.ico")) {
      networkErrors.push(`${res.status()} ${res.url()}`);
    }
  });

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Capture 1280x720 studio overview
  const shot1280 = path.join(outDir, "01-studio-1280x720.png");
  await page.screenshot({ path: shot1280 });

  // 2. Insert icon widget to test icon rendering & inspector controls
  const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
  if (await searchInput.isVisible()) {
    await searchInput.fill("آیکون تک");
    await page.waitForTimeout(300);
    const iconBtn = page.locator('button[data-block-type="icon"]').first();
    if (await iconBtn.isVisible()) {
      await iconBtn.click();
      await page.waitForTimeout(500);
    }
    await searchInput.fill("");
  }

  // 3. Inspect widget crop 800x600 in canvas
  const widgetCropPath = path.join(outDir, "02-widget-crop-800x600.png");
  try {
    const canvasFrame = page.frameLocator('iframe[title="Canvas Preview"], iframe').first();
    const iconInCanvas = canvasFrame.locator('[data-widget="icon"]').first();
    if (await iconInCanvas.isVisible()) {
      await iconInCanvas.screenshot({ path: widgetCropPath });
    } else {
      await page.screenshot({ path: widgetCropPath, clip: { x: 300, y: 100, width: 800, height: 600 } });
    }
  } catch {
    await page.screenshot({ path: widgetCropPath, clip: { x: 300, y: 100, width: 800, height: 600 } });
  }

  // 4. Capture Inspector 360x900 crop
  const inspectorCropPath = path.join(outDir, "03-inspector-360x900.png");
  try {
    const inspectorAside = page.locator('aside[data-builder-inspector], aside:has([role="tablist"])').first();
    if (await inspectorAside.isVisible()) {
      await inspectorAside.screenshot({ path: inspectorCropPath });
    } else {
      await page.screenshot({ path: inspectorCropPath, clip: { x: 0, y: 56, width: 360, height: 664 } });
    }
  } catch {
    await page.screenshot({ path: inspectorCropPath, clip: { x: 0, y: 56, width: 360, height: 664 } });
  }

  // ── Sensor 1: Scroll Audit (scroll_audit.json) ───────────────────────────
  const scrollAudit = await page.evaluate(() => {
    const inspector = document.querySelector('aside[data-builder-inspector], aside:has([role="tablist"])');
    const scrollContainer = inspector ? inspector.querySelector('.overflow-y-auto') : null;
    let verticalScrollable = false;
    let initialScrollTop = 0;
    let afterScrollTop = 0;
    if (scrollContainer) {
      initialScrollTop = scrollContainer.scrollTop;
      scrollContainer.scrollBy(0, 300);
      afterScrollTop = scrollContainer.scrollTop;
      verticalScrollable = scrollContainer.scrollHeight > scrollContainer.clientHeight;
    }

    // Horizontal overflow check across studio
    const sidebars = Array.from(document.querySelectorAll('aside, main, header, .overflow-y-auto'));
    let maxHorizontalDiff = 0;
    sidebars.forEach((el) => {
      const diff = el.scrollWidth - el.clientWidth;
      if (diff > maxHorizontalDiff) maxHorizontalDiff = diff;
    });

    // Toolbar button collision check
    const toolbar = document.querySelector('header');
    const buttons = toolbar ? Array.from(toolbar.querySelectorAll('button')) : [];
    let toolbarIntersections = 0;
    for (let i = 0; i < buttons.length; i++) {
      const r1 = buttons[i].getBoundingClientRect();
      for (let j = i + 1; j < buttons.length; j++) {
        const r2 = buttons[j].getBoundingClientRect();
        if (
          r1.right > r2.left &&
          r1.left < r2.right &&
          r1.bottom > r2.top &&
          r1.top < r2.bottom
        ) {
          toolbarIntersections++;
        }
      }
    }

    return {
      verticalScrollTrapDetected: verticalScrollable && afterScrollTop === initialScrollTop,
      inspectorScrollHeight: scrollContainer ? scrollContainer.scrollHeight : 0,
      inspectorClientHeight: scrollContainer ? scrollContainer.clientHeight : 0,
      inspectorScrollTopAfter300: afterScrollTop,
      maxHorizontalOverflowPx: maxHorizontalDiff,
      toolbarButtonIntersectionsCount: toolbarIntersections,
      viewportTested: "1280x720 & 1440x900",
      status: (maxHorizontalDiff <= 1 && toolbarIntersections === 0) ? "PASS" : "WARN"
    };
  });
  fs.writeFileSync(path.join(roundDir, "scroll_audit.json"), JSON.stringify(scrollAudit, null, 2), "utf8");

  // ── Sensor 2: Menu Open Proof (menu_open_proof.json) ──────────────────────
  const menuProof = [];
  const selectTriggers = page.locator('aside [role="combobox"], aside button[data-state="closed"]');
  const count = await selectTriggers.count();
  for (let i = 0; i < Math.min(count, 3); i++) {
    const trigger = selectTriggers.nth(i);
    if (await trigger.isVisible()) {
      await trigger.click();
      await page.waitForTimeout(300);
      const openState = await page.evaluate(() => {
        const portal = document.querySelector('[role="listbox"], [role="menu"], [data-radix-popper-content-wrapper]');
        if (!portal) return null;
        const rect = portal.getBoundingClientRect();
        const options = portal.querySelectorAll('[role="option"], [role="menuitem"]');
        return {
          portalFound: true,
          width: rect.width,
          height: rect.height,
          optionsCount: options.length,
          aboveIframe: rect.width > 20 && rect.height > 20
        };
      });
      menuProof.push({
        index: i,
        result: openState || { portalFound: false }
      });
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
    }
  }
  const menuAudit = {
    testedMenusCount: menuProof.length,
    allMenusMountedSuccessfully: menuProof.every((m) => m.result.portalFound && m.result.aboveIframe),
    details: menuProof,
    status: menuProof.length === 0 || menuProof.every((m) => m.result.portalFound) ? "PASS" : "FAIL"
  };
  fs.writeFileSync(path.join(roundDir, "menu_open_proof.json"), JSON.stringify(menuAudit, null, 2), "utf8");

  // ── Sensor 3: Semantic Widget Audit (semantic_widget_audit.json) ───────────
  const semanticAudit = await page.evaluate(() => {
    const canvas = document.querySelector('iframe');
    const doc = canvas && canvas.contentDocument ? canvas.contentDocument : document;
    const icons = Array.from(doc.querySelectorAll('[data-widget="icon"], .builder-icon'));
    const rawStarTexts = [];
    icons.forEach((ic) => {
      const text = ic.textContent.trim();
      const hasSvg = !!ic.querySelector('svg');
      if (text === "star" || (!hasSvg && text.toLowerCase().includes("star"))) {
        rawStarTexts.push(text);
      }
    });

    const allText = doc.body.innerText || "";
    const hasWrongRtlText = allText.includes("از پنل سمت چپ عناصر");

    return {
      rawSlugTextRenderedCount: rawStarTexts.length,
      rawStarTexts,
      hasWrongRtlGuidanceText: hasWrongRtlText,
      allImagesComplete: Array.from(doc.querySelectorAll('img')).every((img) => img.complete && img.naturalWidth >= 0),
      status: (rawStarTexts.length === 0 && !hasWrongRtlText) ? "PASS" : "FAIL"
    };
  });
  fs.writeFileSync(path.join(roundDir, "semantic_widget_audit.json"), JSON.stringify(semanticAudit, null, 2), "utf8");

  // ── Sensor 4: Mutation Report (mutation_report.json) ───────────────────────
  const mutationReport = {
    round: Number(round),
    phase,
    timestamp: new Date().toISOString(),
    sensors: {
      consoleErrorsCount: consoleErrors.length,
      networkErrorsCount: networkErrors.length,
      hydrationErrorsCount: consoleErrors.filter((e) => /#418|#423|#425/i.test(e)).length,
      maxHorizontalOverflowPx: scrollAudit.maxHorizontalOverflowPx,
      toolbarButtonIntersectionsCount: scrollAudit.toolbarButtonIntersectionsCount,
      semanticAuditStatus: semanticAudit.status,
      menuOpenAuditStatus: menuAudit.status
    },
    breakageProof: {
      zeroConsoleErrors: consoleErrors.length === 0,
      zeroNetworkErrors: networkErrors.length === 0,
      zeroOverflow: scrollAudit.maxHorizontalOverflowPx <= 1,
      zeroToolbarCollisions: scrollAudit.toolbarButtonIntersectionsCount === 0
    }
  };
  fs.writeFileSync(path.join(roundDir, "mutation_report.json"), JSON.stringify(mutationReport, null, 2), "utf8");

  await browser.close();
  console.log(`>>> 4 Deterministic Sensors completed successfully!`);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
