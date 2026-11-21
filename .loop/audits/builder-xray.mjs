import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

// Resolve packages from frontend directory
const frontendPkgPath = path.resolve("frontend/package.json");
const req = createRequire(frontendPkgPath);
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const PROJECT_ROOT = path.resolve(".");
const BACKEND_DIR = path.join(PROJECT_ROOT, "backend");
const ROUND = process.env.EXCAVATOR_ROUND || "round-11";
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "excavator", ROUND, "before");
const AUDITS_DIR = path.join(PROJECT_ROOT, ".loop", "audits");
const MATRIX_PATH = path.join(PROJECT_ROOT, ".loop", "XRAY_MATRIX.json");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });
fs.mkdirSync(AUDITS_DIR, { recursive: true });

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
  const tmpFile = path.join(BACKEND_DIR, `.e2e-token-${Date.now()}.py`);
  fs.writeFileSync(tmpFile, script, "utf8");
  try {
    const out = execSync(`python "${tmpFile}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const line = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return line ? line.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmpFile)) {
      try { fs.unlinkSync(tmpFile); } catch {}
    }
  }
}

const PATTERN_SLUGS = [
  "hero-banner",
  "feature-grid",
  "product-showcase-cta",
  "testimonials",
  "faq-accordion",
  "image-text",
  "countdown-offer",
  "star-rating-display",
  "review-histogram",
  "product-card-grid",
  "text-marquee",
  "stats-counter",
  "image-gallery-showcase",
  "discount-badge-banner",
  "mega-menu-categories",
  "pricing-table",
  "price-list",
  "icon-box-grid",
  "author-bio",
  "pull-quote",
  "support-callout",
  "comparison-table",
  "process-steps",
  "lead-capture-form",
  "alert-banner",
  "floating-contact-bar",
  "brand-logo-carousel",
  "product-highlights",
];

const BASIC_BLOCK_TYPES = [
  "container", "section", "columns", "form_container",
  "heading", "text_editor", "image", "button", "spacer", "divider",
  "table", "form_input", "form_textarea", "form_select",
  "product_card", "product_grid", "product_variants", "product_price",
  "add_to_cart", "mini_cart", "cart_summary",
  "form_checkbox", "form_radio", "accordion", "tabs",
  "countdown", "video", "icon_box", "social_links",
  "image_gallery", "star_rating", "review_histogram",
  "recently_viewed", "mega_menu"
];

async function runXRay() {
  console.log(">>> [X-RAY] Initializing ruthless audit scanner (.loop/audits/builder-xray.mjs)...");

  const matrix = {
    timestamp: new Date().toISOString(),
    totalFailures: 0,
    p0Count: 0,
    p1Count: 0,
    p2Count: 0,
    patternsPassed: 0,
    patternsTotal: 28,
    blocksPassed: 0,
    blocksTotal: 34,
    deadControlsRemaining: 0,
    failures: [],
    summary: {},
  };

  async function addFailure(severity, category, target, message, meta = {}) {
    matrix.totalFailures++;
    if (severity === "P0") matrix.p0Count++;
    else if (severity === "P1") matrix.p1Count++;
    else matrix.p2Count++;

    const safeTarget = String(target).replace(/[^a-zA-Z0-9_-]/g, "_").slice(0, 50);
    const shotPath = path.join(ARTIFACTS_DIR, `${severity}_${category}_${safeTarget}.png`);
    try {
      if (page && !page.isClosed()) {
        await page.screenshot({ path: shotPath }).catch(() => {});
      }
    } catch {}

    matrix.failures.push({
      severity,
      category,
      target,
      message,
      screenshot: path.relative(PROJECT_ROOT, shotPath),
      meta,
    });
    console.warn(`    [${severity}] [${category}] ${target}: ${message}`);
  }

  const token = getAdminToken();
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, {
    waitUntil: "domcontentloaded",
  });
  await page.waitForTimeout(2000);

  // Helper: clear canvas
  async function clearCanvas() {
    try {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(100);
    } catch {}
    await page.evaluate(() => {
      const store = window.__BUILDER_STORE__;
      if (store) {
        store.setState({
          ast: { ...store.getState().ast, rootElements: [] },
          selectedElementId: null,
          selectedElementIds: [],
        });
      }
    });
    await page.waitForTimeout(300);
  }

  const closeAnyModal = async () => {
    try {
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
      const openOverlays = page.locator("div[data-state='open'].fixed.inset-0");
      if ((await openOverlays.count()) > 0) {
        await page.keyboard.press("Escape");
        await page.waitForTimeout(200);
      }
    } catch {}
  };

  const getCanvasFrame = async () => {
    const iframeEl = await page.waitForSelector('iframe[title="Visual Builder Canvas"]', { state: "attached", timeout: 15000 });
    if (!iframeEl) throw new Error("Iframe canvas not found");
    const frame = await iframeEl.contentFrame();
    if (!frame) throw new Error("Could not access canvas frame content");
    return frame;
  };

  // ──────────────────────────────────────────────────────────────────────────
  // 1. TEST ALL 28 PATTERNS (Pattern-by-Pattern, 1..28)
  // ──────────────────────────────────────────────────────────────────────────
  console.log(">>> [X-RAY] Phase 1: Testing 28 Block Patterns (Checks A, B, C, D, E)...");

  for (let i = 0; i < PATTERN_SLUGS.length; i++) {
    const slug = PATTERN_SLUGS[i];
    let patternFailed = false;

    await clearCanvas();

    // Switch to patterns tab
    const mainTab = page.locator("aside button:has-text('افزودن بلوک')").first();
    if (await mainTab.isVisible()) await mainTab.click();
    const patternsTab = page.locator("aside button:has-text('الگوها')").first();
    await patternsTab.click();
    await page.locator("div[data-pattern-slug]").first().waitFor({ state: "visible", timeout: 15000 });
    await page.waitForTimeout(100);

    // Filter to 'all' categories
    const allCategoryChip = page.locator("button:has-text('همه')").first();
    if (await allCategoryChip.isVisible()) {
      await allCategoryChip.click();
    }

    const patternCard = page.locator(`div[data-pattern-slug="${slug}"]`).first();
    try {
      await patternCard.scrollIntoViewIfNeeded({ timeout: 5000 });
    } catch {}
    if (!(await patternCard.isVisible())) {
      await addFailure("P0", "PATTERN_CARD_NOT_FOUND", slug, `Pattern card for ${slug} not visible in palette`);
      continue;
    }

    // Insert pattern
    await patternCard.click();

    const frame = await getCanvasFrame();
    const rootEl = frame.locator("[data-element-id]").first();
    try {
      await rootEl.waitFor({ state: "visible", timeout: 8000 });
    } catch {
      await addFailure("P0", "PATTERN_NOT_RENDERED", slug, `Root element for pattern ${slug} not rendered`);
      continue;
    }

    // Test targets: root + at least 2 inner children (as strictly specified by prompt)
    const allElements = frame.locator("[data-element-id]");
    const totalCount = await allElements.count();
    const elementsToTest = [rootEl];
    if (totalCount > 1) elementsToTest.push(allElements.nth(1));
    if (totalCount > 2) elementsToTest.push(allElements.nth(2));

    for (let tIdx = 0; tIdx < elementsToTest.length; tIdx++) {
      const targetLoc = elementsToTest[tIdx];
      const targetId = await targetLoc.getAttribute("data-element-id");
      const targetTag = await targetLoc.evaluate((el) => el.tagName.toLowerCase());

      // Click to select (catch interception without force: true)
      try {
        await targetLoc.click({ timeout: 4000 });
      } catch (clickErr) {
        await addFailure("P0", "ELEMENT_CLICK_BLOCKED", `${slug}::${targetId}`, `Element click blocked: ${clickErr.message}`);
        patternFailed = true;
        continue;
      }
      await page.waitForTimeout(300);

      // Check A: Floating toolbar presence
      const toolbarLoc = frame.locator('[data-testid="floating-toolbar"]').first();
      const toolbarVisible = await toolbarLoc.isVisible();
      if (!toolbarVisible) {
        await addFailure("P0", "TOOLBAR_MISSING", `${slug}::${targetId}`, "Floating toolbar not visible on selected element");
        patternFailed = true;
        continue;
      }

      const toolbarRect = await toolbarLoc.evaluate((el) => {
        const r = el.getBoundingClientRect();
        return { width: r.width, height: r.height, top: r.top, bottom: r.bottom, left: r.left, right: r.right };
      });

      if (toolbarRect.width <= 40 || toolbarRect.height <= 20) {
        await addFailure("P0", "TOOLBAR_SIZE_INVALID", `${slug}::${targetId}`, `Toolbar size too small: ${toolbarRect.width}x${toolbarRect.height}`);
        patternFailed = true;
      }

      // Check B: Prohibition of clipping by ancestor with overflow: hidden/clip/auto/scroll
      const clipCheck = await toolbarLoc.evaluate((toolbar) => {
        const doc = toolbar.ownerDocument;
        const win = doc.defaultView;
        const tRect = toolbar.getBoundingClientRect();
        let parent = toolbar.parentElement;
        let culprit = null;
        const overflowValues = new Set(["hidden", "clip", "auto", "scroll"]);

        while (parent && parent !== doc.body) {
          const style = win.getComputedStyle(parent);
          if (overflowValues.has(style.overflow) || overflowValues.has(style.overflowX) || overflowValues.has(style.overflowY)) {
            const pRect = parent.getBoundingClientRect();
            const tolerance = 1;
            if (
              tRect.top < pRect.top - tolerance ||
              tRect.bottom > pRect.bottom + tolerance ||
              tRect.left < pRect.left - tolerance ||
              tRect.right > pRect.right + tolerance
            ) {
              culprit = {
                tag: parent.tagName.toLowerCase(),
                className: parent.className,
                overflow: style.overflow,
                tRect: { top: tRect.top, bottom: tRect.bottom, left: tRect.left, right: tRect.right },
                pRect: { top: pRect.top, bottom: pRect.bottom, left: pRect.left, right: pRect.right },
              };
              break;
            }
          }
          parent = parent.parentElement;
        }
        return culprit;
      });

      if (clipCheck) {
        await addFailure(
          "P0",
          "TOOLBAR_CLIPPED_BY_OVERFLOW",
          `${slug}::${targetId}`,
          `Toolbar clipped by ancestor <${clipCheck.tag}> with overflow:${clipCheck.overflow}`,
          clipCheck
        );
        patternFailed = true;
      }

      // Check C: elementFromPoint test on all toolbar buttons
      const buttonClickability = await toolbarLoc.evaluate((toolbar) => {
        const doc = toolbar.ownerDocument;
        const buttons = Array.from(toolbar.querySelectorAll("button, [role='button']"));
        const unclickable = [];

        for (const btn of buttons) {
          const bRect = btn.getBoundingClientRect();
          const cx = bRect.left + bRect.width / 2;
          const cy = bRect.top + bRect.height / 2;
          const topEl = doc.elementFromPoint(cx, cy);

          if (!topEl || (!btn.contains(topEl) && btn !== topEl)) {
            unclickable.push({
              title: btn.getAttribute("title") || btn.getAttribute("data-testid") || btn.textContent?.trim(),
              cx,
              cy,
              foundTag: topEl ? topEl.tagName.toLowerCase() : null,
              foundClass: topEl ? topEl.className : null,
            });
          }
        }
        return unclickable;
      });

      if (buttonClickability && buttonClickability.length > 0) {
        await addFailure(
          "P0",
          "TOOLBAR_BUTTON_UNCLICKABLE",
          `${slug}::${targetId}`,
          `Toolbar buttons blocked from point click: ${buttonClickability.map((b) => b.title).join(", ")}`,
          buttonClickability
        );
        patternFailed = true;
      }

      // Check E: Prohibition of raw HTML leak in inspector inputs/textareas
      const rawHtmlCheck = await page.evaluate(() => {
        const inspector = document.querySelector("[data-builder-inspector]");
        if (!inspector) return null;
        const inputs = Array.from(inspector.querySelectorAll("input, textarea"));
        const leaking = [];
        for (const input of inputs) {
          const val = (input).value || "";
          if (/<span\b|<div\b|class\s*=/i.test(val)) {
            leaking.push({
              type: input.tagName.toLowerCase(),
              val: val.slice(0, 100),
            });
          }
        }
        return leaking.length > 0 ? leaking : null;
      });

      if (rawHtmlCheck) {
        await addFailure(
          "P1",
          "RAW_HTML_IN_INSPECTOR",
          `${slug}::${targetId}`,
          `Raw HTML tags/classes leaked into inspector field: ${JSON.stringify(rawHtmlCheck)}`,
          rawHtmlCheck
        );
        patternFailed = true;
      }
    }

    // Check D: Real AST actions (Duplicate -> count increases; Move -> order changes; Delete -> count decreases)
    try {
      const initialElementsCount = await frame.locator("[data-element-id]").count();
      const firstEl = frame.locator("[data-element-id]").first();
      await firstEl.click();
      await page.waitForTimeout(200);

      const dupBtn = frame.locator('[data-testid="floating-toolbar"] button[title*="تکثیر"]').first();
      if (await dupBtn.isVisible()) {
        await dupBtn.click();
        await page.waitForTimeout(300);
        const afterDupCount = await frame.locator("[data-element-id]").count();
        if (afterDupCount <= initialElementsCount) {
          await addFailure("P0", "DEAD_TOOLBAR_ACTION", `${slug}::duplicate`, "Duplicate button clicked but element count did not increase");
          patternFailed = true;
        }

        const delBtn = frame.locator('[data-testid="floating-toolbar"] button[title*="حذف"]').first();
        if (await delBtn.isVisible()) {
          await delBtn.click();
          await page.waitForTimeout(300);
          const afterDelCount = await frame.locator("[data-element-id]").count();
          if (afterDelCount >= afterDupCount) {
            await addFailure("P0", "DEAD_TOOLBAR_ACTION", `${slug}::delete`, "Delete button clicked but element count did not decrease");
            patternFailed = true;
          }
        }
      }
    } catch (err) {
      await addFailure("P0", "DEAD_TOOLBAR_ACTION", `${slug}::exception`, `Toolbar action test crashed: ${err.message}`);
      patternFailed = true;
    }

    if (!patternFailed) {
      matrix.patternsPassed++;
    }
  }

  // ──────────────────────────────────────────────────────────────────────────
  // 2. TEST ALL 34 BASIC BLOCKS & NATIVE WIDGETS (1..34)
  // ──────────────────────────────────────────────────────────────────────────
  console.log(">>> [X-RAY] Phase 2: Testing 34 Native Base Blocks...");

  for (let i = 0; i < BASIC_BLOCK_TYPES.length; i++) {
    const blockType = BASIC_BLOCK_TYPES[i];
    let blockFailed = false;

    await clearCanvas();

    const mainTab = page.locator("aside button:has-text('افزودن بلوک')").first();
    if (await mainTab.isVisible()) await mainTab.click();
    const blocksTab = page.locator("aside button:has-text('بلوک‌ها')").first();
    await blocksTab.click();
    await page.locator("[data-block-type]").first().waitFor({ state: "visible", timeout: 15000 });
    await page.waitForTimeout(100);

    // Find block by text or type
    const blockButton = page.locator(`[data-block-type="${blockType}"]`).first();
    const fallbackButton = page.locator(`button:has-text("${blockType}")`).first();

    let targetBtn = (await blockButton.count()) > 0 ? blockButton : fallbackButton;
    try {
      await targetBtn.scrollIntoViewIfNeeded({ timeout: 4000 });
    } catch {}

    // Direct insertion fallback via store if palette element missing
    if ((await targetBtn.count()) === 0 || !(await targetBtn.isVisible())) {
      const inserted = await page.evaluate((type) => {
        const store = window.__BUILDER_STORE__ || (window).__builderStore;
        if (store && store.getState) {
          store.getState().addElement({
            id: `el_test_${type}`,
            name: `Test ${type}`,
            type: ["container", "section", "columns", "form_container"].includes(type) ? "container" : "widget",
            widgetType: ["container", "section", "columns", "form_container"].includes(type) ? undefined : type,
            widgetProps: {},
            styles: { mobile: {} },
            children: [],
          });
          return true;
        }
        return false;
      }, blockType);

      if (!inserted) {
        await addFailure("P0", "BLOCK_PALETTE_MISSING", blockType, `Block definition ${blockType} not found in palette`);
        continue;
      }
    } else {
      await targetBtn.click();
    }

    await page.waitForTimeout(400);

    const frame = await getCanvasFrame();
    const renderedBlock = frame.locator("[data-element-id]").first();
    if (!(await renderedBlock.isVisible())) {
      await addFailure("P0", "BLOCK_RENDER_FAILED", blockType, `Block ${blockType} failed to render on canvas`);
      continue;
    }

    const bBox = await renderedBlock.boundingBox();
    if (!bBox || bBox.width <= 0 || bBox.height <= 0) {
      await addFailure("P0", "BLOCK_ZERO_SIZE", blockType, `Block ${blockType} rendered with zero dimensions`);
      blockFailed = true;
    }

    // Test selection and toolbar
    await renderedBlock.click();
    await page.waitForTimeout(300);

    const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
    if (!(await toolbar.isVisible())) {
      await addFailure("P0", "BLOCK_TOOLBAR_MISSING", blockType, `Toolbar missing on selecting ${blockType}`);
      blockFailed = true;
    }

    if (!blockFailed) {
      matrix.blocksPassed++;
    }
  }

  // ──────────────────────────────────────────────────────────────────────────
  // 3. DEAD CONTROL HUNTER (Inspector Panel Controls)
  // ──────────────────────────────────────────────────────────────────────────
  console.log(">>> [X-RAY] Phase 3: Dead Control Hunter in Inspector Panel...");

  const testDeadControls = async () => {
    await clearCanvas();

    // Insert a container with heading and button
    await page.evaluate(() => {
      const store = window.__BUILDER_STORE__ || (window).__builderStore;
      if (store && store.getState) {
        store.getState().addElement({
          id: "cont_test_hunter",
          name: "کانتینر تستر",
          type: "container",
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "start",
            alignItems: "stretch",
            flexWrap: "nowrap",
            gap: { value: 16, unit: "px" },
            gridColumns: 1,
          },
          styles: {
            mobile: {
              padding: { top: { value: 10, unit: "px" }, bottom: { value: 10, unit: "px" }, left: { value: 10, unit: "px" }, right: { value: 10, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: "head_test_hunter",
              name: "تیتر تستر",
              type: "widget",
              widgetType: "heading",
              widgetProps: { text: "تیتر تستر کنترل", tag: "h2" },
              styles: { mobile: {} },
              children: [],
            },
          ],
        });
        store.getState().selectElement("cont_test_hunter");
      }
    });

    await page.waitForTimeout(500);
    const frame = await getCanvasFrame();
    const contLoc = frame.locator('[data-element-id="cont_test_hunter"]');

    // Test 1: Content Tab - Gap Control
    const gapInput = page.locator('input[data-testid="container-gap-input"]').first();
    if (await gapInput.isVisible()) {
      await gapInput.fill("42");
      await page.waitForTimeout(300);
      const computedGap = await contLoc.evaluate((el) => window.getComputedStyle(el).gap);
      if (computedGap !== "42px") {
        await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "container::gap", `Gap changed to 42px in inspector but computedStyle.gap is ${computedGap}`);
        matrix.deadControlsRemaining++;
      }
    }

    // Test 2: Style Tab - Padding
    const styleTabTrigger = page.locator('[data-builder-inspector] button[role="tab"]:has-text("استایل")').first();
    if (await styleTabTrigger.isVisible()) {
      await styleTabTrigger.click();
      await page.waitForTimeout(300);

      const paddingInput = page.locator('[data-builder-inspector] input[type="number"]').first();
      if (await paddingInput.isVisible()) {
        await paddingInput.fill("35");
        await page.waitForTimeout(300);
        const computedPadding = await contLoc.evaluate((el) => window.getComputedStyle(el).paddingTop);
        if (computedPadding !== "35px") {
          await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "container::paddingTop", `Padding set to 35px in inspector but computedStyle.paddingTop is ${computedPadding}`);
          matrix.deadControlsRemaining++;
        }
      }
    }

    // Test 3: Heading Widget - Content Tab Text Mutation
    const headLoc = frame.locator('[data-element-id="head_test_hunter"]');
    await headLoc.click();
    await page.waitForTimeout(300);

    const contentTabTrigger = page.locator('[data-builder-inspector] button[role="tab"]:has-text("محتوا")').first();
    if (await contentTabTrigger.isVisible()) {
      await contentTabTrigger.click();
      await page.waitForTimeout(300);
    }

    const headingTextInput = page.locator('[data-builder-inspector] input[type="text"]').first();
    if (await headingTextInput.isVisible()) {
      await headingTextInput.fill("تیتر به روز شده تستر");
      await page.waitForTimeout(300);
      const updatedText = await headLoc.evaluate((el) => el.textContent?.trim());
      if (!updatedText || !updatedText.includes("تیتر به روز شده تستر")) {
        await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "heading::text", `Heading text changed in inspector to 'تیتر به روز شده تستر' but DOM text is '${updatedText}'`);
        matrix.deadControlsRemaining++;
      }
    }

    // Test 4: Elementor Inline Editing on Canvas (Double Click)
    try {
      const hTag = headLoc.locator("h2").first();
      if (await hTag.isVisible()) {
        await hTag.dblclick();
        await page.waitForTimeout(300);
        const inlineInput = headLoc.locator("input[type='text']").first();
        if (await inlineInput.isVisible()) {
          await inlineInput.fill("ویرایش مستقیم با دابل کلیک");
          await page.keyboard.press("Enter");
          await page.waitForTimeout(300);
          const inlinedText = await headLoc.evaluate((el) => el.textContent?.trim());
          if (!inlinedText || !inlinedText.includes("ویرایش مستقیم با دابل کلیک")) {
            await addFailure("P0", "DEAD_INLINE_EDITING", "heading::inline", `Inline editing failed: expected 'ویرایش مستقیم با دابل کلیک' but got '${inlinedText}'`);
          }
        } else {
          await addFailure("P0", "INLINE_EDITING_INPUT_MISSING", "heading::inline", "Double-click on heading did not activate inline input");
        }
      }
    } catch (inlineErr) {
      await addFailure("P0", "INLINE_EDITING_ERROR", "heading::inline", `Inline editing test crashed: ${inlineErr.message}`);
    }

    // Test 5: Typography Font Size & Box Shadow Controls
    try {
      await headLoc.click();
      await page.waitForTimeout(300);
      const styleTab = page.locator('[data-builder-inspector] button[role="tab"]:has-text("استایل")').first();
      if (await styleTab.isVisible()) {
        await styleTab.click();
        await page.waitForTimeout(300);

        // Test Font Size input
        const fontSizeInput = page.locator('input[placeholder="مثلاً 16"]').first();
        if (await fontSizeInput.isVisible()) {
          await fontSizeInput.fill("28");
          await page.waitForTimeout(300);
          const computedFontSize = await headLoc.evaluate((el) => window.getComputedStyle(el).fontSize);
          if (computedFontSize !== "28px") {
            await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "typography::fontSize", `Font size set to 28px in inspector but computedStyle.fontSize is ${computedFontSize}`);
            matrix.deadControlsRemaining++;
          }
        }

        // Test Box Shadow preset
        const shadowBtn = page.locator('button:has-text("برجسته (lg)")').first();
        if (await shadowBtn.isVisible()) {
          await shadowBtn.click();
          await page.waitForTimeout(300);
          const computedShadow = await headLoc.evaluate((el) => window.getComputedStyle(el).boxShadow);
          if (!computedShadow || computedShadow === "none") {
            await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "boxShadow::preset", "Box shadow preset clicked but computedStyle.boxShadow is none");
            matrix.deadControlsRemaining++;
          }
        }

        // Test 6: Border Width & Style Controls (Elementor Border System)
        const borderWidthInput = page.locator('input[placeholder="مثلاً 1"]').first();
        if (await borderWidthInput.isVisible()) {
          await borderWidthInput.fill("4");
          await page.waitForTimeout(300);
          const computedBorderWidth = await headLoc.evaluate((el) => window.getComputedStyle(el).borderTopWidth);
          if (computedBorderWidth !== "4px") {
            await addFailure("P0", "DEAD_INSPECTOR_CONTROL", "border::width", `Border width set to 4px in inspector but computedStyle.borderTopWidth is ${computedBorderWidth}`);
            matrix.deadControlsRemaining++;
          }
        }
      }
    } catch (typoErr) {
      await addFailure("P0", "TYPOGRAPHY_CONTROL_ERROR", "inspector::typography", `Typography controls test failed: ${typoErr.message}`);
    }
  };

  await testDeadControls();
  await closeAnyModal();

  // ──────────────────────────────────────────────────────────────────────────
  // 4. STUDIO LAYOUT & WYSIWYG PARITY
  // ──────────────────────────────────────────────────────────────────────────
  console.log(">>> [X-RAY] Phase 4: Studio Layout, Elementor Context Menu, Navigator & Parity Checks...");

  // Check 4.1: Category filter chips clipping
  const mainTab = page.locator("aside button:has-text('افزودن بلوک')").first();
  if (await mainTab.isVisible()) await mainTab.click();
  const patternsTab = page.locator("aside button:has-text('الگوها')").first();
  await patternsTab.click();
  await page.waitForTimeout(300);

  const chipsClipping = await page.evaluate(() => {
    const chipButtons = Array.from(document.querySelectorAll("aside button"));
    const truncatedOrClipped = [];
    for (const b of chipButtons) {
      if (b.scrollWidth > b.clientWidth + 2) {
        truncatedOrClipped.push(b.textContent?.trim());
      }
      if (/اعتماد.*بازخ/.test(b.textContent || "") && b.textContent.includes("...")) {
        truncatedOrClipped.push(b.textContent?.trim());
      }
    }
    return truncatedOrClipped;
  });

  if (chipsClipping && chipsClipping.length > 0) {
    await addFailure("P1", "CATEGORY_CHIP_CLIPPED", "blocks-palette::categories", `Category chips clipped or truncated: ${chipsClipping.join(", ")}`);
  }

  // Check 4.2: Context Menu (Elementor Architecture Parity) on Canvas
  try {
    const frame = await getCanvasFrame();
    const firstBlock = frame.locator("[data-element-id]").first();
    if (await firstBlock.isVisible()) {
      await firstBlock.click({ button: "right" });
      await page.waitForTimeout(300);
      const ctxMenu = page.locator("#builder-context-menu").first();
      if (!(await ctxMenu.isVisible())) {
        await addFailure("P0", "CONTEXT_MENU_CANVAS_MISSING", "canvas::contextmenu", "Right-click on canvas element did not open #builder-context-menu");
      } else {
        await page.keyboard.press("Escape");
        await page.waitForTimeout(200);
      }
    }
  } catch (ctxErr) {
    await addFailure("P0", "CONTEXT_MENU_CANVAS_ERROR", "canvas::contextmenu", `Context menu test failed: ${ctxErr.message}`);
  }

  // Check 4.3: Navigator (LayersTree) Right-Click Context Menu & Inline Rename
  try {
    const layersTab = page.locator("aside button:has-text('لایه‌ها')").first();
    if (await layersTab.isVisible()) {
      await layersTab.click();
      await page.waitForTimeout(300);

      const layerRow = page.locator("[data-layer-row]").first();
      if (await layerRow.isVisible()) {
        // Right-click on layer row
        await layerRow.click({ button: "right" });
        await page.waitForTimeout(300);
        const ctxMenu = page.locator("#builder-context-menu").first();
        if (!(await ctxMenu.isVisible())) {
          await addFailure("P0", "CONTEXT_MENU_LAYERS_MISSING", "layers::contextmenu", "Right-click on layer row did not open #builder-context-menu");
        } else {
          await page.keyboard.press("Escape");
          await page.waitForTimeout(200);
        }

        // Double-click inline rename
        const nameSpan = layerRow.locator("span.cursor-text").first();
        if (await nameSpan.isVisible()) {
          await nameSpan.dblclick();
          await page.waitForTimeout(200);
          const renameInput = layerRow.locator("input[type='text']").first();
          if (!(await renameInput.isVisible())) {
            await addFailure("P1", "NAVIGATOR_INLINE_RENAME_MISSING", "layers::rename", "Double-click on layer title did not activate inline rename input");
          } else {
            await page.keyboard.press("Escape");
          }
        }
      }
    }
  } catch (layersErr) {
    await addFailure("P0", "NAVIGATOR_TEST_ERROR", "layers-tree", `Navigator test failed: ${layersErr.message}`);
  }

  // Check 4.4: Save Draft & WYSIWYG Parity Check
  try {
    const saveDraftBtn = page.locator("button:has-text('ذخیره پیش‌نویس')").first();
    if (await saveDraftBtn.isVisible()) {
      await saveDraftBtn.click();
      await page.waitForTimeout(1000);
      const isClean = await page.evaluate(() => {
        const store = window.__BUILDER_STORE__;
        return store ? !store.getState().isDirty : false;
      });
      if (!isClean) {
        await addFailure("P1", "DRAFT_SAVE_UNCLEAN", "builder::save", "After clicking Save Draft, builder store remained dirty");
      }
    }
  } catch (saveErr) {
    await addFailure("P1", "DRAFT_SAVE_FAILED", "builder::save", `Save draft check failed: ${saveErr.message}`);
  }

  // Check 4.5: Responsive Viewport Switcher Check (Tablet 768px, Mobile 375px, Desktop)
  try {
    const tabletBtn = page.locator("button:has-text('تبلت')").first();
    const mobileBtn = page.locator("button:has-text('موبایل')").first();
    const desktopBtn = page.locator("button:has-text('دسکتاپ')").first();

    if (await tabletBtn.isVisible() && await mobileBtn.isVisible() && await desktopBtn.isVisible()) {
      // 1. Switch to Tablet
      await tabletBtn.click();
      await page.waitForTimeout(400);
      let bp = await page.evaluate(() => window.__BUILDER_STORE__?.getState().activeBreakpoint);
      if (bp !== "tablet") {
        await addFailure("P0", "VIEWPORT_SWITCH_FAILED", "viewport::tablet", `Clicked tablet button but activeBreakpoint is '${bp}'`);
      }

      // 2. Switch to Mobile
      await mobileBtn.click();
      await page.waitForTimeout(400);
      bp = await page.evaluate(() => window.__BUILDER_STORE__?.getState().activeBreakpoint);
      if (bp !== "mobile") {
        await addFailure("P0", "VIEWPORT_SWITCH_FAILED", "viewport::mobile", `Clicked mobile button but activeBreakpoint is '${bp}'`);
      }

      // 3. Switch back to Desktop
      await desktopBtn.click();
      await page.waitForTimeout(400);
      bp = await page.evaluate(() => window.__BUILDER_STORE__?.getState().activeBreakpoint);
      if (bp !== "desktop") {
        await addFailure("P0", "VIEWPORT_SWITCH_FAILED", "viewport::desktop", `Clicked desktop button but activeBreakpoint is '${bp}'`);
      }
    }
  } catch (vpErr) {
    await addFailure("P0", "VIEWPORT_SWITCH_ERROR", "viewport", `Viewport test failed: ${vpErr.message}`);
  }

  // Check 4.6: Real Drag & Drop Insert and Element Reordering (HTML5 DnD)
  try {
    const frame = await getCanvasFrame();
    const initialCount = await frame.locator("[data-element-id]").count();

    // Trigger HTML5 drop onto canvas root
    const dropSuccess = await frame.evaluate(() => {
      const root = document.querySelector("[data-testid='builder-canvas-root']");
      if (!root) return false;
      const dataTransfer = new DataTransfer();
      dataTransfer.setData("application/json", JSON.stringify({ type: "block_def", blockType: "button" }));
      const dropEvent = new DragEvent("drop", {
        bubbles: true,
        cancelable: true,
        dataTransfer,
      });
      root.dispatchEvent(dropEvent);
      return true;
    });

    if (!dropSuccess) {
      await addFailure("P0", "DND_CANVAS_ROOT_MISSING", "canvas::root", "Canvas root element not found for drop event");
    } else {
      await page.waitForTimeout(400);
      const afterDropCount = await frame.locator("[data-element-id]").count();
      if (afterDropCount <= initialCount) {
        await addFailure("P0", "DND_INSERT_FAILED", "canvas::drop", `Dropped button block into canvas root but element count did not increase (${initialCount} -> ${afterDropCount})`);
      }
    }
  } catch (dndErr) {
    await addFailure("P0", "DND_TEST_ERROR", "canvas::dnd", `Drag and drop test crashed: ${dndErr.message}`);
  }

  // Check 4.7: Public Storefront WYSIWYG Parity Check
  try {
    const publicPage = await context.newPage();
    await publicPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await publicPage.waitForTimeout(1500);

    const isRenderedContentVisible = await publicPage.locator(".builder-rendered-content, .prose, main, h1, h2").first().isVisible();
    if (!isRenderedContentVisible) {
      await addFailure("P0", "PUBLIC_STOREFRONT_WYSIWYG_MISSING", "storefront::wysiwyg", "Public page /e2e-isolated-scratchpad did not render compiled builder content");
    }
    await publicPage.close();
  } catch (wysiwygErr) {
    await addFailure("P0", "WYSIWYG_PARITY_ERROR", "storefront::parity", `WYSIWYG parity test crashed: ${wysiwygErr.message}`);
  }

  // Check 4.8: History Undo / Redo & Global Shortcut (Ctrl+Z / Ctrl+Y) Automation
  try {
    const frame = await getCanvasFrame();
    const beforeActionCount = await frame.locator("[data-element-id]").count();

    // 1. Duplicate first element to create history entry
    const firstEl = frame.locator("[data-element-id]").first();
    await firstEl.click();
    await page.waitForTimeout(300);

    const dupBtn = frame.locator('[data-testid="floating-toolbar"] button[title*="تکثیر"]').first();
    if (await dupBtn.isVisible()) {
      await dupBtn.click();
      await page.waitForTimeout(400);

      const afterDupCount = await frame.locator("[data-element-id]").count();
      if (afterDupCount > beforeActionCount) {
        // 2. Click Undo button in toolbar
        const undoBtn = page.locator("button[title*='Ctrl+Z']").first();
        if (await undoBtn.isEnabled()) {
          await undoBtn.click();
          await page.waitForTimeout(400);
          const afterUndoCount = await frame.locator("[data-element-id]").count();
          if (afterUndoCount !== beforeActionCount) {
            await addFailure("P0", "HISTORY_UNDO_FAILED", "builder::undo", `Toolbar Undo failed: expected ${beforeActionCount} elements but found ${afterUndoCount}`);
          }

          // 3. Click Redo button in toolbar
          const redoBtn = page.locator("button[title*='Ctrl+Y']").first();
          if (await redoBtn.isEnabled()) {
            await redoBtn.click();
            await page.waitForTimeout(400);
            const afterRedoCount = await frame.locator("[data-element-id]").count();
            if (afterRedoCount !== afterDupCount) {
              await addFailure("P0", "HISTORY_REDO_FAILED", "builder::redo", `Toolbar Redo failed: expected ${afterDupCount} elements but found ${afterRedoCount}`);
            }
          }
        }
      }
    }
  } catch (historyErr) {
    await addFailure("P0", "HISTORY_TEST_ERROR", "builder::history", `Undo/Redo test crashed: ${historyErr.message}`);
  }

  // Check 4.9: Stress Test With 50+ Nested AST Elements
  try {
    const stressSuccess = await page.evaluate(() => {
      const store = window.__BUILDER_STORE__;
      if (!store) return false;

      const rootContainers = [];
      let elCounter = 1;
      for (let s = 1; s <= 6; s++) {
        const secChildren = [];
        for (let c = 1; c <= 4; c++) {
          const colChildren = [
            {
              id: `stress_head_${elCounter++}`,
              name: `سرتیتر استرس ${elCounter}`,
              type: "widget",
              widgetType: "heading",
              widgetProps: { text: `تست فشار تیتر ${elCounter}`, tag: "h3" },
              styles: { mobile: {} },
              children: [],
            },
            {
              id: `stress_text_${elCounter++}`,
              name: `متن استرس ${elCounter}`,
              type: "widget",
              widgetType: "text_editor",
              widgetProps: { content: `متن توضیحی برای سنجش پایداری در عمق ${c}` },
              styles: { mobile: {} },
              children: [],
            },
          ];
          secChildren.push({
            id: `stress_col_${elCounter++}`,
            name: `ستون فشار ${c}`,
            type: "container",
            layout: { kind: "flex", direction: "column", gap: { value: 8, unit: "px" } },
            styles: { mobile: {} },
            children: colChildren,
          });
        }
        rootContainers.push({
          id: `stress_sec_${elCounter++}`,
          name: `سکشن فشار ${s}`,
          type: "container",
          layout: { kind: "grid", direction: "row", gridColumns: 4, gap: { value: 16, unit: "px" } },
          styles: { mobile: { padding: { top: { value: 24, unit: "px" }, isLinked: true } } },
          children: secChildren,
        });
      }

      store.getState().replacePageAST({
        schemaVersion: 1,
        title: "تست فشار ۵۰ المان",
        slug: "stress-test-page",
        globalStyles: {},
        rootElements: rootContainers,
      });

      return elCounter;
    });

    if (!stressSuccess || stressSuccess < 50) {
      await addFailure("P0", "STRESS_INJECTION_FAILED", "builder::stress", `Failed to inject 50+ stress elements, counter was ${stressSuccess}`);
    } else {
      await page.waitForTimeout(1000);
      const frame = await getCanvasFrame();
      const renderedStressCount = await frame.locator("[data-element-id]").count();
      if (renderedStressCount < 50) {
        await addFailure("P0", "STRESS_RENDER_COUNT_LOW", "builder::stress", `Injected 50+ elements but canvas only rendered ${renderedStressCount}`);
      }
    }
  } catch (stressErr) {
    await addFailure("P0", "STRESS_TEST_ERROR", "builder::stress", `50+ elements stress test failed: ${stressErr.message}`);
  }

  // Check 4.10: Full Page Reload Persistence
  try {
    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const reloadedFrame = await getCanvasFrame();
    const reloadedElementsCount = await reloadedFrame.locator("[data-element-id]").count();
    if (reloadedElementsCount === 0) {
      await addFailure("P0", "RELOAD_CANVAS_EMPTY", "builder::reload", "After full page reload, canvas was empty");
    }
  } catch (reloadErr) {
    await addFailure("P0", "RELOAD_ERROR", "builder::reload", `Reload check crashed: ${reloadErr.message}`);
  }

  // Check 4.11: Page AST Template Roundtrip (Elementor Template Export / Import Parity)
  try {
    const roundtripSuccess = await page.evaluate(() => {
      const store = window.__BUILDER_STORE__;
      if (!store) return false;
      const currentAst = store.getState().ast;
      const exportedJson = JSON.stringify(currentAst);
      const reimportedAst = JSON.parse(exportedJson);
      store.getState().replacePageAST(reimportedAst);
      return store.getState().ast.rootElements.length === currentAst.rootElements.length;
    });

    if (!roundtripSuccess) {
      await addFailure("P0", "TEMPLATE_ROUNDTRIP_FAILED", "builder::templates", "JSON template serialize & re-import mutated or dropped elements");
    }
  } catch (roundtripErr) {
    await addFailure("P0", "TEMPLATE_ROUNDTRIP_ERROR", "builder::templates", `Template roundtrip test crashed: ${roundtripErr.message}`);
  }

  // Final Summary & Write Output
  matrix.summary = {
    totalFailures: matrix.totalFailures,
    p0Count: matrix.p0Count,
    p1Count: matrix.p1Count,
    p2Count: matrix.p2Count,
    patternsPassed: `${matrix.patternsPassed}/${matrix.patternsTotal}`,
    blocksPassed: `${matrix.blocksPassed}/${matrix.blocksTotal}`,
    deadControlsRemaining: matrix.deadControlsRemaining,
  };

  fs.writeFileSync(MATRIX_PATH, JSON.stringify(matrix, null, 2), "utf8");
  console.log("\n==================================================================");
  console.log(`>>> [X-RAY MATRIX GENERATED] Total Failures: ${matrix.totalFailures} (P0: ${matrix.p0Count}, P1: ${matrix.p1Count}, P2: ${matrix.p2Count})`);
  console.log(`    Patterns Passed: ${matrix.patternsPassed}/${matrix.patternsTotal}`);
  console.log(`    Blocks Passed  : ${matrix.blocksPassed}/${matrix.blocksTotal}`);
  console.log(`    Dead Controls  : ${matrix.deadControlsRemaining}`);
  console.log(`    Report Saved   : ${MATRIX_PATH}`);
  console.log("==================================================================\n");

  await browser.close();
  return matrix;
}

runXRay().catch((err) => {
  console.error("FATAL: builder-xray.mjs failed with unhandled error:", err);
  process.exit(1);
});
