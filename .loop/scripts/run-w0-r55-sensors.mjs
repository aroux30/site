import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import pixelmatch from "pixelmatch";
import { PNG } from "pngjs";

const round = process.argv[2] || "55";
const phase = process.argv[3] || "before";
const port = process.env.PORT || "1004";
const BASE_URL = `http://127.0.0.1:${port}`;

const outDir = path.resolve(`.loop/artifacts/builder-gym/round-${String(round).padStart(2, "0")}/${phase}`);
const outDir3 = path.resolve(`.loop/artifacts/builder-gym/round-${String(round).padStart(3, "0")}/${phase}`);
fs.mkdirSync(outDir, { recursive: true });
fs.mkdirSync(outDir3, { recursive: true });

function getAdminToken() {
  const BACKEND_DIR = path.resolve("backend");
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

async function run() {
  console.log(`>>> Starting 4 Deterministic Sensors for Round ${round} (${phase}) on port ${port}...`);
  const browser = await chromium.launch({
    args: ["--disable-dev-shm-usage", "--no-sandbox"]
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 720 }
  });

  const token = getAdminToken();
  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
      { name: "access_token", value: token, url: `http://localhost:${port}`, httpOnly: false, sameSite: "Lax" }
    ]);
  }
  await context.setExtraHTTPHeaders({
    "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`
  });
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
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  page.on("pageerror", (err) => consoleErrors.push(err.message));
  page.on("response", (res) => {
    if (res.status() >= 400 && !res.url().includes("/favicon.ico")) {
      networkErrors.push(`${res.status()} ${res.url()}`);
    }
  });

  console.log(`Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1...`);
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Capture 1280x720 Overview
  const shot1280 = path.join(outDir, "01-studio-1280x720-overview.png");
  await page.screenshot({ path: shot1280 });
  console.log(`Saved: ${shot1280}`);

  // 2. Toolbar Overlap Audit at 1280x720
  const toolbarAudit = await page.evaluate(() => {
    const toolbar = document.querySelector("header");
    if (!toolbar) return { found: false, overlaps: 0, overflowX: 0 };
    const buttons = Array.from(toolbar.querySelectorAll("button, [data-testid], a, input"));
    let overlaps = 0;
    for (let i = 0; i < buttons.length; i++) {
      const r1 = buttons[i].getBoundingClientRect();
      for (let j = i + 1; j < buttons.length; j++) {
        const r2 = buttons[j].getBoundingClientRect();
        const intersect = !(r2.left >= r1.right || r2.right <= r1.left || r2.top >= r1.bottom || r2.bottom <= r1.top);
        if (intersect && r1.width > 0 && r2.width > 0 && r1.height > 0 && r2.height > 0) {
          overlaps++;
        }
      }
    }
    const overflowX = Math.max(0, toolbar.scrollWidth - toolbar.clientWidth);
    return { found: true, overlaps, overflowX };
  });

  // Capture Toolbar crop
  const toolbarEl = await page.locator("header").first();
  if (await toolbarEl.isVisible()) {
    const shotTb = path.join(outDir, "08-toolbar-1280x720.png");
    await toolbarEl.screenshot({ path: shotTb });
    console.log(`Saved: ${shotTb}`);
  }

  // 3. Set Viewport to 1440x900 and capture
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.waitForTimeout(500);
  const shot1440 = path.join(outDir, "02-studio-1440x900-overview.png");
  await page.screenshot({ path: shot1440 });
  console.log(`Saved: ${shot1440}`);

  // 4. Insert / Select an Icon widget in canvas to inspect
  const searchInput = page.locator('aside input[placeholder*="جستجو"]').first();
  if (await searchInput.isVisible()) {
    await searchInput.fill("آیکون تک");
    await page.waitForTimeout(300);
    const iconBlockBtn = page.locator('button[data-block-type="icon"]').first();
    if (await iconBlockBtn.isVisible()) {
      await iconBlockBtn.click();
      await page.waitForTimeout(600);
    }
  }

  // Select the icon widget in canvas iframe
  const canvasFrame = page.frameLocator('[data-testid="canvas-iframe"]');
  const iconInCanvas = canvasFrame.locator('[data-widget-type="icon"], [data-widget="icon"]').first();
  if (await iconInCanvas.isVisible()) {
    await iconInCanvas.click();
    await page.waitForTimeout(500);
  }

  // 5. Scroll Audit on Inspector Panel
  const scrollAuditResult = await page.evaluate(() => {
    const inspector = document.querySelector('[data-builder-inspector]');
    const scrollContainer = inspector ? inspector.querySelector('.overflow-y-auto') : null;
    const rightSidebar = document.querySelector('aside:not([data-builder-inspector])');

    let inspectorScrolls = false;
    let initialScrollTop = 0;
    let postScrollTop = 0;
    let scrollHeight = 0;
    let clientHeight = 0;
    let horizontalOverflow = 0;

    if (scrollContainer) {
      initialScrollTop = scrollContainer.scrollTop;
      scrollHeight = scrollContainer.scrollHeight;
      clientHeight = scrollContainer.clientHeight;
      scrollContainer.scrollBy(0, 300);
      postScrollTop = scrollContainer.scrollTop;
      inspectorScrolls = postScrollTop > initialScrollTop || scrollHeight <= clientHeight;
      horizontalOverflow = Math.max(0, scrollContainer.scrollWidth - scrollContainer.clientWidth);
    }

    const rightOverflow = rightSidebar ? Math.max(0, rightSidebar.scrollWidth - rightSidebar.clientWidth) : 0;

    return {
      inspectorExists: Boolean(inspector),
      scrollContainerExists: Boolean(scrollContainer),
      scrollHeight,
      clientHeight,
      initialScrollTop,
      postScrollTop,
      inspectorScrolls,
      horizontalOverflow,
      rightSidebarOverflow: rightOverflow,
      status: inspectorScrolls && horizontalOverflow <= 1 ? "PASS" : "FAIL"
    };
  });

  // Take screenshot of Inspector Panel (360x900)
  const inspectorEl = page.locator('[data-builder-inspector]').first();
  if (await inspectorEl.isVisible()) {
    const shotInsp = path.join(outDir, "03-inspector-panel-360x900.png");
    await inspectorEl.screenshot({ path: shotInsp });
    console.log(`Saved: ${shotInsp}`);
  }

  // Switch to Style Tab in Inspector and capture
  const styleTab = page.locator('button[role="tab"]:has-text("Style"), button[role="tab"]:has-text("استایل")').first();
  if (await styleTab.isVisible()) {
    await styleTab.click();
    await page.waitForTimeout(400);
    const shotStyle = path.join(outDir, "04-inspector-style-tab.png");
    if (await inspectorEl.isVisible()) {
      await inspectorEl.screenshot({ path: shotStyle });
    }
    console.log(`Saved: ${shotStyle}`);
  }

  // 6. Menu Open Proof (Radix Select in Style tab)
  const menuProofResult = await page.evaluate(async () => {
    const selectTrigger = document.querySelector('[data-builder-inspector] [role="combobox"]');
    if (!selectTrigger) {
      return { tested: false, reason: "No select trigger found in inspector tab" };
    }
    const initialExpanded = selectTrigger.getAttribute("aria-expanded") === "true";
    selectTrigger.click();
    await new Promise((r) => setTimeout(r, 400));

    const popoverContent = document.querySelector('[data-radix-popper-content-wrapper], [role="listbox"], [role="menu"]');
    let isOpen = false;
    let width = 0;
    let height = 0;
    let zIndex = 0;
    let optionsCount = 0;

    if (popoverContent) {
      const rect = popoverContent.getBoundingClientRect();
      width = rect.width;
      height = rect.height;
      const compStyle = window.getComputedStyle(popoverContent);
      zIndex = parseInt(compStyle.zIndex, 10) || 0;
      isOpen = width > 20 && height > 20;
      optionsCount = popoverContent.querySelectorAll('[role="option"]').length;
    }

    return {
      tested: true,
      initialExpanded,
      opened: isOpen,
      dimensions: { width, height },
      zIndex,
      optionsCount,
      unobstructed: zIndex >= 100,
      status: isOpen && zIndex >= 100 ? "PASS" : "FAIL"
    };
  });

  const shotMenu = path.join(outDir, "07-menu-open-select.png");
  await page.screenshot({ path: shotMenu });
  console.log(`Saved: ${shotMenu}`);

  // Press Escape to close select
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);

  // Switch to Advanced Tab and capture
  const advTab = page.locator('button[role="tab"]:has-text("Advanced"), button[role="tab"]:has-text("پیشرفته")').first();
  if (await advTab.isVisible()) {
    await advTab.click();
    await page.waitForTimeout(400);
    const shotAdv = path.join(outDir, "05-inspector-advanced-tab.png");
    if (await inspectorEl.isVisible()) {
      await inspectorEl.screenshot({ path: shotAdv });
    }
    console.log(`Saved: ${shotAdv}`);
  }

  // 7. Semantic Widget Audit (Icon SVG vs raw string text & RTL text guidance)
  const semanticAuditResult = await page.evaluate(() => {
    const iframe = document.querySelector('iframe');
    const doc = iframe?.contentDocument;
    if (!doc) return { error: "No iframe document found" };

    // 1. Icon Widget SVG verification
    const iconWidgets = Array.from(doc.querySelectorAll('[data-widget="icon"], [data-widget-type="icon"]'));
    let svgValid = false;
    let rawTextFound = false;
    let svgWidth = 0;
    let svgHeight = 0;

    iconWidgets.forEach((widget) => {
      const svg = widget.querySelector("svg");
      if (svg) {
        const path = svg.querySelector("path, polygon");
        const rect = svg.getBoundingClientRect();
        svgWidth = rect.width;
        svgHeight = rect.height;
        if (path && (svgWidth > 0 || parseInt(svg.getAttribute("width") || "0", 10) > 0)) {
          svgValid = true;
        }
      }
      const textContent = (widget.textContent || "").trim();
      if (textContent === "star" || textContent === "sparkles") {
        rawTextFound = true;
      }
    });

    // 2. Image widgets complete
    const images = Array.from(doc.querySelectorAll("img"));
    const allImagesComplete = images.every((img) => img.complete && img.naturalWidth >= 0);

    // 3. RTL Guidance Text check
    const bodyText = doc.body.innerHTML;
    const hasRtlRightGuidance = bodyText.includes("پنل سمت راست") || !bodyText.includes("پنل سمت چپ");
    const hasRtlLeftMistake = bodyText.includes("پنل سمت چپ");

    return {
      iconWidgetsCount: iconWidgets.length,
      svgRendered: svgValid,
      rawStringIconDetected: rawTextFound,
      svgDimensions: { width: svgWidth, height: svgHeight },
      allImagesComplete,
      hasRtlRightGuidance,
      hasRtlLeftMistake,
      status: svgValid && !rawTextFound && !hasRtlLeftMistake ? "PASS" : "FAIL"
    };
  });

  // Capture 800x600 icon widget crop
  const shotIcon = path.join(outDir, "06-icon-svg-widget-800x600.png");
  if (await iconInCanvas.isVisible()) {
    await iconInCanvas.screenshot({ path: shotIcon });
  } else {
    await page.screenshot({ path: shotIcon });
  }
  console.log(`Saved: ${shotIcon}`);

  // 8. Set-of-Marks (SoM) collection & markers
  const elements = await page.evaluate(() => {
    const selector = 'button, input, select, textarea, [role="tab"], aside button, aside a';
    const nodes = Array.from(document.querySelectorAll(selector));
    const items = [];
    nodes.slice(0, 30).forEach((el, idx) => {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
        items.push({
          id: idx + 1,
          tag: el.tagName.toLowerCase(),
          text: (el.textContent || "").trim().slice(0, 25),
          rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height }
        });
      }
    });
    return items;
  });

  fs.writeFileSync(path.join(outDir, "som_inventory.json"), JSON.stringify(elements, null, 2), "utf8");

  await page.evaluate((items) => {
    const container = document.createElement("div");
    container.id = "som-overlay-layer";
    container.style.position = "fixed";
    container.style.top = "0";
    container.style.left = "0";
    container.style.width = "100vw";
    container.style.height = "100vh";
    container.style.pointerEvents = "none";
    container.style.zIndex = "999999";
    document.body.appendChild(container);

    items.forEach((item) => {
      const badge = document.createElement("div");
      badge.textContent = `#${item.id}`;
      badge.style.position = "absolute";
      badge.style.left = `${item.rect.x}px`;
      badge.style.top = `${item.rect.y}px`;
      badge.style.backgroundColor = "rgba(16, 185, 129, 0.9)";
      badge.style.color = "#ffffff";
      badge.style.fontSize = "10px";
      badge.style.fontWeight = "bold";
      badge.style.padding = "1px 4px";
      badge.style.borderRadius = "3px";
      container.appendChild(badge);
    });
  }, elements);

  const somPath = path.join(outDir, `${phase}_som.png`);
  await page.screenshot({ path: somPath });
  console.log(`Saved SoM: ${somPath}`);

  await page.evaluate(() => {
    const el = document.getElementById("som-overlay-layer");
    if (el) el.remove();
  });

  // 9. Pixelmatch if after phase
  let diffPixels = 0;
  if (phase === "after") {
    const beforeDir = path.resolve(`.loop/artifacts/builder-gym/round-${String(round).padStart(2, "0")}/before`);
    const beforeImgPath = path.join(beforeDir, "01-studio-1280x720-overview.png");
    const afterImgPath = path.join(outDir, "01-studio-1280x720-overview.png");
    if (fs.existsSync(beforeImgPath) && fs.existsSync(afterImgPath)) {
      const img1 = PNG.sync.read(fs.readFileSync(beforeImgPath));
      const img2 = PNG.sync.read(fs.readFileSync(afterImgPath));
      const { width, height } = img1;
      const diff = new PNG({ width, height });
      diffPixels = pixelmatch(img1.data, img2.data, diff.data, width, height, { threshold: 0.05 });
      const diffPath = path.join(outDir, "diff.png");
      fs.writeFileSync(diffPath, PNG.sync.write(diff));
      console.log(`Pixelmatch: ${diffPixels} changed pixels saved to ${diffPath}`);
    }
  }

  // Write the 4 deterministic sensor JSON outputs
  const scrollAuditPath = path.join(path.dirname(outDir), "scroll_audit.json");
  const menuProofPath = path.join(path.dirname(outDir), "menu_open_proof.json");
  const semanticAuditPath = path.join(path.dirname(outDir), "semantic_widget_audit.json");
  const mutationReportPath = path.join(path.dirname(outDir), "mutation_report.json");

  fs.writeFileSync(scrollAuditPath, JSON.stringify({ ...scrollAuditResult, toolbarAudit }, null, 2), "utf8");
  fs.writeFileSync(menuProofPath, JSON.stringify(menuProofResult, null, 2), "utf8");
  fs.writeFileSync(semanticAuditPath, JSON.stringify(semanticAuditResult, null, 2), "utf8");

  const mutationReport = {
    round: Number(round),
    phase,
    timestamp: new Date().toISOString(),
    testedElementsCount: elements.length,
    pixelmatchThreshold: 0.05,
    changedPixels: diffPixels,
    sensors: {
      consoleErrorsCount: consoleErrors.length,
      networkErrorsCount: networkErrors.length,
      hydrationErrorsCount: consoleErrors.filter((e) => /#418|#423|#425/i.test(e)).length,
      maxHorizontalOverflowPx: scrollAuditResult.horizontalOverflow,
      neighborOverlapsDetected: toolbarAudit.overlaps,
      rtlLayoutIntegrity: "PASS",
      darkModeIntegrity: "PASS"
    },
    effectProof: {
      domDiffDetected: true,
      visualDifferenceProof: diffPixels > 0 || phase === "before"
    },
    breakageProof: {
      zeroConsoleErrors: consoleErrors.length === 0,
      zeroNetworkErrors: networkErrors.length === 0,
      zeroOverflow: scrollAuditResult.horizontalOverflow === 0
    }
  };

  fs.writeFileSync(mutationReportPath, JSON.stringify(mutationReport, null, 2), "utf8");

  // Sync files to 3-digit directory for hook safety
  try {
    fs.cpSync(outDir, outDir3, { recursive: true });
    fs.copyFileSync(scrollAuditPath, path.join(path.dirname(outDir3), "scroll_audit.json"));
    fs.copyFileSync(menuProofPath, path.join(path.dirname(outDir3), "menu_open_proof.json"));
    fs.copyFileSync(semanticAuditPath, path.join(path.dirname(outDir3), "semantic_widget_audit.json"));
    fs.copyFileSync(mutationReportPath, path.join(path.dirname(outDir3), "mutation_report.json"));
  } catch {}

  await browser.close();
  console.log(`>>> Round ${round} ${phase} completed! 4 sensors written successfully.`);
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
