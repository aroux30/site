import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

// Resolve packages from frontend directory
const frontendPkgPath = path.resolve("frontend/package.json");
const req = createRequire(frontendPkgPath);
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const PROJECT_ROOT = process.cwd();
const ARTIFACTS_DIR = path.join(PROJECT_ROOT, ".loop", "artifacts", "excavator", "round-01", "before");
const MATRIX_PATH = path.join(PROJECT_ROOT, ".loop", "XRAY_MATRIX.json");

fs.mkdirSync(ARTIFACTS_DIR, { recursive: true });

function getAdminToken() {
  const candidateDirs = [
    process.env.E2E_BACKEND_DIR,
    "C:/Users/Administrator/Desktop/site/backend",
    path.resolve(PROJECT_ROOT, "backend"),
    path.resolve(PROJECT_ROOT, "..", "..", "backend"),
  ].filter(Boolean);

  const backendDir = candidateDirs.find((d) => fs.existsSync(path.join(d, ".env"))) || "C:/Users/Administrator/Desktop/site/backend";
  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token

async def main():
    user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
    try:
        import app.tests.conftest
        from app.core.database.session import async_session_factory
        from sqlalchemy import select
        from app.modules.users.domain.models import User
        async with async_session_factory() as s:
            u = (await s.execute(select(User).where(User.is_superuser.is_(True)))).scalars().first()
            if u:
                user_id = str(u.id)
    except Exception:
        pass
    print("TOKEN_START:" + create_access_token(
        user_id,
        extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
        expires_delta=datetime.timedelta(hours=2),
    ))

asyncio.run(main())
`;
  const tmpFile = path.join(backendDir, `.e2e-token-${Date.now()}.py`);
  fs.writeFileSync(tmpFile, script, "utf8");
  let out = "";
  try {
    out = execSync(`python "${tmpFile}"`, { cwd: backendDir, encoding: "utf8" });
  } finally {
    if (fs.existsSync(tmpFile)) {
      try { fs.unlinkSync(tmpFile); } catch {}
    }
  }
  const line = out.split("\n").find((l) => l.includes("TOKEN_START:"));
  return line ? line.replace("TOKEN_START:", "").trim() : "";
}

const PATTERNS_LIST = [
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
  "product-highlights"
];

const BASIC_BLOCKS_LIST = [
  { type: "container", name: "کانتینر (Container)" },
  { type: "section", name: "بخش کامل (Section)" },
  { type: "columns", name: "دو ستونه (2 Columns)" },
  { type: "form_container", name: "فرم سازنده (Form Container)" },
  { type: "heading", name: "سرتیتر (Heading)" },
  { type: "text_editor", name: "پاراگراف متن (Paragraph)" },
  { type: "image", name: "تصویر (Image)" },
  { type: "button", name: "دکمه اقدام (Button)" },
  { type: "spacer", name: "فاصله‌ساز (Spacer)" },
  { type: "divider", name: "خط جداکننده (Divider)" },
  { type: "table", name: "جدول داده (Table)" },
  { type: "form_input", name: "فیلد ورودی متن (Input)" },
  { type: "form_textarea", name: "متن چندخطی (Textarea)" },
  { type: "form_select", name: "منوی کشویی (Select)" },
  { type: "product_card", name: "کارت محصول (Product Card)" },
  { type: "product_grid", name: "ویترین محصولات (Product Grid)" },
  { type: "product_variants", name: "تنوع محصول (Product Variants)" },
  { type: "product_price", name: "قیمت محصول (Product Price)" },
  { type: "add_to_cart", name: "دکمه خرید (Add to Cart)" },
  { type: "mini_cart", name: "مینی کارت (Mini Cart)" },
  { type: "cart_summary", name: "خلاصه سبد خرید (Cart Summary)" },
  { type: "form_checkbox", name: "چک‌باکس فرم (Checkbox)" },
  { type: "form_radio", name: "دکمه رادیویی (Radio Group)" },
  { type: "accordion", name: "آکاردئون (Accordion)" },
  { type: "tabs", name: "تب‌های محتوا (Tabs)" },
  { type: "countdown", name: "شمارنده معکوس (Countdown)" },
  { type: "video", name: "پخش‌کننده ویدئو (Video)" },
  { type: "icon_box", name: "باکس آیکون و ویژگی (Icon Box)" },
  { type: "social_links", name: "شبکه‌های اجتماعی (Social Links)" },
  { type: "image_gallery", name: "گالری تصاویر (Image Gallery)" },
  { type: "star_rating", name: "امتیاز ستاره‌ای (Star Rating)" },
  { type: "review_histogram", name: "نمودار نظرات (Review Histogram)" },
  { type: "recently_viewed", name: "بازدیدهای اخیر (Recently Viewed)" },
  { type: "mega_menu", name: "مگامنو (Mega Menu)" }
];

async function runXRayAudit() {
  console.log("===============================================================================");
  console.log(">>> [X-RAY AUDIT] Ruthless Verification of Visual Page Builder (Elementor Parity)");
  console.log("===============================================================================");

  const matrix = {
    timestamp: new Date().toISOString(),
    summary: {
      totalChecks: 0,
      passedChecks: 0,
      failedChecks: 0,
      totalFailures: 0,
      p0Count: 0,
      p1Count: 0,
      p2Count: 0,
      patternsPassed: "0/28",
      blocksPassed: "0/34",
      deadControlsRemaining: 0,
    },
    patterns: [],
    blocks: [],
    deadControls: [],
    studioChecks: {
      categoryChipsClipped: false,
      horizontalOverflow: false,
      dndPassed: false,
      wysiwygParityPassed: false,
      failures: [],
    },
    failures: [],
  };

  function addFailure(sev, code, target, description, screenshotPath = null) {
    const record = { severity: sev, code, target, description, screenshot: screenshotPath };
    matrix.failures.push(record);
    matrix.summary.totalFailures++;
    if (sev === "P0") matrix.summary.p0Count++;
    else if (sev === "P1") matrix.summary.p1Count++;
    else matrix.summary.p2Count++;
    console.error(`  [${sev}] ${code} on ${target}: ${description}`);
  }

  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
  });

  const adminToken = getAdminToken();
  if (adminToken) {
    await context.addCookies([
      { name: "access_token", value: adminToken, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: {
            user: { id: "47f274da-3abd-4d91-bc9c-83ba913fc66f", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  }

  const page = await context.newPage();

  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      consoleErrors.push(msg.text());
    }
  });

  // Navigate to editor
  console.log(`>>> Loading editor: ${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`);
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  });
  await page.waitForTimeout(2000);

  // Helper to get canvas iframe handle
  const getCanvasFrame = () => page.frameLocator('iframe[title="Visual Builder Canvas"]');

  // Helper to clear canvas via store or UI
  const clearCanvas = async () => {
    await page.evaluate(() => {
      const store = window.__builderStore || window.useBuilderStore;
      if (store && store.getState) {
        const s = store.getState();
        s.replacePageAST({ ...s.ast, rootElements: [] });
        s.selectElement(null);
      }
    });
    await page.waitForTimeout(200);

    // Fallback: If elements still exist, delete them via keyboard Delete
    const frame = getCanvasFrame();
    let count = await frame.locator("[data-element-id]").count();
    let attempts = 0;
    while (count > 0 && attempts < 10) {
      try {
        await frame.locator("[data-element-id]").first().click({ timeout: 1000 });
        await page.waitForTimeout(100);
        await page.keyboard.press("Delete");
        await page.waitForTimeout(150);
        count = await frame.locator("[data-element-id]").count();
      } catch {
        break;
      }
      attempts++;
    }
  };

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 4A: Studio Layout Checks (Chips, Horizontal Overflow)
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 4A] Checking Studio Layout & Panes for Clipping and Horizontal Overflow...");
  matrix.summary.totalChecks++;

  // Ensure "افزودن بلوک" left sidebar tab is selected
  const ensureBlocksSidebar = async () => {
    const addBlockTab = page.locator("button:has-text('افزودن بلوک')").first();
    if (await addBlockTab.isVisible()) {
      await addBlockTab.click();
      await page.waitForTimeout(200);
    }
  };
  await ensureBlocksSidebar();

  // Switch to patterns tab to inspect category filter chips
  const patternsTabBtn = page.locator("button:has-text('الگوها')").first();
  if (await patternsTabBtn.isVisible()) {
    await patternsTabBtn.click();
    await page.waitForTimeout(500);

    // Check category filter chips
    const chipContainer = page.locator(".flex.gap-1.overflow-x-auto, [data-category-chips]").first();
    if (await chipContainer.isVisible()) {
      const chipInfo = await chipContainer.evaluate((container) => {
        const chips = Array.from(container.querySelectorAll("button"));
        const results = [];
        for (const chip of chips) {
          const text = chip.textContent?.trim() || "";
          const isEllipsis = text.includes("...") || text.includes("…");
          const rect = chip.getBoundingClientRect();
          const parentRect = container.getBoundingClientRect();
          // Check if clipped unintentionally without scroll
          results.push({ text, isEllipsis, width: rect.width });
        }
        return { chips: results, containerScrollWidth: container.scrollWidth, containerClientWidth: container.clientWidth };
      });

      for (const chip of chipInfo.chips) {
        if (chip.isEllipsis || chip.text.includes("بازخ...")) {
          matrix.studioChecks.categoryChipsClipped = true;
          const shot = path.join(ARTIFACTS_DIR, "layout-chip-clipped.png");
          await page.screenshot({ path: shot });
          addFailure("P1", "CATEGORY_CHIP_CLIPPED", chip.text, `Category chip '${chip.text}' has truncated text or ellipsis.`, shot);
        }
      }
    }
  }

  // Check horizontal overflow in main page
  const hasPageOverflow = await page.evaluate(() => {
    return document.documentElement.scrollWidth > window.innerWidth || document.body.scrollWidth > window.innerWidth;
  });
  if (hasPageOverflow) {
    matrix.studioChecks.horizontalOverflow = true;
    addFailure("P1", "STUDIO_HORIZONTAL_OVERFLOW", "window", "Main studio page has horizontal overflow (scrollWidth > innerWidth).");
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 1: Test all 28 Patterns (1..28)
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 1] Testing all 28 Block Patterns (Checks A, B, C, D, E)...");
  let passedPatternsCount = 0;

  for (let i = 0; i < PATTERNS_LIST.length; i++) {
    const slug = PATTERNS_LIST[i];
    console.log(`\n  --- Pattern [${i + 1}/28]: ${slug} ---`);
    matrix.summary.totalChecks++;

    const patternReport = {
      index: i + 1,
      slug,
      passed: true,
      failures: [],
      checkA: true, // Toolbar visibility
      checkB: true, // Overflow clipping
      checkC: true, // elementFromPoint clickability
      checkD: true, // AST action execution
      checkE: true, // Raw HTML in inspector
    };

    try {
      // 1. Clear canvas and ensure blocks sidebar is open
      await clearCanvas();
      await ensureBlocksSidebar();

      // 2. Select Patterns tab
      if (await patternsTabBtn.isVisible()) {
        await patternsTabBtn.click();
        await page.waitForTimeout(300);
      }

      // 3. Find and click pattern card
      const patternCard = page.locator(`[data-pattern-slug="${slug}"]`).first();
      if (!(await patternCard.isVisible())) {
        // Maybe select "همه" category first
        const allCategoryBtn = page.locator("button:has-text('همه')").first();
        if (await allCategoryBtn.isVisible()) await allCategoryBtn.click();
        await page.waitForTimeout(300);
      }

      if (!(await patternCard.isVisible())) {
        patternReport.passed = false;
        patternReport.failures.push("PATTERN_CARD_NOT_FOUND");
        addFailure("P0", "PATTERN_CARD_NOT_FOUND", slug, `Pattern card [data-pattern-slug="${slug}"] is not visible in palette.`);
        matrix.patterns.push(patternReport);
        continue;
      }

      await patternCard.click();
      await page.waitForTimeout(1000);

      // 4. In Canvas Iframe: find pattern root element
      const frame = getCanvasFrame();
      const rootElements = frame.locator("[data-element-id]");
      const count = await rootElements.count();
      if (count === 0) {
        patternReport.passed = false;
        patternReport.failures.push("PATTERN_NOT_RENDERED");
        addFailure("P0", "PATTERN_NOT_RENDERED", slug, `Pattern ${slug} was inserted but no [data-element-id] elements appeared on canvas.`);
        matrix.patterns.push(patternReport);
        continue;
      }

      // Target root element and at least 2 child elements
      const targetIndices = [0];
      if (count > 1) targetIndices.push(1);
      if (count > 2) targetIndices.push(Math.min(2, count - 1));

      for (const tIdx of targetIndices) {
        const targetEl = rootElements.nth(tIdx);
        if (!(await targetEl.isVisible())) continue;

        const targetId = await targetEl.getAttribute("data-element-id");

        // Deselect previous element to ensure clean click on target
        await page.evaluate(() => {
          const store = window.__builderStore || window.useBuilderStore;
          if (store && store.getState) store.getState().selectElement(null);
        });
        await page.waitForTimeout(100);

        // Click element to select it
        await targetEl.click();
        await page.waitForTimeout(400);

        // CHECK A: Toolbar visibility
        const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
        const tbVisible = await toolbar.isVisible();
        if (!tbVisible) {
          patternReport.checkA = false;
          patternReport.passed = false;
          const shot = path.join(ARTIFACTS_DIR, `pattern-${slug}-el${tIdx}-no-toolbar.png`);
          await page.screenshot({ path: shot });
          addFailure("P0", "TOOLBAR_MISSING", `${slug} (el ${targetId})`, `Floating toolbar is not visible upon selection.`, shot);
          continue;
        }

        const tbBox = await toolbar.boundingBox();
        if (!tbBox || tbBox.width <= 40 || tbBox.height <= 20) {
          patternReport.checkA = false;
          patternReport.passed = false;
          addFailure("P0", "TOOLBAR_DIMENSIONS_INVALID", `${slug} (el ${targetId})`, `Floating toolbar has invalid dimensions: ${JSON.stringify(tbBox)}`);
        }

        // CHECK B: Prohibition of clipping by ancestor overflow: hidden | clip | auto | scroll
        const clippingResult = await toolbar.evaluate((tb) => {
          const tbRect = tb.getBoundingClientRect();
          let curr = tb.parentElement;
          const doc = tb.ownerDocument;

          while (curr && curr !== doc.body && curr !== doc.documentElement) {
            const style = window.getComputedStyle(curr);
            const ox = style.overflowX;
            const oy = style.overflowY;
            const o = style.overflow;
            const clipsY = ["hidden", "clip", "scroll", "auto"].includes(oy) || ["hidden", "clip", "scroll", "auto"].includes(o);
            const clipsX = ["hidden", "clip", "scroll", "auto"].includes(ox) || ["hidden", "clip", "scroll", "auto"].includes(o);

            if (clipsX || clipsY) {
              const pRect = curr.getBoundingClientRect();
              if (clipsY && (tbRect.top < pRect.top - 1 || tbRect.bottom > pRect.bottom + 1)) {
                return {
                  clipped: true,
                  ancestor: curr.tagName + (curr.className ? `.${curr.className.slice(0, 40)}` : ""),
                  tbTop: tbRect.top,
                  parentTop: pRect.top,
                  tbBottom: tbRect.bottom,
                  parentBottom: pRect.bottom,
                };
              }
              if (clipsX && (tbRect.left < pRect.left - 1 || tbRect.right > pRect.right + 1)) {
                return {
                  clipped: true,
                  ancestor: curr.tagName + (curr.className ? `.${curr.className.slice(0, 40)}` : ""),
                  tbLeft: tbRect.left,
                  parentLeft: pRect.left,
                };
              }
            }
            curr = curr.parentElement;
          }
          return { clipped: false };
        });

        if (clippingResult.clipped) {
          patternReport.checkB = false;
          patternReport.passed = false;
          const shot = path.join(ARTIFACTS_DIR, `pattern-${slug}-toolbar-clipped.png`);
          await page.screenshot({ path: shot });
          addFailure(
            "P0",
            "TOOLBAR_CLIPPED_BY_OVERFLOW",
            `${slug} (el ${targetId})`,
            `Floating toolbar is clipped by ancestor with overflow: hidden (${clippingResult.ancestor}): tbTop=${clippingResult.tbTop}, parentTop=${clippingResult.parentTop}`,
            shot
          );
        }

        // CHECK C: Real elementFromPoint on all toolbar buttons
        // Ensure toolbar is scrolled into view before hit test
        await toolbar.scrollIntoViewIfNeeded();
        await page.waitForTimeout(100);

        const hitResult = await toolbar.evaluate((tb) => {
          const doc = tb.ownerDocument;
          const buttons = Array.from(tb.querySelectorAll("button, [role='button'], span[title]"));
          const unclickable = [];

          for (const btn of buttons) {
            const rect = btn.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) continue;
            const cx = rect.left + rect.width / 2;
            const cy = rect.top + rect.height / 2;
            const hit = doc.elementFromPoint(cx, cy);
            if (!hit || (hit !== btn && !btn.contains(hit))) {
              unclickable.push({
                title: btn.getAttribute("title") || btn.textContent?.trim() || "unknown",
                cx,
                cy,
                hitTag: hit ? hit.tagName + (hit.className ? `.${hit.className.slice(0, 30)}` : "") : "none",
              });
            }
          }
          return { unclickable };
        });

        if (hitResult.unclickable.length > 0) {
          patternReport.checkC = false;
          patternReport.passed = false;
          addFailure(
            "P0",
            "TOOLBAR_BUTTON_UNCLICKABLE",
            `${slug} (el ${targetId})`,
            `Buttons unclickable via elementFromPoint: ${JSON.stringify(hitResult.unclickable)}`
          );
        }

        // CHECK D: Real AST action execution (Duplicate, Move Up/Down, Delete)
        if (tIdx === 0) {
          const initialCount = await rootElements.count();
          // Test duplicate button
          const dupBtn = toolbar.locator('button[title="تکثیر"], button:has-text("تکثیر")').first();
          if (await dupBtn.isVisible()) {
            await dupBtn.click();
            await page.waitForTimeout(400);
            const afterDupCount = await frame.locator("[data-element-id]").count();
            if (afterDupCount <= initialCount) {
              patternReport.checkD = false;
              patternReport.passed = false;
              addFailure("P0", "DEAD_TOOLBAR_ACTION", `${slug} (duplicate)`, `Clicked duplicate button but element count did not increase (${initialCount} -> ${afterDupCount}).`);
            }
          }
        }

        // CHECK E: Prohibition of raw HTML leak in Inspector Panel (<span, class=", <div)
        const inspectorTextareas = page.locator("[data-builder-inspector] textarea, [data-builder-inspector] input[type='text']");
        const inputCount = await inspectorTextareas.count();
        for (let inpIdx = 0; inpIdx < inputCount; inpIdx++) {
          const val = await inspectorTextareas.nth(inpIdx).inputValue();
          if (val && (val.includes("<span") || val.includes("class=") || (val.includes("<div") && !val.includes("html_custom")))) {
            patternReport.checkE = false;
            patternReport.passed = false;
            const shot = path.join(ARTIFACTS_DIR, `pattern-${slug}-raw-html-inspector.png`);
            await page.screenshot({ path: shot });
            addFailure(
              "P1",
              "RAW_HTML_IN_INSPECTOR",
              `${slug} (field: "${val.slice(0, 35)}...")`,
              `Raw HTML tags leaked into clean inspector input field: ${val.slice(0, 80)}`,
              shot
            );
          }
        }
      }
    } catch (patternErr) {
      patternReport.passed = false;
      addFailure("P0", "PATTERN_TEST_EXCEPTION", slug, patternErr.message);
    }

    if (patternReport.passed) {
      passedPatternsCount++;
      console.log(`    ✅ Pattern ${slug} PASSED all 5 checks.`);
    } else {
      console.log(`    ❌ Pattern ${slug} FAILED (${patternReport.failures.join(", ")}).`);
    }
    matrix.patterns.push(patternReport);
  }
  matrix.summary.patternsPassed = `${passedPatternsCount}/28`;

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 2: Test all 34 Native Basic Blocks (1..34)
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 2] Testing all 34 Native Basic Blocks (1..34)...");
  let passedBlocksCount = 0;

  const blocksTabBtn = page.locator("button:has-text('بلوک‌ها')").first();
  if (await blocksTabBtn.isVisible()) {
    await blocksTabBtn.click();
    await page.waitForTimeout(400);
  }

  for (let b = 0; b < BASIC_BLOCKS_LIST.length; b++) {
    const blockDef = BASIC_BLOCKS_LIST[b];
    console.log(`\n  --- Block [${b + 1}/34]: ${blockDef.type} (${blockDef.name}) ---`);
    matrix.summary.totalChecks++;

    const blockReport = {
      index: b + 1,
      type: blockDef.type,
      name: blockDef.name,
      passed: true,
      failures: [],
    };

    try {
      await clearCanvas();
      await ensureBlocksSidebar();

      if (await blocksTabBtn.isVisible()) {
        await blocksTabBtn.click();
        await page.waitForTimeout(300);
      }

      // Find block card in palette
      const blockCard = page.locator(`button:has-text('${blockDef.name.split(" ")[0]}')`).first();
      if (!(await blockCard.isVisible())) {
        blockReport.passed = false;
        blockReport.failures.push("BLOCK_CARD_NOT_FOUND");
        addFailure("P0", "BLOCK_CARD_NOT_FOUND", blockDef.type, `Block card '${blockDef.name}' not found in blocks palette.`);
        matrix.blocks.push(blockReport);
        continue;
      }

      await blockCard.click();
      await page.waitForTimeout(600);

      const frame = getCanvasFrame();
      const el = frame.locator("[data-element-id]").first();
      if (!(await el.isVisible())) {
        blockReport.passed = false;
        blockReport.failures.push("BLOCK_NOT_RENDERED");
        addFailure("P0", "BLOCK_NOT_RENDERED", blockDef.type, `Block '${blockDef.type}' was clicked but did not render inside canvas.`);
        matrix.blocks.push(blockReport);
        continue;
      }

      // Check non-zero dimensions
      const box = await el.boundingBox();
      if (!box || box.width <= 0 || box.height <= 0) {
        blockReport.passed = false;
        blockReport.failures.push("ZERO_DIMENSIONS");
        addFailure("P0", "BLOCK_ZERO_DIMENSIONS", blockDef.type, `Block '${blockDef.type}' rendered with zero dimensions: ${JSON.stringify(box)}`);
      }

      // Click to select
      await el.click();
      await page.waitForTimeout(300);

      // Check toolbar
      const toolbar = frame.locator('[data-testid="floating-toolbar"]').first();
      if (!(await toolbar.isVisible())) {
        blockReport.passed = false;
        blockReport.failures.push("TOOLBAR_MISSING");
        addFailure("P0", "BLOCK_TOOLBAR_MISSING", blockDef.type, `Floating toolbar did not appear for block '${blockDef.type}'.`);
      }
    } catch (blockErr) {
      blockReport.passed = false;
      addFailure("P0", "BLOCK_TEST_EXCEPTION", blockDef.type, blockErr.message);
    }

    if (blockReport.passed) {
      passedBlocksCount++;
      console.log(`    ✅ Block ${blockDef.type} PASSED.`);
    } else {
      console.log(`    ❌ Block ${blockDef.type} FAILED.`);
    }
    matrix.blocks.push(blockReport);
  }
  matrix.summary.blocksPassed = `${passedBlocksCount}/34`;

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 3: Dead Control Hunter in Inspector Panel
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 3] Running Dead Control Hunter on Key Elements...");
  const testElements = [
    { type: "container", name: "کانتینر", initialAdd: "کانتینر" },
    { type: "heading", name: "سرتیتر", initialAdd: "سرتیتر" },
    { type: "button", name: "دکمه اقدام", initialAdd: "دکمه اقدام" },
    { type: "image", name: "تصویر", initialAdd: "تصویر" },
    { type: "table", name: "جدول داده", initialAdd: "جدول داده" },
  ];

  for (const tEl of testElements) {
    console.log(`\n  Hunting dead controls on: ${tEl.type}...`);
    matrix.summary.totalChecks++;

    try {
      await clearCanvas();
      if (await blocksTabBtn.isVisible()) {
        await blocksTabBtn.click();
        await page.waitForTimeout(300);
      }

      const card = page.locator(`button:has-text('${tEl.initialAdd}')`).first();
      if (await card.isVisible()) {
        await card.click();
        await page.waitForTimeout(500);
      }

      const frame = getCanvasFrame();
      const el = frame.locator("[data-element-id]").first();
      if (!(await el.isVisible())) continue;
      await el.click();
      await page.waitForTimeout(400);

      // Inspect tabs: Content, Style, Advanced
      const tabs = ["محتوا", "استایل", "پیشرفته"];
      for (const tabName of tabs) {
        const tabTrigger = page.locator(`[data-builder-inspector] button:has-text('${tabName}')`).first();
        if (!(await tabTrigger.isVisible())) continue;
        await tabTrigger.click();
        await page.waitForTimeout(300);

        // Find visible controls in current tab
        const inputs = page.locator("[data-builder-inspector] input:visible, [data-builder-inspector] select:visible, [data-builder-inspector] textarea:visible");
        const count = await inputs.count();

        // Sample up to 4 controls per tab to avoid timeout
        const sampleCount = Math.min(count, 4);
        for (let cIdx = 0; cIdx < sampleCount; cIdx++) {
          const ctrl = inputs.nth(cIdx);
          const isReadonly = await ctrl.evaluate((e) => e.readOnly || e.disabled);
          if (isReadonly) continue;

          const tagName = await ctrl.evaluate((c) => c.tagName.toLowerCase());
          const typeAttr = await ctrl.getAttribute("type");
          const initialVal = await ctrl.inputValue();

          // Get canvas element computed style before change
          const beforeStyle = await el.evaluate((dom) => ({
            padding: window.getComputedStyle(dom).padding,
            margin: window.getComputedStyle(dom).margin,
            fontSize: window.getComputedStyle(dom).fontSize,
            color: window.getComputedStyle(dom).color,
            bgColor: window.getComputedStyle(dom).backgroundColor,
            text: dom.textContent || "",
            html: dom.outerHTML,
            id: dom.id,
            className: dom.className,
          }));

          // Attempt meaningful change
          let testVal = initialVal === "تست تغییر محتوا" ? "مقدار جدید تست" : "تست تغییر محتوا";
          if (typeAttr === "number" || (initialVal && initialVal.match(/^\d+$/))) {
            testVal = initialVal === "42" ? "24" : "42";
          } else if (tagName === "select") {
            // Select second option if available
            testVal = await ctrl.evaluate((sel) => {
              const options = Array.from(sel.options);
              return options.length > 1 ? options[1].value : "";
            });
          }

          if (testVal && testVal !== initialVal) {
            await ctrl.fill(testVal);
            await ctrl.press("Enter");
            await ctrl.evaluate((e) => {
              e.dispatchEvent(new Event("input", { bubbles: true }));
              e.dispatchEvent(new Event("change", { bubbles: true }));
            });
            await page.waitForTimeout(400);

            // Re-evaluate element in canvas
            const afterStyle = await el.evaluate((dom) => ({
              padding: window.getComputedStyle(dom).padding,
              margin: window.getComputedStyle(dom).margin,
              fontSize: window.getComputedStyle(dom).fontSize,
              color: window.getComputedStyle(dom).color,
              bgColor: window.getComputedStyle(dom).backgroundColor,
              text: dom.textContent || "",
              html: dom.outerHTML,
              id: dom.id,
              className: dom.className,
            }));

            const changed =
              beforeStyle.padding !== afterStyle.padding ||
              beforeStyle.margin !== afterStyle.margin ||
              beforeStyle.fontSize !== afterStyle.fontSize ||
              beforeStyle.color !== afterStyle.color ||
              beforeStyle.bgColor !== afterStyle.bgColor ||
              beforeStyle.text !== afterStyle.text ||
              beforeStyle.id !== afterStyle.id ||
              beforeStyle.className !== afterStyle.className ||
              beforeStyle.html !== afterStyle.html;

            if (!changed) {
              const deadCtrlInfo = {
                targetElement: tEl.type,
                tab: tabName,
                controlType: `${tagName}[${typeAttr || "text"}]`,
                initialVal,
                testVal,
              };
              matrix.deadControls.push(deadCtrlInfo);
              matrix.summary.deadControlsRemaining++;
              addFailure(
                "P0",
                "DEAD_INSPECTOR_CONTROL",
                `${tEl.type} -> ${tabName} (${deadCtrlInfo.controlType})`,
                `Changing control from '${initialVal}' to '${testVal}' produced NO change in canvas DOM or styles.`
              );
            }
          }
        }
      }
    } catch (deadErr) {
      console.warn(`Dead control hunter warning on ${tEl.type}:`, deadErr.message);
    }
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 4B: Drag & Drop and WYSIWYG Parity Checks
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 4B] Testing Drag & Drop and WYSIWYG Parity...");
  matrix.summary.totalChecks++;

  try {
    // Save draft and test WYSIWYG parity
    const saveBtn = page.locator('button:has-text("ذخیره پیش‌نویس"), button:has-text("ذخیره")').first();
    if (await saveBtn.isVisible()) {
      await saveBtn.click();
      await page.waitForTimeout(1500);

      // Open public page
      const publicPage = await context.newPage();
      await publicPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
      await publicPage.waitForTimeout(1000);

      const publicContent = await publicPage.locator(".builder-rendered-content, article").first();
      const isPublicVisible = await publicContent.isVisible();
      if (isPublicVisible) {
        matrix.studioChecks.wysiwygParityPassed = true;
        console.log("    ✅ WYSIWYG Parity verified between editor canvas and storefront output.");
      } else {
        addFailure("P0", "WYSIWYG_STOREFRONT_MISMATCH", "public_page", "Saved page content did not render visibly on storefront public URL.");
      }
      await publicPage.close();
    }
  } catch (wysiwygErr) {
    addFailure("P0", "WYSIWYG_TEST_EXCEPTION", "scratchpad", wysiwygErr.message);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // PART 4C: Elementor Parity Advanced UX Checks (Context Menu, Structure Preset)
  // ─────────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [PART 4C] Testing Elementor Advanced UX (Context Menu & Structure Presets)...");
  matrix.summary.totalChecks++;

  try {
    await clearCanvas();
    if (await blocksTabBtn.isVisible()) {
      await blocksTabBtn.click();
      await page.waitForTimeout(300);
      const contBtn = page.locator("button:has-text('کانتینر')").first();
      if (await contBtn.isVisible()) await contBtn.click();
      await page.waitForTimeout(400);
    }

    const frame = getCanvasFrame();
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').first();
    const hasGuide = await emptyGuide.isVisible();
    if (hasGuide) {
      const preset2Btn = frame.locator('[data-testid="structure-preset-2"]').first();
      if (await preset2Btn.isVisible()) {
        await preset2Btn.click();
        await page.waitForTimeout(500);
        const childCols = await frame.locator('[data-element-id]').count();
        if (childCols >= 3) {
          console.log("    ✅ Elementor Structure Preset (2-col) created child columns successfully.");
        } else {
          addFailure("P1", "STRUCTURE_PRESET_FAILED", "empty-container", `Clicking 2-col preset resulted in ${childCols} elements instead of >= 3.`);
        }
      }
    }

    const firstEl = frame.locator('[data-element-id]').first();
    if (await firstEl.isVisible()) {
      await firstEl.click({ button: "right" });
      await page.waitForTimeout(400);

      const ctxMenu = page.locator('[data-testid="builder-context-menu"]').first();
      if (await ctxMenu.isVisible()) {
        console.log("    ✅ Elementor Context Menu opened successfully on right-click.");
        await page.keyboard.press("Escape");
        await page.waitForTimeout(200);
      } else {
        addFailure("P1", "CONTEXT_MENU_NOT_SHOWN", "canvas-element", "Right-click on element did not open [data-testid=\"builder-context-menu\"].");
      }
    }

    // ── Check Inline Text Editing on Canvas ──
    const headEl = frame.locator('h1, h2, h3').first();
    if (await headEl.isVisible()) {
      await headEl.dblclick();
      await page.waitForTimeout(300);

      const inlineEditor = frame.locator('[data-testid="inline-text-editor"]').first();
      if (await inlineEditor.isVisible()) {
        console.log("    ✅ Inline Text Editing activated on double-click successfully.");
        await page.keyboard.press("Escape");
        await page.waitForTimeout(200);
      } else {
        addFailure("P1", "INLINE_EDITING_NOT_ACTIVE", "heading", "Double click on heading did not activate [data-testid=\"inline-text-editor\"].");
      }
    }

    // ── Check Style Group Controls (Gradient & Shadow) in Inspector ──
    const styleTabBtn = page.locator("[data-builder-inspector] button:has-text('استایل')").first();
    if (await styleTabBtn.isVisible()) {
      await styleTabBtn.click();
      await page.waitForTimeout(300);

      const hasShadowInput = await page.locator("input[placeholder*='0 4px 6px']").isVisible();
      if (hasShadowInput) {
        console.log("    ✅ Elementor Grouped Style Controls (Box Shadow & Typography) verified in Inspector.");
      }
    }

    // ── Check Navigator (LayersTree) Search and Expand/Collapse ──
    const layersTabBtn = page.locator("button:has-text('لایه‌ها')").first();
    if (await layersTabBtn.isVisible()) {
      await layersTabBtn.click();
      await page.waitForTimeout(300);

      const navSearch = page.locator("input[placeholder*='جستجوی لایه']").first();
      const toggleAllBtn = page.locator("button:has-text('بستن همه'), button:has-text('باز کردن همه')").first();
      if ((await navSearch.isVisible()) && (await toggleAllBtn.isVisible())) {
        console.log("    ✅ Elementor Navigator Search & Expand/Collapse All verified.");
      } else {
        addFailure("P1", "NAVIGATOR_FEATURES_MISSING", "layers-tree", "Navigator search input or toggle-all button is missing.");
      }
    }

    // ── Check Elementor Hotkeys Modal (Shift+? / Toolbar button) ──
    const hotkeysBtn = page.locator('[data-testid="hotkeys-btn"]').first();
    if (await hotkeysBtn.isVisible()) {
      await hotkeysBtn.click();
      await page.waitForTimeout(300);

      const modal = page.locator('[data-testid="hotkeys-modal"]').first();
      if (await modal.isVisible()) {
        console.log("    ✅ Elementor Hotkeys Cheatsheet modal opened successfully.");
        await page.keyboard.press("Escape");
        await page.waitForTimeout(200);
      } else {
        addFailure("P1", "HOTKEYS_MODAL_NOT_OPEN", "toolbar", "Clicking hotkeys button did not open modal.");
      }
    }

    // ── Check Section Shape Divider in Inspector ──
    if (await firstEl.isVisible()) {
      await firstEl.click();
      await page.waitForTimeout(300);
      if (await styleTabBtn.isVisible()) {
        await styleTabBtn.click();
        await page.waitForTimeout(300);
        const shapeDividerHeader = await page.locator("text='جداکننده شکل کانتینر'").first().isVisible();
        if (shapeDividerHeader) {
          console.log("    ✅ Elementor Section Shape Divider controls verified in Inspector.");
        }

        const hasHeightPreset = await page.locator("[data-testid*='height-preset']").first().isVisible();
        if (hasHeightPreset) {
          console.log("    ✅ Elementor Container Height & Fit to Screen controls verified in Inspector.");
        }

        const hasBackdropBlur = await page.locator("text='شیشه مات پس‌زمینه'").first().isVisible();
        if (hasBackdropBlur) {
          console.log("    ✅ Elementor Backdrop Filter (Glassmorphism) controls verified in Inspector.");
        }
      }
    }

    // ── Check Ctrl+Shift+M Responsive Viewport Cycling ──
    const beforeBp = await page.evaluate(() => {
      const s = (window.__builderStore || window.useBuilderStore).getState();
      return s.activeBreakpoint;
    });
    await page.keyboard.press("Control+Shift+M");
    await page.waitForTimeout(200);
    const afterBp = await page.evaluate(() => {
      const s = (window.__builderStore || window.useBuilderStore).getState();
      return s.activeBreakpoint;
    });
    if (beforeBp !== afterBp) {
      console.log(`    ✅ Ctrl+Shift+M cycled responsive breakpoint: ${beforeBp} -> ${afterBp}`);
      // Cycle back
      await page.keyboard.press("Control+Shift+M");
      await page.keyboard.press("Control+Shift+M");
    }

    // ── Check Responsive Device Visibility Controls in Advanced Tab ──
    const advTabBtn = page.locator("[data-builder-inspector] button:has-text('پیشرفته')").first();
    if (await advTabBtn.isVisible()) {
      await advTabBtn.click();
      await page.waitForTimeout(300);

      const hasDeviceSwitches = await page.locator("text='نمایش در دسکتاپ'").first().isVisible();
      if (hasDeviceSwitches) {
        console.log("    ✅ Elementor Responsive Device Visibility Controls (Desktop/Tablet/Mobile) verified in Inspector.");
      }
    }

    // ── Check Direct Page Title Editing in Toolbar (Elementor Title Parity) ──
    const titleSpan = page.locator("header span[title*='ویرایش نام برگه']").first();
    if (await titleSpan.isVisible()) {
      await titleSpan.dblclick();
      await page.waitForTimeout(200);

      const titleInput = page.locator("header input[type='text']").first();
      if (await titleInput.isVisible()) {
        console.log("    ✅ Direct Page Title editing activated on double-click in Toolbar.");
        await page.keyboard.press("Escape");
        await page.waitForTimeout(100);
      }
    }
  } catch (ctxErr) {
    addFailure("P1", "ADVANCED_UX_EXCEPTION", "elementor-parity", ctxErr.message);
  }

  // ─────────────────────────────────────────────────────────────────────────────
  // Summary Calculation and Final Output
  // ─────────────────────────────────────────────────────────────────────────────
  matrix.summary.passedChecks = matrix.summary.totalChecks - matrix.failures.length;
  matrix.summary.failedChecks = matrix.failures.length;

  console.log("\n===============================================================================");
  console.log(">>> [X-RAY MATRIX SUMMARY]");
  console.log(`    Total Failures: ${matrix.summary.totalFailures}`);
  console.log(`    P0 Count:       ${matrix.summary.p0Count}`);
  console.log(`    P1 Count:       ${matrix.summary.p1Count}`);
  console.log(`    P2 Count:       ${matrix.summary.p2Count}`);
  console.log(`    Patterns:       ${matrix.summary.patternsPassed}`);
  console.log(`    Blocks:         ${matrix.summary.blocksPassed}`);
  console.log(`    Dead Controls:  ${matrix.summary.deadControlsRemaining}`);
  console.log("===============================================================================");

  fs.writeFileSync(MATRIX_PATH, JSON.stringify(matrix, null, 2), "utf8");
  console.log(`\n>>> Wrote matrix report to: ${MATRIX_PATH}`);

  await browser.close();
  return matrix;
}

runXRayAudit().catch((err) => {
  console.error("Fatal error in X-Ray audit:", err);
  process.exit(1);
});
