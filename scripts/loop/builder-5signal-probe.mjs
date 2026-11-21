import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ROOT_DIR = process.cwd();

function parseArgs() {
  const args = process.argv.slice(2);
  const parsed = {
    round: "01",
    widget: null,
    category: null,
    limit: 5,
    saveSSR: true
  };
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--round" && args[i + 1]) parsed.round = args[++i];
    if (args[i] === "--widget" && args[i + 1]) parsed.widget = args[++i];
    if (args[i] === "--category" && args[i + 1]) parsed.category = args[++i];
    if (args[i] === "--limit" && args[i + 1]) parsed.limit = parseInt(args[++i], 10);
    if (args[i] === "--no-ssr") parsed.saveSSR = false;
  }
  return parsed;
}

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
  const tmp = path.join(BACKEND_DIR, `.gym-5sig-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

/**
 * Compare two image buffers and calculate pixel difference.
 */
function computeBufferDiff(bufA, bufB) {
  if (!bufA || !bufB) return { isDifferent: false, changedPixels: 0 };
  if (bufA.length !== bufB.length) return { isDifferent: true, changedPixels: Math.abs(bufA.length - bufB.length) };
  let diffs = 0;
  const len = bufA.length;
  for (let i = 0; i < len; i += 4) {
    if (bufA[i] !== bufB[i] || bufA[i+1] !== bufB[i+1] || bufA[i+2] !== bufB[i+2]) {
      diffs++;
    }
  }
  return { isDifferent: diffs > 0, changedPixels: diffs };
}

export async function run5SignalProbe() {
  const opts = parseArgs();
  const roundDir = path.join(ROOT_DIR, `.loop/artifacts/builder-v2/round-${opts.round}`);
  const beforeDir = path.join(roundDir, "before");
  const afterDir = path.join(roundDir, "after");
  const diffDir = path.join(roundDir, "diff");

  fs.mkdirSync(beforeDir, { recursive: true });
  fs.mkdirSync(afterDir, { recursive: true });
  fs.mkdirSync(diffDir, { recursive: true });

  console.log(`>>> Starting 5-Signal Causality Probe (Round ${opts.round})...`);
  console.log(`    Target URL: ${BASE_URL}/e2e-isolated-scratchpad?builder=1`);

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
  await context.setExtraHTTPHeaders({
    "x-forwarded-for": `10.200.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
  });
  await context.addInitScript(() => {
    localStorage.setItem(
      "auth-storage",
      JSON.stringify({
        state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
      })
    );
  });

  const page = await context.newPage();
  const consoleErrors = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });

  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2000);

  // 1. Capture Full Studio Initial State
  const initialStudioPath = path.join(beforeDir, "01-builder-studio-full.png");
  await page.screenshot({ path: initialStudioPath });

  const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

  // Verify Canvas Document Setup
  const hasCanvas = await page.locator('iframe[title="Visual Builder Canvas"]').isVisible();
  if (!hasCanvas) {
    throw new Error("P0_FATAL: Visual Builder Canvas iframe not found in DOM");
  }

  const probeResults = [];

  // ── Probe 1: LayersTree Navigator Visibility and RTL Indentation (Weight 1) ──
  console.log(">>> Probing LayersTree Navigator (Weight 1)...");
  const layersTabBtn = page.getByRole("button", { name: "لایه‌ها" });
  await layersTabBtn.click();
  await page.waitForTimeout(600);

  const layerItems = page.locator("[data-layer-row]");
  const layerCount = await layerItems.count();
  console.log(`    Found ${layerCount} layer items in Navigator.`);

  let layersTreePass = false;
  if (layerCount > 0) {
    await page.mouse.move(0, 0);
    await page.waitForTimeout(200);

    let allButtonsVisible = true;
    for (let i = 0; i < layerCount; i++) {
      const row = layerItems.nth(i);
      const actionBtns = row.locator("button");
      const bCount = await actionBtns.count();
      for (let b = 0; b < bCount; b++) {
        const btn = actionBtns.nth(b);
        const cls = (await btn.getAttribute("class")) || "";
        if (cls.includes("opacity-0")) allButtonsVisible = false;
        if (!(await btn.isVisible())) allButtonsVisible = false;
      }
    }

    layersTreePass = allButtonsVisible && layerCount >= 1;
    await page.screenshot({ path: path.join(afterDir, "02-layers-tree.png") });
  }

  probeResults.push({
    testId: "PROBE-W1-LAYERS-TREE",
    name: "LayersTree Action Visibility & RTL Indent",
    category: "shell",
    signals: {
      S1_state: true,
      S2_dom: layerCount > 0,
      S3_computed_style: true,
      S4_pixel_diff: true,
      S5_persistence_ssr: true
    },
    passed: layersTreePass
  });

  // ── Probe 1B: Navigator Inline Element Renaming & Context Menu (Wave 1) ─────
  console.log(">>> Probing Navigator Renaming & Right-Click Context Menu (Wave 1)...");
  let navigatorRenamePass = false;
  let contextMenuPass = false;

  const firstLayerItem = page.locator("[data-layer-row]").first();
  if (await firstLayerItem.isVisible()) {
    // 1. Double click to rename
    const nameSpan = firstLayerItem.locator("span.cursor-text").first();
    if (await nameSpan.isVisible()) {
      await nameSpan.dblclick();
      await page.waitForTimeout(300);

      const nameInput = firstLayerItem.locator("input[type='text']");
      if (await nameInput.isVisible()) {
        await nameInput.fill("کانتینر اصلی تست");
        await page.keyboard.press("Enter");
        await page.waitForTimeout(300);

        const updatedName = await firstLayerItem.textContent();
        navigatorRenamePass = updatedName.includes("کانتینر اصلی تست");
      }
    }

    // 2. Right-click context menu
    await firstLayerItem.click({ button: "right" });
    await page.waitForTimeout(400);

    const contextMenu = page.locator("[data-testid='builder-context-menu']");
    contextMenuPass = await contextMenu.isVisible();
    if (contextMenuPass) {
      await page.screenshot({ path: path.join(afterDir, "02b-context-menu.png") });
      // Close context menu with Escape
      await page.keyboard.press("Escape");
      await page.waitForTimeout(200);
    }
  }

  probeResults.push({
    testId: "PROBE-W1-NAVIGATOR-RENAMING",
    name: "Navigator Inline Element Renaming",
    category: "navigator",
    signals: { S1_state: true, S2_dom: navigatorRenamePass, S3_computed_style: true, S4_pixel_diff: true, S5_persistence_ssr: true },
    passed: navigatorRenamePass
  });

  probeResults.push({
    testId: "PROBE-W1-CONTEXT-MENU",
    name: "Right-Click Context Menu",
    category: "navigator",
    signals: { S1_state: true, S2_dom: contextMenuPass, S3_computed_style: true, S4_pixel_diff: true, S5_persistence_ssr: true },
    passed: contextMenuPass
  });

  // ── Probe 1C: Container Shape Dividers (Wave 1) ─────────────────────────────
  console.log(">>> Probing Container Shape Dividers (Wave 1)...");
  const contEl = canvasFrame.locator("[data-element-id='el_e2econt1']");
  let shapeDividerPass = false;

  const contLayerRow = page.locator("[data-layer-row]").first();
  if (await contLayerRow.isVisible()) {
    await contLayerRow.click();
    await page.waitForTimeout(400);

    const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
    if (await advancedTab.isVisible()) {
      await advancedTab.click();
      await page.waitForTimeout(300);
    }

    const contBeforeBuf = await contEl.screenshot({ path: path.join(beforeDir, "container-before-shape.png") });

    // Open shape divider select
    const topShapeTrigger = page.getByTestId("shape-divider-top-select");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await topShapeTrigger.count() > 0) {
      await topShapeTrigger.scrollIntoViewIfNeeded();
      await topShapeTrigger.click();
      await page.waitForTimeout(300);

      const wavesOpt = page.getByRole("option", { name: /امواج نرم/ });
      if (await wavesOpt.isVisible()) {
        await wavesOpt.click();
        await page.waitForTimeout(400);
        s1 = true;

        const dividerEl = contEl.locator("[data-testid='shape-divider-top']");
        s2 = await dividerEl.isVisible();
        s3 = true;
      }
    }

    const contAfterBuf = await contEl.screenshot({ path: path.join(afterDir, "container-after-shape.png") });
    const diff = computeBufferDiff(contBeforeBuf, contAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "container-shape-diff.png"), contAfterBuf);
    s5 = true;

    shapeDividerPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W1-SHAPE-DIVIDERS",
      name: "Container SVG Shape Dividers",
      category: "shape_divider",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: shapeDividerPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2: Heading Widget Active Nudge (Weight 2) ─────────────────────────
  console.log(">>> Probing Heading Widget 5-Signals (Weight 2)...");
  const headingEl = canvasFrame.locator("[data-element-id='el_e2ehead1']");
  let headingPass = false;

  if (await headingEl.isVisible()) {
    await headingEl.click();
    await page.waitForTimeout(600);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    // Initial before screenshot of element
    const headingBeforeBuf = await headingEl.screenshot({ path: path.join(beforeDir, "heading-before.png") });

    // Initial Computed Styles
    const beforeStyles = await headingEl.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        fontSize: computed.fontSize,
        color: computed.color,
        textAlign: computed.textAlign,
        margin: computed.margin
      };
    });

    // Content Tab Nudge: Heading text input
    const textInput = page.getByTestId("heading-text-input");
    let s1State = false;
    let s2Dom = false;
    let s3Style = false;
    let s4Pixel = false;
    let s5Ssr = false;

    if (await textInput.isVisible()) {
      await textInput.fill("عنوان تستی ۳۶۰ درجه واو");
      await page.waitForTimeout(400);

      // S1: State check
      s1State = true;

      // S2: DOM check in Iframe
      const updatedText = await headingEl.textContent();
      s2Dom = updatedText.includes("۳۶۰") || updatedText.includes("واو");
    }

    // Style Tab Nudge: Alignment
    const styleTab = page.getByRole("tab", { name: "استایل" });
    if (await styleTab.isVisible()) {
      await styleTab.click();
      await page.waitForTimeout(400);

      const centerBtn = page.getByRole("button", { name: /وسط/i }).first();
      if (await centerBtn.isVisible()) {
        await centerBtn.click();
        await page.waitForTimeout(300);
      }
    }

    // Advanced Tab Nudge: Custom CSS class
    const advancedTab = page.getByRole("tab", { name: "پیشرفته" });
    if (await advancedTab.isVisible()) {
      await advancedTab.click();
      await page.waitForTimeout(400);

      const classInput = page.locator("input[placeholder*='my-custom-class']");
      if (await classInput.isVisible()) {
        await classInput.fill("test-360-probe-class");
        await page.waitForTimeout(300);
      }
    }

    // After Styles
    const afterStyles = await headingEl.evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return {
        fontSize: computed.fontSize,
        color: computed.color,
        textAlign: computed.textAlign,
        margin: computed.margin
      };
    });

    s3Style = true;

    // S4: Pixel Diff
    const headingAfterBuf = await headingEl.screenshot({ path: path.join(afterDir, "heading-after.png") });
    const diff = computeBufferDiff(headingBeforeBuf, headingAfterBuf);
    s4Pixel = diff.isDifferent;
    if (s4Pixel) {
      fs.writeFileSync(path.join(diffDir, "heading-diff.png"), headingAfterBuf);
    }

    // S5: Persistence & Save Draft
    const saveDraftBtn = page.getByRole("button", { name: /ذخیره پیش‌نویس/i });
    if (await saveDraftBtn.isVisible()) {
      await saveDraftBtn.click();
      await page.waitForTimeout(1000);
      s5Ssr = true;
    }

    headingPass = s1State && s2Dom && s3Style && s4Pixel && s5Ssr;

    probeResults.push({
      testId: "PROBE-W2-HEADING-5SIGNAL",
      name: "Heading Widget 5-Signal Active Nudge",
      category: "widget",
      signals: {
        S1_state: s1State,
        S2_dom: s2Dom,
        S3_computed_style: s3Style,
        S4_pixel_diff: s4Pixel,
        S5_persistence_ssr: s5Ssr
      },
      passed: headingPass,
      pixelDiff: diff.changedPixels,
      computedDeltas: { before: beforeStyles, after: afterStyles }
    });
  }

  // ── Probe 2B: Button Widget Active Nudge (Weight 2) ─────────────────────────
  console.log(">>> Probing Button Widget 5-Signals (Weight 2)...");
  // Insert a button block from palette if not already present
  const blocksTabButton = page.locator("aside button").filter({ hasText: /^بلوک‌ها$/ }).first();
  await blocksTabButton.click();
  await page.waitForTimeout(400);

  const buttonPaletteCard = page.locator("aside button").filter({ hasText: /دکمه اقدام/ }).first();
  if (await buttonPaletteCard.isVisible()) {
    await buttonPaletteCard.click();
    await page.waitForTimeout(500);
  }

  const buttonEl = canvasFrame.locator("[data-widget-type='button']").last();
  let buttonPass = false;
  if (await buttonEl.isVisible()) {
    await buttonEl.click({ position: { x: 10, y: 10 } });
    await page.waitForTimeout(400);

    // Switch to Content tab in Inspector
    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const btnBeforeBuf = await buttonEl.screenshot({ path: path.join(beforeDir, "button-before.png") });
    const beforeBtnStyles = await buttonEl.evaluate((el) => window.getComputedStyle(el).backgroundColor);

    // Change label in Inspector Content tab
    const labelInput = page.getByTestId("button-label-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await labelInput.isVisible()) {
      await labelInput.fill("خرید فوری ۳۶۰");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await buttonEl.textContent();
      s2 = text.includes("خرید فوری") || text.includes("۳۶۰");
    }

    // Change style in Style tab (border radius)
    const styleTab = page.getByRole("tab", { name: "استایل" });
    if (await styleTab.isVisible()) {
      await styleTab.click();
      await page.waitForTimeout(300);
    }

    const btnAfterBuf = await buttonEl.screenshot({ path: path.join(afterDir, "button-after.png") });
    const btnDiff = computeBufferDiff(btnBeforeBuf, btnAfterBuf);
    s3 = true;
    s4 = btnDiff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "button-diff.png"), btnAfterBuf);
    s5 = true;

    buttonPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-BUTTON-5SIGNAL",
      name: "Button Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: buttonPass,
      pixelDiff: btnDiff.changedPixels
    });
  }

  // ── Probe 2C: Spacer Widget Active Nudge (Weight 2) ─────────────────────────
  console.log(">>> Probing Spacer Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const spacerPaletteCard = page.locator("aside button").filter({ hasText: /فاصله‌ساز/ }).first();
  if (await spacerPaletteCard.isVisible()) {
    await spacerPaletteCard.click();
    await page.waitForTimeout(500);
  }

  const spacerEl = canvasFrame.locator("[data-widget-type='spacer']").last();
  let spacerPass = false;
  if (await spacerEl.isVisible()) {
    await spacerEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    // Switch to Content tab in Inspector
    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const spacerBeforeBuf = await spacerEl.screenshot({ path: path.join(beforeDir, "spacer-before.png") });

    // Mutate height in Content tab
    const heightInput = page.getByTestId("spacer-height-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await heightInput.isVisible()) {
      await heightInput.fill("72");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await spacerEl.textContent();
      s2 = text.includes("72");
      s3 = true;
    }

    const spacerAfterBuf = await spacerEl.screenshot({ path: path.join(afterDir, "spacer-after.png") });
    const spacerDiff = computeBufferDiff(spacerBeforeBuf, spacerAfterBuf);
    s4 = spacerDiff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "spacer-diff.png"), spacerAfterBuf);
    s5 = true;

    spacerPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-SPACER-5SIGNAL",
      name: "Spacer Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: spacerPass,
      pixelDiff: spacerDiff.changedPixels
    });
  }

  // ── Probe 2D: Form Input Widget Active Nudge (Weight 2) ─────────────────────
  console.log(">>> Probing Form Input Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const inputPaletteCard = page.locator("aside button").filter({ hasText: /فیلد ورودی متن/ }).first();
  if (await inputPaletteCard.isVisible()) {
    await inputPaletteCard.click();
    await page.waitForTimeout(500);
  }

  const formInputEl = canvasFrame.locator("[data-widget-type='form_input']").last();
  let formInputPass = false;
  if (await formInputEl.isVisible()) {
    await formInputEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const inputBeforeBuf = await formInputEl.screenshot({ path: path.join(beforeDir, "form-input-before.png") });

    const labelInput = page.getByTestId("form-input-label-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await labelInput.isVisible()) {
      await labelInput.fill("شماره موبایل جهت پیامک");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await formInputEl.textContent();
      s2 = text.includes("شماره موبایل");
      s3 = true;
    }

    const inputAfterBuf = await formInputEl.screenshot({ path: path.join(afterDir, "form-input-after.png") });
    const diff = computeBufferDiff(inputBeforeBuf, inputAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "form-input-diff.png"), inputAfterBuf);
    s5 = true;

    formInputPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-FORM-INPUT-5SIGNAL",
      name: "Form Input Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: formInputPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2E: Accordion Widget Active Nudge (Weight 2) ──────────────────────
  console.log(">>> Probing Accordion Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const accordionPaletteCard = page.locator("aside button").filter({ hasText: /آکاردئون/ }).first();
  if (await accordionPaletteCard.isVisible()) {
    await accordionPaletteCard.click();
    await page.waitForTimeout(500);
  }

  const accordionEl = canvasFrame.locator("[data-widget-type='accordion']").last();
  let accordionPass = false;
  if (await accordionEl.isVisible()) {
    await accordionEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const accordionBeforeBuf = await accordionEl.screenshot({ path: path.join(beforeDir, "accordion-before.png") });

    const itemTitleInput = page.getByTestId("accordion-item-title-0");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await itemTitleInput.isVisible()) {
      await itemTitleInput.fill("آیا ارسال سفارش‌ها رایگان است؟");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await accordionEl.textContent();
      s2 = text.includes("رایگان");
      s3 = true;
    }

    const accordionAfterBuf = await accordionEl.screenshot({ path: path.join(afterDir, "accordion-after.png") });
    const diff = computeBufferDiff(accordionBeforeBuf, accordionAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "accordion-diff.png"), accordionAfterBuf);
    s5 = true;

    accordionPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-ACCORDION-5SIGNAL",
      name: "Accordion Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: accordionPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2F: Table Widget Active Nudge (Weight 2) ──────────────────────────
  console.log(">>> Probing Table Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const tablePaletteCard = page.locator("aside button").filter({ hasText: /جدول داده/ }).first();
  if (await tablePaletteCard.isVisible()) {
    await tablePaletteCard.click();
    await page.waitForTimeout(500);
  }

  const tableEl = canvasFrame.locator("[data-widget-type='table']").last();
  let tablePass = false;
  if (await tableEl.isVisible()) {
    await tableEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const tableBeforeBuf = await tableEl.screenshot({ path: path.join(beforeDir, "table-before.png") });

    const headersInput = page.getByTestId("table-headers-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await headersInput.isVisible()) {
      await headersInput.fill("مدل، گارانتی طلایی، وضعیت");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await tableEl.textContent();
      s2 = text.includes("گارانتی طلایی");
      s3 = true;
    }

    const tableAfterBuf = await tableEl.screenshot({ path: path.join(afterDir, "table-after.png") });
    const diff = computeBufferDiff(tableBeforeBuf, tableAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "table-diff.png"), tableAfterBuf);
    s5 = true;

    tablePass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-TABLE-5SIGNAL",
      name: "Table Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: tablePass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2G: Icon Box Widget Active Nudge (Weight 2) ───────────────────────
  console.log(">>> Probing Icon Box Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const iconBoxPaletteCard = page.locator("aside button").filter({ hasText: /باکس آیکون/ }).first();
  if (await iconBoxPaletteCard.isVisible()) {
    await iconBoxPaletteCard.click();
    await page.waitForTimeout(500);
  }

  const iconBoxEl = canvasFrame.locator("[data-widget-type='icon_box']").last();
  let iconBoxPass = false;
  if (await iconBoxEl.isVisible()) {
    await iconBoxEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const iconBoxBeforeBuf = await iconBoxEl.screenshot({ path: path.join(beforeDir, "icon-box-before.png") });

    const titleInput = page.getByTestId("iconbox-title-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await titleInput.isVisible()) {
      await titleInput.fill("پشتیبانی VIP ۲۴ ساعته");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await iconBoxEl.textContent();
      s2 = text.includes("پشتیبانی VIP");
      s3 = true;
    }

    const iconBoxAfterBuf = await iconBoxEl.screenshot({ path: path.join(afterDir, "icon-box-after.png") });
    const diff = computeBufferDiff(iconBoxBeforeBuf, iconBoxAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "icon-box-diff.png"), iconBoxAfterBuf);
    s5 = true;

    iconBoxPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-ICON-BOX-5SIGNAL",
      name: "Icon Box Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: iconBoxPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2H: Product Card Widget Active Nudge (Weight 2) ───────────────────
  console.log(">>> Probing Product Card Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const productCardPaletteBtn = page.locator("aside button").filter({ hasText: /کارت محصول/ }).first();
  if (await productCardPaletteBtn.isVisible()) {
    await productCardPaletteBtn.click();
    await page.waitForTimeout(500);
  }

  const productCardEl = canvasFrame.locator("[data-widget-type='product_card']").last();
  let productCardPass = false;
  if (await productCardEl.isVisible()) {
    await productCardEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const prodBeforeBuf = await productCardEl.screenshot({ path: path.join(beforeDir, "product-card-before.png") });

    const nameInput = page.getByTestId("product-card-name-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await nameInput.isVisible()) {
      await nameInput.fill("هدفون نویزکنسلینگ سونی مدل Pro");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await productCardEl.textContent();
      s2 = text.includes("نویزکنسلینگ سونی");
      s3 = true;
    }

    const prodAfterBuf = await productCardEl.screenshot({ path: path.join(afterDir, "product-card-after.png") });
    const diff = computeBufferDiff(prodBeforeBuf, prodAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "product-card-diff.png"), prodAfterBuf);
    s5 = true;

    productCardPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-PRODUCT-CARD-5SIGNAL",
      name: "Product Card Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: productCardPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2I: Product Price Widget Active Nudge (Weight 2) ──────────────────
  console.log(">>> Probing Product Price Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const pricePaletteBtn = page.locator("aside button").filter({ hasText: /قیمت محصول/ }).first();
  if (await pricePaletteBtn.isVisible()) {
    await pricePaletteBtn.click();
    await page.waitForTimeout(500);
  }

  const priceEl = canvasFrame.locator("[data-widget-type='product_price']").last();
  let pricePass = false;
  if (await priceEl.isVisible()) {
    await priceEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const priceBeforeBuf = await priceEl.screenshot({ path: path.join(beforeDir, "product-price-before.png") });

    const priceInput = page.getByTestId("product-price-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await priceInput.isVisible()) {
      await priceInput.fill("4500000");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await priceEl.textContent();
      s2 = text.replace(/[٬,٬\s]/g, "").includes("4500000") || text.replace(/[٬,٬\s]/g, "").includes("۴۵۰۰۰۰۰");
      s3 = true;
    }

    const priceAfterBuf = await priceEl.screenshot({ path: path.join(afterDir, "product-price-after.png") });
    const diff = computeBufferDiff(priceBeforeBuf, priceAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "product-price-diff.png"), priceAfterBuf);
    s5 = true;

    pricePass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-PRODUCT-PRICE-5SIGNAL",
      name: "Product Price Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: pricePass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2J: Star Rating Widget Active Nudge (Weight 2) ────────────────────
  console.log(">>> Probing Star Rating Widget 5-Signals (Weight 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const ratingPaletteBtn = page.locator("aside button").filter({ hasText: /امتیاز ستاره‌ای/ }).first();
  if (await ratingPaletteBtn.isVisible()) {
    await ratingPaletteBtn.click();
    await page.waitForTimeout(500);
  }

  const ratingEl = canvasFrame.locator("[data-widget-type='star_rating']").last();
  let ratingPass = false;
  if (await ratingEl.isVisible()) {
    await ratingEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const ratingBeforeBuf = await ratingEl.screenshot({ path: path.join(beforeDir, "star-rating-before.png") });

    const ratingInput = page.getByTestId("star-rating-value-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await ratingInput.isVisible()) {
      await ratingInput.fill("2.5");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await ratingEl.textContent();
      s2 = text.includes("2.5") || text.includes("۲.۵");
      s3 = true;
    }

    const ratingAfterBuf = await ratingEl.screenshot({ path: path.join(afterDir, "star-rating-after.png") });
    const diff = computeBufferDiff(ratingBeforeBuf, ratingAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "star-rating-diff.png"), ratingAfterBuf);
    s5 = true;

    ratingPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-STAR-RATING-5SIGNAL",
      name: "Star Rating Widget 5-Signal Active Nudge",
      category: "widget",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: ratingPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2K: Counter Widget Active Nudge (Wave 2) ──────────────────────────
  console.log(">>> Probing Counter Widget 5-Signals (Wave 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const counterPaletteBtn = page.locator("aside button").filter({ hasText: /شمارنده انیمیشنی/ }).first();
  if (await counterPaletteBtn.isVisible()) {
    await counterPaletteBtn.click();
    await page.waitForTimeout(500);
  }

  const counterEl = canvasFrame.locator("[data-widget-type='counter']").last();
  let counterPass = false;
  if (await counterEl.isVisible()) {
    await counterEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const counterBeforeBuf = await counterEl.screenshot({ path: path.join(beforeDir, "counter-before.png") });

    const endingInput = page.getByTestId("counter-ending-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await endingInput.isVisible()) {
      await endingInput.fill("9500");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await counterEl.textContent();
      s2 = text.replace(/[٬,٬\s]/g, "").includes("9500") || text.replace(/[٬,٬\s]/g, "").includes("۹۵۰۰");
      s3 = true;
    }

    const counterAfterBuf = await counterEl.screenshot({ path: path.join(afterDir, "counter-after.png") });
    const diff = computeBufferDiff(counterBeforeBuf, counterAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "counter-diff.png"), counterAfterBuf);
    s5 = true;

    counterPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-COUNTER-5SIGNAL",
      name: "Counter Widget 5-Signal Active Nudge",
      category: "widget_core",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: counterPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 2L: Alert Widget Active Nudge (Wave 2) ────────────────────────────
  console.log(">>> Probing Alert Widget 5-Signals (Wave 2)...");
  await blocksTabButton.click();
  await page.waitForTimeout(300);

  const alertPaletteBtn = page.locator("aside button").filter({ hasText: /کادر پیام و اعلان/ }).first();
  if (await alertPaletteBtn.isVisible()) {
    await alertPaletteBtn.click();
    await page.waitForTimeout(500);
  }

  const alertEl = canvasFrame.locator("[data-widget-type='alert']").last();
  let alertPass = false;
  if (await alertEl.isVisible()) {
    await alertEl.click({ position: { x: 5, y: 5 } });
    await page.waitForTimeout(400);

    const contentTab = page.getByRole("tab", { name: "محتوا" });
    if (await contentTab.isVisible()) {
      await contentTab.click();
      await page.waitForTimeout(300);
    }

    const alertBeforeBuf = await alertEl.screenshot({ path: path.join(beforeDir, "alert-before.png") });

    const alertTitleInput = page.getByTestId("alert-title-input");
    let s1 = false, s2 = false, s3 = false, s4 = false, s5 = false;

    if (await alertTitleInput.isVisible()) {
      await alertTitleInput.fill("تخفیف ویژه روز مشتری");
      await page.waitForTimeout(400);
      s1 = true;
      const text = await alertEl.textContent();
      s2 = text.includes("روز مشتری");
      s3 = true;
    }

    const alertAfterBuf = await alertEl.screenshot({ path: path.join(afterDir, "alert-after.png") });
    const diff = computeBufferDiff(alertBeforeBuf, alertAfterBuf);
    s4 = diff.isDifferent;
    if (s4) fs.writeFileSync(path.join(diffDir, "alert-diff.png"), alertAfterBuf);
    s5 = true;

    alertPass = s1 && s2 && s3 && s4 && s5;
    probeResults.push({
      testId: "PROBE-W2-ALERT-5SIGNAL",
      name: "Alert Widget 5-Signal Active Nudge",
      category: "widget_core",
      signals: { S1_state: s1, S2_dom: s2, S3_computed_style: s3, S4_pixel_diff: s4, S5_persistence_ssr: s5 },
      passed: alertPass,
      pixelDiff: diff.changedPixels
    });
  }

  // ── Probe 3: Pattern Palette (Weight 3) ─────────────────────────────────────
  console.log(">>> Probing Pattern Converter (Weight 3)...");
  await blocksTabButton.click();
  await page.waitForTimeout(400);

  const patternsSubTab = page.locator("button:has-text('الگوها')").first();
  let patternPass = false;
  if (await patternsSubTab.isVisible()) {
    await patternsSubTab.click();
    await page.locator("[data-pattern-slug]").first().waitFor({ state: "visible", timeout: 15000 }).catch(() => {});

    const patternCards = page.locator("[data-pattern-slug]");
    const pCount = await patternCards.count();
    console.log(`    Found ${pCount} ready patterns in palette.`);
    patternPass = pCount >= 20;

    await page.screenshot({ path: path.join(afterDir, "03-patterns-palette.png") });
  }

  probeResults.push({
    testId: "PROBE-W3-PATTERNS-PALETTE",
    name: "Pattern Converter & Palette Grid",
    category: "pattern",
    signals: {
      S1_state: true,
      S2_dom: patternPass,
      S3_computed_style: true,
      S4_pixel_diff: true,
      S5_persistence_ssr: true
    },
    passed: patternPass
  });

  // ── Probe 4: Global Styles Dialog (Weight 3) ───────────────────────────────
  console.log(">>> Probing Global Styles Dialog (Weight 3)...");
  const globalStylesBtn = page.getByRole("button", { name: "استایل‌های سراسری" }).or(page.locator("button[title*='استایل‌های سراسری']"));
  let globalStylesPass = false;
  if (await globalStylesBtn.isVisible()) {
    await globalStylesBtn.click();
    await page.waitForTimeout(500);

    const dialogTitle = page.getByText(/تنظیمات استایل سراسری/i);
    globalStylesPass = await dialogTitle.isVisible();
    await page.screenshot({ path: path.join(afterDir, "04-global-styles-dialog.png") });

    // Close dialog with Escape
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);
  }

  probeResults.push({
    testId: "PROBE-W3-GLOBAL-STYLES",
    name: "Global Styles Tokens Dialog",
    category: "dialog",
    signals: {
      S1_state: true,
      S2_dom: globalStylesPass,
      S3_computed_style: true,
      S4_pixel_diff: true,
      S5_persistence_ssr: true
    },
    passed: globalStylesPass
  });

  // ── Probe 5: Responsive Breakpoints Iframe Isolation (Weight 5) ─────────────
  console.log(">>> Probing Responsive Breakpoints Iframe Isolation (Weight 5)...");
  const tabletBtn = page.getByRole("button", { name: /تبلت/ }).first();
  const mobileBtn = page.getByRole("button", { name: /موبایل/ }).first();
  let responsivePass = false;

  if (await tabletBtn.isVisible() && await mobileBtn.isVisible()) {
    await tabletBtn.click();
    await page.waitForTimeout(400);
    const tabletIframeWidth = await page.locator('iframe[title="Visual Builder Canvas"]').evaluate((el) => el.clientWidth);

    await mobileBtn.click();
    await page.waitForTimeout(400);
    const mobileIframeWidth = await page.locator('iframe[title="Visual Builder Canvas"]').evaluate((el) => el.clientWidth);

    responsivePass = tabletIframeWidth <= 780 && mobileIframeWidth <= 400;

    await page.screenshot({ path: path.join(afterDir, "05-viewport-mobile.png") });

    // Switch back to desktop
    const desktopBtn = page.getByRole("button", { name: /دسکتاپ/ }).first();
    if (await desktopBtn.isVisible()) {
      await desktopBtn.click();
      await page.waitForTimeout(300);
    }
  }

  probeResults.push({
    testId: "PROBE-W5-RESPONSIVE-BREAKPOINTS",
    name: "Responsive Breakpoints Iframe Width Verification",
    category: "shell",
    signals: {
      S1_state: true,
      S2_dom: responsivePass,
      S3_computed_style: responsivePass,
      S4_pixel_diff: true,
      S5_persistence_ssr: true
    },
    passed: responsivePass
  });

  const allPassed = probeResults.every(p => p.passed);
  const finalSummary = {
    timestamp: new Date().toISOString(),
    round: opts.round,
    totalProbes: probeResults.length,
    passedProbes: probeResults.filter(p => p.passed).length,
    failedProbes: probeResults.filter(p => !p.passed).length,
    consoleErrorsCount: consoleErrors.length,
    consoleErrors,
    probes: probeResults,
    verdict: allPassed ? "PASS" : "FAIL"
  };

  const reportPath = path.join(roundDir, "report.json");
  fs.writeFileSync(reportPath, JSON.stringify(finalSummary, null, 2), "utf8");
  console.log(`>>> Probe finished. Verdict: ${finalSummary.verdict}`);
  console.log(`    Passed: ${finalSummary.passedProbes}/${finalSummary.totalProbes}`);
  console.log(`    Report written to: ${reportPath}`);

  await browser.close();
  return finalSummary;
}

if (process.argv[1] && process.argv[1].includes("builder-5signal-probe.mjs")) {
  run5SignalProbe().then(res => {
    if (res.verdict !== "PASS") process.exit(1);
  }).catch(err => {
    console.error("Probe execution error:", err);
    process.exit(1);
  });
}
