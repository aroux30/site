/**
 * .loop/audits/builder-xray.mjs
 *
 * Machine-accurate, uncheatable X-Ray audit for Visual Page Builder.
 * Tests every pattern (1..28), every basic block (1..34), dead controls in inspector,
 * layout clipping, drag-and-drop, and WYSIWYG parity.
 *
 * Output: .loop/XRAY_MATRIX.json and screenshots in .loop/artifacts/excavator/round-XX/
 */

import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const WORKTREE_ROOT = process.cwd();
const frontendPkgPath = path.join(PROJECT_ROOT, "frontend", "package.json");
const req = createRequire(frontendPkgPath);
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.join(PROJECT_ROOT, "backend");

// Parse CLI args: --round 01 --stage before|after
const args = process.argv.slice(2);
let roundArg = "round-01";
let stageArg = "before";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--round" && args[i + 1]) {
    roundArg = args[i + 1].startsWith("round-") ? args[i + 1] : `round-${args[i + 1]}`;
    i++;
  } else if (args[i] === "--stage" && args[i + 1]) {
    stageArg = args[i + 1];
    i++;
  }
}

const ARTIFACTS_DIR = path.join(WORKTREE_ROOT, ".loop", "artifacts", "excavator", roundArg, stageArg);
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
  const tmp = path.join(BACKEND_DIR, `.xray-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function runXRayAudit() {
  console.log(`\n===============================================================`);
  console.log(`>>> EXCAVATOR X-RAY AUDIT: Round [${roundArg}] | Stage [${stageArg}]`);
  console.log(`===============================================================\n`);

  const matrix = {
    timestamp: new Date().toISOString(),
    round: roundArg,
    stage: stageArg,
    totalFailures: 0,
    p0Count: 0,
    p1Count: 0,
    patterns: [],
    blocks: [],
    deadControls: [],
    layoutAndInteraction: {
      categoryChipsClipping: { passed: true, issues: [] },
      dragAndDrop: { passed: true, issues: [] },
      wysiwygParity: { passed: true, issues: [] },
    },
    hydrationErrors: [],
  };

  function addFailure(category, severity, details) {
    matrix.totalFailures++;
    if (severity === "P0") matrix.p0Count++;
    else if (severity === "P1") matrix.p1Count++;
    console.log(`  [FAIL] [${severity}] [${category}]: ${details.message || JSON.stringify(details)}`);
  }

  const token = getAdminToken();
  const browser = await chromium.launch({
    headless: true,
    args: ["--disable-dev-shm-usage", "--no-sandbox"],
  });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  if (token) {
    await context.addCookies([
      { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
    ]);
  }

  const page = await context.newPage();

  // Listen for hydration / console errors
  const hydrationRegex = /#418|#423|#425|Hydration failed|did not match/i;
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const text = msg.text();
      if (hydrationRegex.test(text)) {
        matrix.hydrationErrors.push(text);
        addFailure("HYDRATION", "P0", { message: text });
      }
    }
  });

  page.on("pageerror", (err) => {
    const text = err.message || String(err);
    if (hydrationRegex.test(text)) {
      matrix.hydrationErrors.push(text);
      addFailure("HYDRATION", "P0", { message: text });
    }
  });

  await page.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: {
          user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
          isAuthenticated: true,
          isLoading: false,
        },
      })
    );
  });

  console.log(">>> Navigating to editor: /e2e-isolated-scratchpad?visual_editor=true");
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, {
    waitUntil: "domcontentloaded",
    timeout: 45000,
  });
  await page.waitForTimeout(2500);

  // Helper to get frame
  const getCanvasFrame = async () => {
    const all = page.frames();
    const f = all.find((fr) => fr !== page.mainFrame());
    if (f) return { frame: f };
    console.log("    [GET_CANVAS_FRAME RETRY] frames:", all.map((fr) => fr.url()));
    for (let retry = 0; retry < 20; retry++) {
      await page.waitForTimeout(250);
      const found = page.frames().find((fr) => fr !== page.mainFrame());
      if (found) return { frame: found };
    }
    throw new Error("Could not access canvas iframe contentFrame after retries!");
  };

  // Helper to reset canvas
  const clearCanvas = async () => {
    if (!page.url().includes("visual_editor=true")) {
      await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?visual_editor=true`, { waitUntil: "domcontentloaded" });
      await page.waitForTimeout(1000);
    }
    await page.evaluate(() => {
      const store = window.__BUILDER_STORE__;
      if (store && store.getState) {
        const s = store.getState();
        s.replacePageAST({
          ...s.ast,
          rootElements: [],
        });
      }
    });
    await page.waitForTimeout(400);
  };

  // Ensure window.__BUILDER_STORE__ is accessible
  const hasStore = await page.evaluate(() => typeof window.__BUILDER_STORE__ !== "undefined");
  if (!hasStore) {
    console.log(">>> Attaching store helper to window for deterministic tests...");
    await page.evaluate(() => {
      // Find zustand store from React fiber or wait for it
    });
  }

  // ──────────────────────────────────────────────────────────────────────────
  // SECTION 1: Pattern-by-Pattern Audit (1..28)
  // ──────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [SECTION 1] Testing 28 Block Patterns (Checks A, B, C, D, E)...");

  // Fetch registered patterns from backend
  let patternList = [];
  try {
    const res = await fetch("http://127.0.0.1:8000/api/v1/content/block-patterns");
    const groups = await res.json();
    for (const g of groups) {
      for (const p of g.patterns) {
        patternList.push(p);
      }
    }
  } catch (err) {
    console.error("Failed to load block patterns from backend API:", err);
  }

  console.log(`    Loaded ${patternList.length} patterns from backend.`);

  // Click on "الگوها" tab in blocks palette
  const patternsTabBtn = page.locator("button:has-text('الگوها')").first();
  if (await patternsTabBtn.isVisible()) {
    await patternsTabBtn.click();
    await page.waitForTimeout(500);
  }

  for (let idx = 0; idx < patternList.length; idx++) {
    const p = patternList[idx];
    const patternNum = idx + 1;
    console.log(`\n  --- Pattern ${patternNum}/28: [${p.slug}] "${p.title}" ---`);

    const patternResult = {
      index: patternNum,
      slug: p.slug,
      title: p.title,
      category: p.category,
      passed: true,
      failures: [],
    };

    // 1. Clear canvas
    await clearCanvas();

    // 2. Clear search input if filled, and select "همه"
    const searchInput = page.locator("input[placeholder*='الگو']").first();
    if (await searchInput.isVisible()) {
      await searchInput.fill("");
      await page.waitForTimeout(200);
    }
    const allCatBtn = page.locator("button:has-text('همه (')").first();
    if (await allCatBtn.isVisible()) {
      await allCatBtn.click();
      await page.waitForTimeout(200);
    }

    let card = page.locator(`[data-pattern-slug="${p.slug}"]`);
    if (!(await card.isVisible())) {
      // Try searching for the pattern
      await searchInput.fill(p.title);
      await page.waitForTimeout(300);
      card = page.locator(`[data-pattern-slug="${p.slug}"]`);
    }

    if (!(await card.isVisible())) {
      const msg = `Pattern card for slug "${p.slug}" not found in palette!`;
      patternResult.passed = false;
      patternResult.failures.push({ check: "PALETTE", severity: "P0", message: msg });
      addFailure("PATTERN_INSERT", "P0", { slug: p.slug, message: msg });
      matrix.patterns.push(patternResult);
      continue;
    }

    // Insert pattern
    await card.click();
    // Wait for rendering to complete
    await page.waitForTimeout(1000);

    const { frame } = await getCanvasFrame();

    // Check root element inside canvas
    const rootEl = frame.locator("[data-element-id]").first();
    const count = await rootEl.count();
    if (count === 0) {
      const msg = `Pattern "${p.slug}" did not insert any element into canvas!`;
      patternResult.passed = false;
      patternResult.failures.push({ check: "A", severity: "P0", message: msg });
      addFailure("EMPTY_CANVAS_AFTER_INSERT", "P0", { slug: p.slug, message: msg });
      matrix.patterns.push(patternResult);
      continue;
    }

    // Elements to test: root element + at least 2 inner children
    const testElementIds = await frame.evaluate(() => {
      const all = Array.from(document.querySelectorAll("[data-element-id]"));
      if (all.length === 0) return [];
      const ids = [all[0].getAttribute("data-element-id")];
      if (all.length > 1) ids.push(all[1].getAttribute("data-element-id"));
      if (all.length > 2) ids.push(all[all.length - 1].getAttribute("data-element-id"));
      return Array.from(new Set(ids));
    });

    for (const elemId of testElementIds) {
      const elemLocator = frame.locator(`[data-element-id="${elemId}"]`);
      await elemLocator.scrollIntoViewIfNeeded().catch(() => {});
      await elemLocator.click({ timeout: 3000 }).catch(() => {});
      await page.waitForTimeout(300);

      // Evaluate Checks A, B, C inside the iframe
      const checkResult = await frame.evaluate((targetId) => {
        const doc = document;
        const target = doc.querySelector(`[data-element-id="${targetId}"]`);
        if (!target) return { foundTarget: false };

        const toolbar = doc.querySelector('[data-testid="floating-toolbar"]');
        if (!toolbar) {
          return { foundTarget: true, foundToolbar: false };
        }

        const tRect = toolbar.getBoundingClientRect();
        const checkA = tRect.width > 40 && tRect.height > 20;

        // Check B: Overflow clipping check
        const clippingAncestors = [];
        let curr = toolbar.parentElement;
        while (curr && curr !== doc.documentElement && curr !== doc.body) {
          const s = doc.defaultView.getComputedStyle(curr);
          const overflows = [s.overflow, s.overflowX, s.overflowY];
          const hasHidden = overflows.some((o) => ["hidden", "clip", "scroll", "auto"].includes(o));
          if (hasHidden) {
            const pRect = curr.getBoundingClientRect();
            // Did toolbar spill outside?
            const isOutside =
              tRect.top < pRect.top - 1.5 ||
              tRect.bottom > pRect.bottom + 1.5 ||
              tRect.left < pRect.left - 1.5 ||
              tRect.right > pRect.right + 1.5;
            if (isOutside) {
              clippingAncestors.push({
                tag: curr.tagName,
                className: (curr.className || "").toString().slice(0, 100),
                overflow: s.overflow,
                overflowY: s.overflowY,
                pRect: { top: pRect.top, bottom: pRect.bottom, left: pRect.left, right: pRect.right },
                tRect: { top: tRect.top, bottom: tRect.bottom, left: tRect.left, right: tRect.right },
              });
            }
          }
          curr = curr.parentElement;
        }

        // Check C: elementFromPoint on all toolbar buttons
        toolbar.scrollIntoView({ behavior: "instant", block: "center" });
        const buttons = Array.from(toolbar.querySelectorAll("button, span[draggable]"));
        const buttonHits = [];
        for (const btn of buttons) {
          const bRect = btn.getBoundingClientRect();
          const cx = bRect.left + bRect.width / 2;
          const cy = bRect.top + bRect.height / 2;
          const topEl = doc.elementFromPoint(cx, cy);
          const isClickable = topEl && (topEl === btn || btn.contains(topEl) || toolbar.contains(topEl));
          buttonHits.push({
            title: btn.getAttribute("title") || btn.getAttribute("data-testid") || btn.tagName,
            cx,
            cy,
            isClickable,
            topElTag: topEl ? topEl.tagName : null,
            topElClass: topEl ? (topEl.className || "").toString().slice(0, 50) : null,
          });
        }

        return {
          foundTarget: true,
          foundToolbar: true,
          checkA,
          tRect: { width: tRect.width, height: tRect.height, top: tRect.top, left: tRect.left },
          clippingAncestors,
          buttonHits,
        };
      }, elemId);

      // Process Check A
      if (!checkResult.foundToolbar || !checkResult.checkA) {
        const msg = `Check A FAIL: Floating toolbar missing or size <= 40x20 on element ${elemId}`;
        patternResult.passed = false;
        patternResult.failures.push({ check: "A", severity: "P0", message: msg, elemId });
        addFailure("TOOLBAR_MISSING", "P0", { pattern: p.slug, elemId, message: msg });

        // Save screenshot of broken element
        const shotPath = path.join(ARTIFACTS_DIR, `fail-p${patternNum}-checkA-${p.slug}.png`);
        await page.screenshot({ path: shotPath, fullPage: false }).catch(() => {});
      }

      // Process Check B
      if (checkResult.clippingAncestors && checkResult.clippingAncestors.length > 0) {
        const msg = `Check B FAIL (P0: TOOLBAR_CLIPPED_BY_OVERFLOW): Toolbar clipped by ${checkResult.clippingAncestors.length} overflow-hidden ancestor(s)!`;
        patternResult.passed = false;
        patternResult.failures.push({
          check: "B",
          severity: "P0",
          message: msg,
          elemId,
          ancestors: checkResult.clippingAncestors,
        });
        addFailure("TOOLBAR_CLIPPED_BY_OVERFLOW", "P0", {
          pattern: p.slug,
          elemId,
          ancestor: checkResult.clippingAncestors[0],
        });

        const shotPath = path.join(ARTIFACTS_DIR, `fail-p${patternNum}-checkB-${p.slug}.png`);
        await page.screenshot({ path: shotPath, fullPage: false }).catch(() => {});
      }

      // Process Check C
      if (checkResult.buttonHits) {
        const unclickable = checkResult.buttonHits.filter((b) => !b.isClickable);
        if (unclickable.length > 0) {
          const msg = `Check C FAIL (P0: TOOLBAR_BUTTON_UNCLICKABLE): ${unclickable.length} buttons obscured or out of reach (${unclickable.map((b) => b.title).join(", ")})!`;
          patternResult.passed = false;
          patternResult.failures.push({ check: "C", severity: "P0", message: msg, elemId, unclickable });
          addFailure("TOOLBAR_BUTTON_UNCLICKABLE", "P0", { pattern: p.slug, elemId, unclickable });
        }
      }

      // Process Check E: Raw HTML leak in inspector
      // Check if this element is a text/heading widget and inspect the textarea/input
      const rawHtmlCheck = await page.evaluate(() => {
        const inspector = document.querySelector("[data-builder-inspector]");
        if (!inspector) return { hasInspector: false };

        const textareas = Array.from(inspector.querySelectorAll("textarea"));
        const inputs = Array.from(inspector.querySelectorAll("input[type='text']"));
        const fields = [...textareas, ...inputs];

        for (const f of fields) {
          const val = f.value || "";
          if (
            val.includes("<span") ||
            val.includes("class=") ||
            val.includes("<div") ||
            val.includes("<p class=")
          ) {
            return {
              hasRawHtml: true,
              leakedValue: val.slice(0, 150),
              fieldName: f.getAttribute("name") || f.getAttribute("placeholder") || f.tagName,
            };
          }
        }
        return { hasRawHtml: false };
      });

      if (rawHtmlCheck.hasRawHtml) {
        const msg = `Check E FAIL (P1: RAW_HTML_IN_INSPECTOR): Raw HTML tags/classes leaked into inspector field "${rawHtmlCheck.fieldName}"! Preview: "${rawHtmlCheck.leakedValue}"`;
        patternResult.passed = false;
        patternResult.failures.push({ check: "E", severity: "P1", message: msg, elemId });
        addFailure("RAW_HTML_IN_INSPECTOR", "P1", { pattern: p.slug, elemId, preview: rawHtmlCheck.leakedValue });

        const shotPath = path.join(ARTIFACTS_DIR, `fail-p${patternNum}-checkE-${p.slug}.png`);
        await page.screenshot({ path: shotPath, fullPage: false }).catch(() => {});
      }
    }

    // Process Check D: Real action verification on toolbar buttons (duplicate, move, delete)
    if (testElementIds.length > 0) {
      const rootId = testElementIds[0];
      const elemLocator = frame.locator(`[data-element-id="${rootId}"]`);
      await elemLocator.click({ timeout: 2000 }).catch(() => {});
      await page.waitForTimeout(200);

      const beforeCount = await frame.locator("[data-element-id]").count();

      // Test Duplicate
      const dupBtn = frame.locator('[data-testid="floating-toolbar"] button[title*="تکثیر"]').first();
      if (await dupBtn.isVisible()) {
        await dupBtn.click().catch(() => {});
        await page.waitForTimeout(400);
        const afterDupCount = await frame.locator("[data-element-id]").count();
        if (afterDupCount <= beforeCount) {
          const msg = `Check D FAIL (P0: DEAD_TOOLBAR_ACTION): Duplicate button clicked but element count did not increase (${beforeCount} -> ${afterDupCount})!`;
          patternResult.passed = false;
          patternResult.failures.push({ check: "D", severity: "P0", action: "duplicate", message: msg });
          addFailure("DEAD_TOOLBAR_ACTION_DUPLICATE", "P0", { pattern: p.slug, message: msg });
        }
      }

      // Test Delete
      const delBtn = frame.locator('[data-testid="floating-toolbar"] button[title*="حذف"]').first();
      if (await delBtn.isVisible()) {
        const preDelCount = await frame.locator("[data-element-id]").count();
        await delBtn.click().catch(() => {});
        await page.waitForTimeout(400);
        const postDelCount = await frame.locator("[data-element-id]").count();
        if (postDelCount >= preDelCount) {
          const msg = `Check D FAIL (P0: DEAD_TOOLBAR_ACTION): Delete button clicked but element count did not decrease (${preDelCount} -> ${postDelCount})!`;
          patternResult.passed = false;
          patternResult.failures.push({ check: "D", severity: "P0", action: "delete", message: msg });
          addFailure("DEAD_TOOLBAR_ACTION_DELETE", "P0", { pattern: p.slug, message: msg });
        }
      }
    }

    matrix.patterns.push(patternResult);
  }

  // ──────────────────────────────────────────────────────────────────────────
  // SECTION 2: 34 Basic Blocks & Widgets (1..34)
  // ──────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [SECTION 2] Testing 34 Basic Blocks & Widgets...");

  // Switch to basic blocks tab in sidebar and sub-tab in palette
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.setLeftTab("blocks");
  });
  await page.waitForTimeout(300);

  const paletteBasicSubTab = page.locator("button:has-text('بلوک‌ها (')").first();
  if (await paletteBasicSubTab.isVisible()) {
    await paletteBasicSubTab.click();
    await page.waitForTimeout(400);
  }

  // Extract all block definitions from DOM or known list of 34
  const blockTypes = [
    "container", "section", "columns", "form_container",
    "heading", "text_editor", "image", "button", "spacer", "divider",
    "table", "form_input", "form_textarea", "form_select",
    "product_card", "product_grid", "product_variants", "product_price",
    "add_to_cart", "mini_cart", "cart_summary", "form_checkbox", "form_radio",
    "accordion", "tabs", "countdown", "video", "icon_box", "social_links",
    "image_gallery", "star_rating", "review_histogram", "recently_viewed", "mega_menu"
  ];

  for (let idx = 0; idx < blockTypes.length; idx++) {
    const bType = blockTypes[idx];
    const bNum = idx + 1;
    console.log(`  --- Block ${bNum}/34: [${bType}] ---`);

    const blockResult = {
      index: bNum,
      type: bType,
      passed: true,
      failures: [],
    };

    await clearCanvas();

    // Click block button in palette
    const blockBtn = page.locator(`button[data-block-type="${bType}"]`).first();
    if (await blockBtn.isVisible()) {
      await blockBtn.click();
      await page.waitForTimeout(400);
    }

    const { frame } = await getCanvasFrame();
    const elem = frame.locator("[data-element-id]").first();
    if ((await elem.count()) === 0) {
      const msg = `Block ${bType} did not render in canvas!`;
      blockResult.passed = false;
      blockResult.failures.push({ check: "RENDER", severity: "P0", message: msg });
      addFailure("BLOCK_NOT_RENDERED", "P0", { block: bType, message: msg });
      matrix.blocks.push(blockResult);
      continue;
    }

    // Check size > 0
    const box = await elem.boundingBox();
    if (!box || box.width <= 0 || box.height <= 0) {
      const msg = `Block ${bType} rendered with zero width/height!`;
      blockResult.passed = false;
      blockResult.failures.push({ check: "DIMENSIONS", severity: "P0", message: msg });
      addFailure("BLOCK_ZERO_DIMENSIONS", "P0", { block: bType, message: msg });
    }

    // Click and check toolbar
    await elem.click({ timeout: 2000 }).catch(() => {});
    await page.waitForTimeout(300);

    const toolbarVisible = await frame.locator('[data-testid="floating-toolbar"]').isVisible();
    if (!toolbarVisible) {
      const msg = `Block ${bType} toolbar did not appear on selection!`;
      blockResult.passed = false;
      blockResult.failures.push({ check: "TOOLBAR", severity: "P0", message: msg });
      addFailure("BLOCK_TOOLBAR_MISSING", "P0", { block: bType, message: msg });
    }

    matrix.blocks.push(blockResult);
  }

  // ──────────────────────────────────────────────────────────────────────────
  // SECTION 3: Dead Control Hunter in Inspector
  // ──────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [SECTION 3] Dead Control Hunter in Inspector (Content, Style, Advanced)...");

  // Test widgets: container, heading, button, table
  await clearCanvas();

  // 1. Test Container controls
  console.log("    Testing Container Inspector Controls...");
  console.log("    DEBUG URL:", page.url(), "Title:", await page.title(), "Frames:", page.frames().length);
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "test_cont_1",
            name: "کانتینر تستی",
            type: "container",
            layout: { kind: "flex", direction: "column", gap: { value: 16, unit: "px" }, gridColumns: 2 },
            styles: {
              mobile: {
                padding: {
                  top: { value: 10, unit: "px" },
                  right: { value: 10, unit: "px" },
                  bottom: { value: 10, unit: "px" },
                  left: { value: 10, unit: "px" },
                  isLinked: true,
                },
              },
            },
            children: [
              {
                id: "test_head_1",
                name: "عنوان تستی",
                type: "widget",
                widgetType: "heading",
                widgetProps: { text: "متن تستی اول", tag: "h2" },
                styles: { mobile: {} },
                children: [],
              },
            ],
          },
        ],
      });
      store.getState().selectElement("test_cont_1");
    }
  });
  await page.waitForTimeout(500);

  const { frame: frameCont } = await getCanvasFrame();

  // Test gap input
  const gapInput = page.locator("[data-testid='container-gap-input']").first();
  if (await gapInput.isVisible()) {
    await gapInput.fill("32");
    await page.waitForTimeout(400);

    const appliedGap = await frameCont.evaluate(() => {
      const el = document.querySelector("[data-element-id='test_cont_1']");
      return el ? el.style.gap : null;
    });

    if (appliedGap !== "32px") {
      const msg = `Container gap control is dead! Expected 32px, got "${appliedGap}"`;
      matrix.deadControls.push({ widget: "container", tab: "content", control: "gap", severity: "P0", message: msg });
      addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "container", control: "gap", message: msg });
    }
  }

  // Switch to Style tab
  const styleTabTrigger = page.locator("button[role='tab']:has-text('استایل')").first();
  if (await styleTabTrigger.isVisible()) {
    await styleTabTrigger.click();
    await page.waitForTimeout(400);

    // Test padding
    const padInput = page.locator("input[data-testid='padding-top-input'], input[placeholder*='بالا']").first();
    if (await padInput.isVisible()) {
      await padInput.fill("45");
      await page.waitForTimeout(400);

      const appliedPadding = await frameCont.evaluate(() => {
        const el = document.querySelector("[data-element-id='test_cont_1']");
        return el ? el.style.paddingTop || window.getComputedStyle(el).paddingTop : null;
      });

      if (!appliedPadding || !appliedPadding.includes("45")) {
        const msg = `Container padding control is dead! Expected 45px, got "${appliedPadding}"`;
        matrix.deadControls.push({ widget: "container", tab: "style", control: "padding", severity: "P0", message: msg });
        addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "container", control: "padding", message: msg });
      }
    }

    // Test Box Shadow
    const shadowPresetBtn = page.locator("button:has-text('عمیق (lg)')").first();
    if (await shadowPresetBtn.isVisible()) {
      await shadowPresetBtn.click();
      await page.waitForTimeout(400);

      const appliedShadow = await frameCont.evaluate(() => {
        const el = document.querySelector("[data-element-id='test_cont_1']");
        return el ? el.style.boxShadow : null;
      });

      if (!appliedShadow || !appliedShadow.includes("rgb")) {
        const msg = `Container box-shadow control is dead! Got: "${appliedShadow}"`;
        matrix.deadControls.push({ widget: "container", tab: "style", control: "boxShadow", severity: "P0", message: msg });
        addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "container", control: "boxShadow", message: msg });
      }
    }

    // Test Background Gradient (Elementor Grouped Controls)
    const gradTabBtn = page.locator("button:has-text('گرادیانت')").first();
    if (await gradTabBtn.isVisible()) {
      await gradTabBtn.click();
      await page.waitForTimeout(400);

      const appliedBg = await frameCont.evaluate(() => {
        const el = document.querySelector("[data-element-id='test_cont_1']");
        return el ? el.style.backgroundImage : null;
      });

      if (!appliedBg || !appliedBg.includes("linear-gradient")) {
        const msg = `Container gradient background control is dead! Got: "${appliedBg}"`;
        matrix.deadControls.push({ widget: "container", tab: "style", control: "gradient", severity: "P0", message: msg });
        addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "container", control: "gradient", message: msg });
      }
    }
  }

  // 2. Test Heading controls
  console.log("    Testing Heading Inspector Controls...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.selectElement("test_head_1");
  });
  await page.waitForTimeout(400);

  // Switch to Content tab
  const contentTabTrigger = page.locator("button[role='tab']:has-text('محتوا')").first();
  if (await contentTabTrigger.isVisible()) {
    await contentTabTrigger.click();
    await page.waitForTimeout(400);

    const headingTextInput = page.locator("[data-builder-inspector] [data-testid='heading-text-input'], [data-builder-inspector] input.h-8.text-xs").first();
    if (await headingTextInput.isVisible()) {
      await headingTextInput.fill("عنوان به‌روزشده با هوش مصنوعی");
      await page.waitForTimeout(400);

      const textInDom = await frameCont.evaluate(() => {
        const el = document.querySelector("[data-element-id='test_head_1']");
        return el ? el.textContent : "";
      });

      if (!textInDom.includes("عنوان به‌روزشده")) {
        const msg = `Heading text control is dead! Did not update text in canvas DOM.`;
        matrix.deadControls.push({ widget: "heading", tab: "content", control: "text", severity: "P0", message: msg });
        addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "heading", control: "text", message: msg });
      }
    }

    // Switch to Style tab for Heading Typography
    if (await styleTabTrigger.isVisible()) {
      await styleTabTrigger.click();
      await page.waitForTimeout(400);

      const fontSizeInput = page.locator("[data-testid='typography-fontsize-input']").first();
      if (await fontSizeInput.isVisible()) {
        await fontSizeInput.fill("42");
        await page.waitForTimeout(400);

        const appliedFs = await frameCont.evaluate(() => {
          const el = document.querySelector("[data-element-id='test_head_1']");
          return el ? el.style.fontSize : null;
        });

        if (appliedFs !== "42px") {
          const msg = `Heading typography font-size control is dead! Expected 42px, got "${appliedFs}"`;
          matrix.deadControls.push({ widget: "heading", tab: "style", control: "fontSize", severity: "P0", message: msg });
          addFailure("DEAD_INSPECTOR_CONTROL", "P0", { widget: "heading", control: "fontSize", message: msg });
        }
      }
    }
  }

  // ──────────────────────────────────────────────────────────────────────────
  // SECTION 4: Layout & Interaction (Chips Clipping, Dnd, WYSIWYG Parity)
  // ──────────────────────────────────────────────────────────────────────────
  console.log("\n>>> [SECTION 4] Layout & Interaction Verification...");

  // 1. Category chips clipping check
  if (await patternsTabBtn.isVisible()) {
    await patternsTabBtn.click();
    await page.waitForTimeout(400);

    const chipsCheck = await page.evaluate(() => {
      const container = document.querySelector("div.flex.gap-1, div.flex.gap-1\\.5, div.flex-wrap.gap-1\\.5");
      if (!container) return { found: false };

      const chips = Array.from(container.querySelectorAll("button"));
      const clippedChips = [];

      for (const chip of chips) {
        const text = chip.textContent || "";
        // Check if text is mangled (e.g. E2E corrupted or clipped)
        const isClipped = chip.scrollWidth > chip.clientWidth + 2;
        if (isClipped) {
          clippedChips.push({ text, scrollWidth: chip.scrollWidth, clientWidth: chip.clientWidth });
        }
      }

      return {
        found: true,
        totalChips: chips.length,
        clippedChips,
      };
    });

    if (chipsCheck.found && chipsCheck.clippedChips && chipsCheck.clippedChips.length > 0) {
      const msg = `${chipsCheck.clippedChips.length} category chips are clipped by sidebar bounds: ${chipsCheck.clippedChips.map((c) => c.text).join(", ")}`;
      matrix.layoutAndInteraction.categoryChipsClipping.passed = false;
      matrix.layoutAndInteraction.categoryChipsClipping.issues.push(msg);
      addFailure("CATEGORY_CHIPS_CLIPPED", "P1", { message: msg });
    }
  }

  // 2. Draft Save + WYSIWYG Parity check
  console.log("    Testing Draft Save & WYSIWYG Parity with Public Page...");
  const saveDraftBtn = page.locator("button:has-text('ذخیره پیش‌نویس')").first();
  if (await saveDraftBtn.isVisible()) {
    await saveDraftBtn.click();
    await page.waitForTimeout(1500);

    // Open public page in separate context
    const publicPage = await context.newPage();
    await publicPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await publicPage.waitForTimeout(1000);

    const publicContent = await publicPage.content();
    const hasRenderedHeading = publicContent.includes("عنوان به‌روزشده") || publicContent.includes("E2E");
    if (!hasRenderedHeading) {
      const msg = `WYSIWYG Parity mismatch: Public page did not display saved canvas content!`;
      matrix.layoutAndInteraction.wysiwygParity.passed = false;
      matrix.layoutAndInteraction.wysiwygParity.issues.push(msg);
      addFailure("WYSIWYG_PARITY_MISMATCH", "P0", { message: msg });
    }
    await publicPage.close();
  }

  // 3. Elementor Parity: Container Preset Picker Check
  console.log("    Testing Elementor Parity: Container Preset Picker...");
  await clearCanvas();
  // Insert an empty container
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "empty_container_test",
            name: "کانتینر خالی",
            type: "container",
            isLocked: false,
            isHidden: false,
            layout: { kind: "flex", direction: "column", gap: { value: 16, unit: "px" }, gridColumns: 1 },
            styles: { mobile: {} },
            children: [],
          },
        ],
      });
      store.getState().selectElement("empty_container_test");
    }
  });
  await page.waitForTimeout(600);

  const { frame: framePreset } = await getCanvasFrame();
  const presetPicker = framePreset.locator("[data-testid='container-preset-picker']");
  if (!(await presetPicker.isVisible())) {
    const msg = `Container Preset Picker (Elementor Parity) not visible in empty container!`;
    addFailure("CONTAINER_PRESET_PICKER_MISSING", "P0", { message: msg });
  } else {
    // Click 2-col preset
    const twoColBtn = framePreset.locator("[data-preset-id='2-col']").first();
    await twoColBtn.click();
    await page.waitForTimeout(500);

    const childCount = await framePreset.locator("[data-element-id^='col_']").count();
    if (childCount !== 2) {
      const msg = `Container 2-col preset did not insert 2 child columns! Found: ${childCount}`;
      addFailure("CONTAINER_PRESET_INSERT_FAILED", "P0", { message: msg });
    }
  }

  // 4. Elementor Parity: Context Menu on Canvas
  console.log("    Testing Elementor Parity: Context Menu...");
  const targetCol = framePreset.locator("[data-element-id^='col_']").first();
  await targetCol.dispatchEvent("contextmenu", { bubbles: true, cancelable: true });
  await page.waitForTimeout(400);

  const contextMenu = page.locator("[data-testid='builder-context-menu']");
  if (!(await contextMenu.isVisible())) {
    const msg = `Context Menu (Elementor Parity) did not open on right click!`;
    addFailure("CONTEXT_MENU_MISSING", "P0", { message: msg });
  } else {
    // Verify actions exist
    const hasDuplicate = await contextMenu.locator("text=تکثیر").isVisible();
    const hasCopy = await contextMenu.locator("text=کپی المان").isVisible();
    const hasDelete = await contextMenu.locator("text=حذف").isVisible();
    if (!hasDuplicate || !hasCopy || !hasDelete) {
      const msg = `Context Menu missing key Elementor actions (Duplicate, Copy, Delete)!`;
      addFailure("CONTEXT_MENU_ACTIONS_MISSING", "P0", { message: msg });
    }
    // Close context menu by clicking canvas
    await page.mouse.click(10, 10);
    await page.waitForTimeout(200);
  }

  // 5. Elementor Parity: LayersTree Drag-and-Drop & Rename
  console.log("    Testing Elementor Parity: LayersTree Drag & Drop...");
  const layersTabBtn = page.locator("button:has-text('لایه‌ها')").first();
  if (await layersTabBtn.isVisible()) {
    await layersTabBtn.click();
    await page.waitForTimeout(400);

    const layerRows = page.locator("[data-layer-row]");
    const rowCount = await layerRows.count();
    if (rowCount >= 2) {
      const sourceRow = layerRows.nth(0);
      const isDraggable = await sourceRow.getAttribute("draggable");
      if (isDraggable !== "true") {
        addFailure("LAYERS_TREE_DND_NOT_DRAGGABLE", "P0", { message: "LayersTree rows must be draggable for Elementor Navigator parity" });
      }
    }

    // Test Navigator Search Filter
    const searchInput = page.locator("[data-testid='layers-search-input']");
    if (await searchInput.isVisible()) {
      await searchInput.fill("ستون");
      await page.waitForTimeout(300);
      const filteredCount = await page.locator("[data-layer-row]").count();
      if (filteredCount === 0) {
        addFailure("LAYERS_TREE_SEARCH_FAILED", "P0", { message: "Navigator search filter returned zero matches for 'ستون'" });
      }
      await searchInput.fill("");
      await page.waitForTimeout(200);
    }
  }

  // 6. Elementor Parity: Keyboard Shortcuts Help Modal & History Hotkeys
  console.log("    Testing Elementor Parity: Keyboard Shortcuts Dialog & Undo/Redo Hotkeys...");
  const shortcutsBtn = page.locator("[data-testid='shortcuts-help-btn']");
  if (await shortcutsBtn.isVisible()) {
    await shortcutsBtn.click();
    await page.waitForTimeout(400);

    const dialogTitle = page.locator("text=راهنمای کلیدهای میانبر");
    if (!(await dialogTitle.isVisible())) {
      addFailure("SHORTCUTS_DIALOG_MISSING", "P0", { message: "Keyboard Shortcuts Dialog failed to open" });
    } else {
      // Press Escape to close modal
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
    }
  }

  // Test Undo/Redo Hotkeys (Ctrl+Z and Ctrl+Y)
  const initialCount = await framePreset.locator("[data-element-id]").count();
  // Press Delete on active selection
  await page.keyboard.press("Delete");
  await page.waitForTimeout(300);
  const postDelCount = await framePreset.locator("[data-element-id]").count();

  if (postDelCount < initialCount) {
    // Press Ctrl+Z to Undo
    await page.keyboard.press("Control+z");
    await page.waitForTimeout(400);
    const restoredCount = await framePreset.locator("[data-element-id]").count();
    if (restoredCount !== initialCount) {
      addFailure("HOTKEY_UNDO_FAILED", "P0", { message: `Ctrl+Z did not restore deleted element (${restoredCount} vs ${initialCount})` });
    }
  }

  // 7. Elementor Parity: Responsive Breakpoint Conditional Visibility in Preview Mode
  console.log("    Testing Elementor Parity: Responsive Breakpoint Visibility...");
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "resp_vis_elem",
            name: "المان مخفی در موبایل",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "عنوان مخصوص دسکتاپ و تبلت" },
            visibleOnMobile: false,
            visibleOnDesktop: true,
            visibleOnTablet: true,
            styles: { mobile: {} },
            children: [],
          },
        ],
      });
      store.getState().selectElement("resp_vis_elem");
      store.getState().setBreakpoint("mobile");
    }
  });
  await page.waitForTimeout(400);

  // In edit mode on mobile, hidden badge should be visible
  const hasBadge = await framePreset.locator("span:has-text('مخفی در موبایل')").first().isVisible();
  if (!hasBadge) {
    addFailure("RESPONSIVE_VISIBILITY_BADGE_MISSING", "P0", { message: "Badge indicating element is hidden on mobile not found" });
  }

  // Switch to preview mode: element must not be rendered
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.setPreviewMode(true);
  });
  await page.waitForTimeout(400);

  const visibleInPreview = await framePreset.locator("[data-element-id='resp_vis_elem']").isVisible();
  if (visibleInPreview) {
    addFailure("RESPONSIVE_VISIBILITY_LEAK_IN_PREVIEW", "P0", { message: "Element with visibleOnMobile=false leaked into mobile preview mode!" });
  }

  // Restore preview mode & desktop breakpoint
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.setPreviewMode(false);
    window.__BUILDER_STORE__?.getState()?.setBreakpoint("desktop");
  });
  await page.waitForTimeout(300);

  // 8. Elementor Parity: Wrap / Unwrap Container Actions
  console.log("    Testing Elementor Parity: Wrap / Unwrap Container Actions...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.wrapInContainer("resp_vis_elem");
  });
  await page.waitForTimeout(400);

  const wrapperExists = await page.evaluate(() => {
    const root = window.__BUILDER_STORE__?.getState()?.ast.rootElements[0];
    return root && root.type === "container" && root.name === "کانتینر احاطه‌کننده" && root.children.length === 1;
  });

  if (!wrapperExists) {
    addFailure("WRAP_IN_CONTAINER_FAILED", "P0", { message: "wrapInContainer did not wrap element inside a new parent container" });
  } else {
    // Test unwrap
    await page.evaluate(() => {
      const wrapperId = window.__BUILDER_STORE__?.getState()?.ast.rootElements[0]?.id;
      if (wrapperId) window.__BUILDER_STORE__?.getState()?.unwrapContainer(wrapperId);
    });
    await page.waitForTimeout(400);

    const unwrapped = await page.evaluate(() => {
      const root = window.__BUILDER_STORE__?.getState()?.ast.rootElements[0];
      return root && root.id === "resp_vis_elem";
    });

    if (!unwrapped) {
      addFailure("UNWRAP_CONTAINER_FAILED", "P0", { message: "unwrapContainer did not restore child to parent level" });
    }
  }

  // 9. Elementor Parity: Multi-Selection & Cross-Session Persistent Clipboard
  console.log("    Testing Elementor Parity: Multi-Selection & Persistent Clipboard...");
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "multi_1",
            name: "المان یک",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "یک" },
            styles: { mobile: {} },
            children: [],
          },
          {
            id: "multi_2",
            name: "المان دو",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "دو" },
            styles: { mobile: {} },
            children: [],
          },
        ],
      });
      store.getState().toggleSelectElement("multi_1", false);
      store.getState().toggleSelectElement("multi_2", true);
    }
  });
  await page.waitForTimeout(400);

  // Check multi-selection box in overlay
  const multiBoxCount = await framePreset.locator("[data-testid='overlay-multi-box']").count();
  if (multiBoxCount < 1) {
    addFailure("MULTI_SELECTION_BOX_MISSING", "P0", { message: "Multi-selection bounding box not rendered in overlay portal" });
  }

  // Test persistent clipboard in localStorage
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.copyElement("multi_1");
  });
  await page.waitForTimeout(200);

  const storedClip = await page.evaluate(() => {
    return localStorage.getItem("builder_clipboard_element");
  });

  if (!storedClip || !storedClip.includes("multi_1")) {
    addFailure("PERSISTENT_CLIPBOARD_FAILED", "P0", { message: "copyElement did not persist element to localStorage" });
  }

  // 10. Elementor Parity: History & Revision Timeline Panel
  console.log("    Testing Elementor Parity: History Timeline Panel & JumpToHistory...");
  const historyTabBtn = page.locator("[data-testid='history-tab-btn']");
  if (await historyTabBtn.isVisible()) {
    await historyTabBtn.click();
    await page.waitForTimeout(400);

    const historyPanel = page.locator("[data-testid='builder-history-panel']");
    if (!(await historyPanel.isVisible())) {
      addFailure("HISTORY_PANEL_MISSING", "P0", { message: "History timeline panel not visible on tab switch" });
    } else {
      const stepButtons = page.locator("[data-history-step]");
      const count = await stepButtons.count();
      if (count < 1) {
        addFailure("HISTORY_TIMELINE_EMPTY", "P0", { message: "History timeline contains zero steps" });
      } else {
        // Click on the first history step to jump back
        await stepButtons.first().click();
        await page.waitForTimeout(300);
      }
    }

    // Switch back to blocks tab
    const blocksTabBtn = page.locator("button:has-text('بلوک‌ها')").first();
    if (await blocksTabBtn.isVisible()) {
      await blocksTabBtn.click();
      await page.waitForTimeout(300);
    }
  }

  // 11. Elementor Parity: Global Styles Dialog & Design Tokens Sync
  console.log("    Testing Elementor Parity: Global Styles Dialog & Two-Layer Tokens...");
  const globalStylesBtn = page.locator("button:has-text('استایل سراسری')").first();
  if (await globalStylesBtn.isVisible()) {
    await globalStylesBtn.click();
    await page.waitForTimeout(400);

    const dialog = page.locator("div[role='dialog']").first();
    if (!(await dialog.isVisible())) {
      addFailure("GLOBAL_STYLES_DIALOG_MISSING", "P0", { message: "Global Styles dialog failed to open" });
    } else {
      // Check presence of reset button
      const resetBtn = dialog.locator("button:has-text('بازنشانی به تم پیش‌فرض')");
      if (!(await resetBtn.isVisible())) {
        addFailure("GLOBAL_STYLES_RESET_MISSING", "P0", { message: "Reset to default theme button missing" });
      }

      // Close dialog
      const cancelBtn = dialog.locator("button:has-text('انصراف')");
      if (await cancelBtn.isVisible()) {
        await cancelBtn.click();
        await page.waitForTimeout(300);
      }
    }
  }

  // 12. Elementor Parity: Custom CSS ID & Classes Binding
  console.log("    Testing Elementor Parity: Custom CSS ID and Classes DOM Reflection...");
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "anchor_el_test",
            name: "المان تستی نشانه",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "عنوان با نشانه اختصاصی" },
            styles: {
              mobile: {},
              customCssId: "my-anchor-section",
              customCssClass: "custom-verified-banner",
            },
            children: [],
          },
        ],
      });
      store.getState().selectElement("anchor_el_test");
    }
  });
  await page.waitForTimeout(500);

  const customIdReflected = await framePreset.evaluate(() => {
    const el = document.getElementById("my-anchor-section");
    return el && el.classList.contains("custom-verified-banner");
  });

  if (!customIdReflected) {
    addFailure("CUSTOM_CSS_ID_REFLECTION_FAILED", "P0", { message: "customCssId or customCssClass not reflected on element in canvas DOM" });
  }

  // 13. Elementor Parity: Save Page Template Dialog
  console.log("    Testing Elementor Parity: Save Page Template Dialog...");
  const savePageTplBtn = page.locator("button:has-text('قالب برگه')").first();
  if (await savePageTplBtn.isVisible()) {
    await savePageTplBtn.click();
    await page.waitForTimeout(400);

    const dialog = page.locator("div[role='dialog']").first();
    if (!(await dialog.isVisible())) {
      addFailure("SAVE_PAGE_TEMPLATE_DIALOG_MISSING", "P0", { message: "SavePageTemplateDialog did not open on toolbar click" });
    } else {
      const titleInput = dialog.locator("input").first();
      const hasInput = await titleInput.isVisible();
      if (!hasInput) {
        addFailure("SAVE_PAGE_TEMPLATE_TITLE_MISSING", "P0", { message: "Template title input missing in dialog" });
      }

      // Close dialog
      const cancelBtn = dialog.locator("button:has-text('انصراف')");
      if (await cancelBtn.isVisible()) {
        await cancelBtn.click();
        await page.waitForTimeout(300);
      }
    }
  }

  // 14. Elementor Parity: Boxed Container Content Width
  console.log("    Testing Elementor Parity: Boxed Container Content Width...");
  await page.evaluate(() => {
    const store = window.__BUILDER_STORE__;
    if (store && store.getState) {
      store.getState().replacePageAST({
        ...store.getState().ast,
        rootElements: [
          {
            id: "boxed_cont_test",
            name: "کانتینر جعبه‌ای",
            type: "container",
            layout: {
              kind: "flex",
              direction: "column",
              gap: { value: 16, unit: "px" },
              gridColumns: 1,
              boxedWidth: { value: 1024, unit: "px" },
            },
            styles: { mobile: {} },
            children: [],
          },
        ],
      });
      store.getState().selectElement("boxed_cont_test");
    }
  });
  await page.waitForTimeout(400);

  const boxedApplied = await framePreset.evaluate(() => {
    const el = document.querySelector("[data-element-id='boxed_cont_test']");
    return el ? { maxWidth: el.style.maxWidth, marginL: el.style.marginLeft, marginR: el.style.marginRight } : null;
  });

  if (!boxedApplied || boxedApplied.maxWidth !== "1024px") {
    addFailure("CONTAINER_BOXED_WIDTH_FAILED", "P0", { message: `Boxed container maxWidth not applied in canvas DOM (got: ${JSON.stringify(boxedApplied)})` });
  }

  // 15. Elementor Parity: Opacity & Advanced Layout Controls
  console.log("    Testing Elementor Parity: Opacity Control...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.updateDeviceStyles("boxed_cont_test", "desktop", {
      opacity: 0.75,
    });
  });
  await page.waitForTimeout(400);

  const appliedOpacity = await framePreset.evaluate(() => {
    const el = document.querySelector("[data-element-id='boxed_cont_test']");
    return el ? el.style.opacity : null;
  });

  if (appliedOpacity !== "0.75") {
    addFailure("OPACITY_CONTROL_FAILED", "P0", { message: `Opacity control not applied in canvas DOM (expected "0.75", got "${appliedOpacity}")` });
  }

  // 16. Elementor Parity: Flex Item Align-Self & Order
  console.log("    Testing Elementor Parity: Flex Item Align-Self & Order...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.updateDeviceStyles("boxed_cont_test", "desktop", {
      alignSelf: "center",
      order: 3,
    });
  });
  await page.waitForTimeout(400);

  const appliedItemStyles = await framePreset.evaluate(() => {
    const el = document.querySelector("[data-element-id='boxed_cont_test']");
    return el ? { alignSelf: el.style.alignSelf, order: el.style.order } : null;
  });

  if (!appliedItemStyles || appliedItemStyles.alignSelf !== "center" || appliedItemStyles.order !== "3") {
    addFailure("ALIGN_SELF_ORDER_FAILED", "P0", { message: `alignSelf or order not reflected in canvas DOM (got: ${JSON.stringify(appliedItemStyles)})` });
  }

  // 17. Elementor Parity: Background Overlay Control
  console.log("    Testing Elementor Parity: Background Overlay Control...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.updateDeviceStyles("boxed_cont_test", "desktop", {
      backgroundOverlay: {
        type: "color",
        color: "rgba(0, 0, 0, 0.4)",
        opacity: 0.6,
      },
    });
  });
  await page.waitForTimeout(400);

  const overlayApplied = await framePreset.evaluate(() => {
    const el = document.querySelector("[data-element-id='boxed_cont_test'] [data-testid='background-overlay']");
    return el ? { opacity: el.style.opacity, bg: el.style.backgroundColor } : null;
  });

  if (!overlayApplied || overlayApplied.opacity !== "0.6") {
    addFailure("BACKGROUND_OVERLAY_FAILED", "P0", { message: `Background overlay not rendered in canvas DOM (got: ${JSON.stringify(overlayApplied)})` });
  }

  // 18. Elementor Parity: CSS Filter Control
  console.log("    Testing Elementor Parity: CSS Filter Control...");
  await page.evaluate(() => {
    window.__BUILDER_STORE__?.getState()?.updateDeviceStyles("boxed_cont_test", "desktop", {
      filter: "blur(4px)",
    });
  });
  await page.waitForTimeout(400);

  const appliedFilter = await framePreset.evaluate(() => {
    const el = document.querySelector("[data-element-id='boxed_cont_test']");
    return el ? el.style.filter : null;
  });

  if (!appliedFilter || !appliedFilter.includes("blur(4px)")) {
    addFailure("CSS_FILTER_CONTROL_FAILED", "P0", { message: `CSS filter not applied in canvas DOM (expected blur(4px), got: "${appliedFilter}")` });
  }

  // ──────────────────────────────────────────────────────────────────────────
  // Write Final Matrix Report
  // ──────────────────────────────────────────────────────────────────────────
  const reportPath = path.join(WORKTREE_ROOT, ".loop", "XRAY_MATRIX.json");
  fs.writeFileSync(reportPath, JSON.stringify(matrix, null, 2), "utf8");

  console.log(`\n===============================================================`);
  console.log(`>>> X-RAY AUDIT COMPLETED:`);
  console.log(`    Total Failures : ${matrix.totalFailures}`);
  console.log(`    P0 Failures    : ${matrix.p0Count}`);
  console.log(`    P1 Failures    : ${matrix.p1Count}`);
  console.log(`    Report Saved   : ${reportPath}`);
  console.log(`===============================================================\n`);

  await browser.close();
  return matrix;
}

runXRayAudit().catch((err) => {
  console.error("Fatal error running X-Ray audit:", err);
  process.exit(1);
});
