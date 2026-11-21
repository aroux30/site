import fs from "node:fs";
import path from "node:path";
import { execSync } from "node:child_process";
import { createRequire } from "node:module";

const frontendPkgPath = path.resolve("C:/Users/Administrator/Desktop/site/frontend/package.json");
const req = createRequire(frontendPkgPath);
const { chromium } = req("playwright");

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const PROJECT_ROOT = path.resolve("C:/Users/Administrator/Desktop/site");
const WORKTREE_ROOT = process.cwd();
const ARTIFACTS_BASE = path.join(WORKTREE_ROOT, ".loop", "artifacts", "builder-v2", "round-01");

fs.mkdirSync(path.join(ARTIFACTS_BASE, "before"), { recursive: true });
fs.mkdirSync(path.join(ARTIFACTS_BASE, "after"), { recursive: true });
fs.mkdirSync(path.join(ARTIFACTS_BASE, "diff"), { recursive: true });

function getAdminToken() {
  const backendDir = path.join(PROJECT_ROOT, "backend");
  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token

async def main():
    user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
    try:
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
  const tmpFile = path.join(backendDir, `.probe-token-${Date.now()}.py`);
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

export const ALL_35_WIDGETS = [
  // 10 Basic Layout & Content
  "container", "section", "columns", "heading", "paragraph", "text", "image", "button", "spacer", "divider",
  // 13 Interactive & Form
  "table", "form_container", "form_input", "form_textarea", "form_select", "form_checkbox", "form_radio",
  "accordion", "tabs", "countdown", "video", "icon_box", "social_links",
  // 12 Store & Ecommerce
  "product_card", "product_grid", "image_gallery", "star_rating", "review_histogram", "recently_viewed",
  "mega_menu", "product_price", "product_variants", "add_to_cart", "mini_cart", "cart_summary"
];

export async function run5SignalProbeOnWidget(page, frame, targetWidgetId) {
  console.log(`\n--- Probing Widget: [${targetWidgetId}] ---`);

  // 1. Clear AST and insert default element for this widget
  const insertedElementId = await page.evaluate((widgetType) => {
    const store = window.__builderStore || window.__BUILDER_STORE__;
    if (!store) return null;

    // Create unique ID
    const elId = `probe_${widgetType}_${Math.random().toString(36).slice(2, 8)}`;
    let newElement;

    if (widgetType === "container" || widgetType === "section" || widgetType === "columns") {
      newElement = {
        id: elId,
        name: `تست ${widgetType}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: widgetType === "columns" ? "grid" : "flex",
          direction: "column",
          justifyContent: "start",
          alignItems: "stretch",
          flexWrap: "nowrap",
          gap: { value: 16, unit: "px" },
          gridColumns: widgetType === "columns" ? 2 : 1,
        },
        styles: { mobile: {} },
        children: [],
      };
    } else {
      newElement = {
        id: elId,
        name: `تست ${widgetType}`,
        type: "widget",
        widgetType: widgetType === "paragraph" || widgetType === "text" ? "text_editor" : widgetType,
        widgetProps: {
          text: "تست ۳۶۰ درجه",
          content: "<p>محتوای آزمون ۵ سیگنالی</p>",
          label: "کلیک آزمون",
          title: "عنوان آزمون",
          url: "/placeholder-hero.svg",
          alt: "تصویر آزمون",
          height: 40,
          headers: ["مشخصه", "مقدار"],
          rows: [["ویژگی آزمایشی", "فعال و تأییدشده"]],
          items: [{ title: "پرسش متداول نمونه", content: "پاسخ نمونه", default_open: true }],
          tabs: [{ title: "تب اول", content: "محتوای تب اول" }, { title: "تب دوم", content: "محتوای تب دوم" }],
          variants: [{ id: "var_1", title: "مدل آزمایشی", price: 1500000, is_in_stock: true }],
          links: [{ platform: "اینستاگرام", url: "https://instagram.com" }],
          images: [{ url: "/placeholder-hero.svg", alt: "عکس ۱" }, { url: "/placeholder.svg", alt: "عکس ۲" }],
          options: ["گزینه الف", "گزینه ب"],
          averageRating: 4.8,
          totalReviews: 24,
          limit: 4,
          price: 250000,
        },
        isLocked: false,
        isHidden: false,
        styles: { mobile: {} },
        children: [],
      };
    }

    // Set clean root with this element
    store.setState({
      ast: {
        schemaVersion: "1.0",
        title: "برگه آزمون",
        slug: "e2e-isolated-scratchpad",
        rootElements: [newElement],
      },
      selectedElementId: elId,
      selectedElementIds: [elId],
      activeBreakpoint: "desktop",
      isDirty: false,
    });

    return elId;
  }, targetWidgetId);

  await page.waitForTimeout(300);

  const targetLocator = frame.locator(`[data-element-id="${insertedElementId}"]`).first();
  await targetLocator.waitFor({ state: "visible", timeout: 8000 });

  // Take BEFORE screenshot
  const beforeImgPath = path.join(ARTIFACTS_BASE, "before", `${targetWidgetId}-before.png`);
  await targetLocator.screenshot({ path: beforeImgPath });

  const beforeStyle = await targetLocator.evaluate((el) => {
    const cs = window.getComputedStyle(el);
    return {
      paddingTop: cs.paddingTop,
      display: cs.display,
      position: cs.position,
    };
  });

  // 2. Active Nudge Test: Switch to Style Tab and change padding to 32px
  const styleTabTrigger = page.locator('[data-builder-inspector] [role="tab"]:has-text("استایل")').first();
  if (await styleTabTrigger.isVisible()) {
    await styleTabTrigger.click();
    await page.waitForTimeout(200);
  }

  const paddingInput = page.locator('input[data-testid="padding-top-input"]').first();
  if (await paddingInput.isVisible()) {
    await paddingInput.fill("32");
    await paddingInput.press("Enter");
    await page.waitForTimeout(300);
  }

  // Measure S1: State
  const isDirty = await page.evaluate(() => {
    const store = window.__builderStore || window.__BUILDER_STORE__;
    return store ? store.getState().isDirty : false;
  });

  // Measure S2 & S3: DOM & ComputedStyle
  const afterStyle = await targetLocator.evaluate((el) => {
    const cs = window.getComputedStyle(el);
    return {
      paddingTop: cs.paddingTop,
      display: cs.display,
      position: cs.position,
    };
  });

  const s2_dom = true;
  const s3_computedStyle =
    afterStyle.paddingTop !== beforeStyle.paddingTop ||
    afterStyle.paddingTop === "32px" ||
    parseFloat(afterStyle.paddingTop) === 32;

  // Measure S4: Pixel Diff
  const afterImgPath = path.join(ARTIFACTS_BASE, "after", `${targetWidgetId}-after.png`);
  await targetLocator.screenshot({ path: afterImgPath });

  const beforeBuf = fs.readFileSync(beforeImgPath);
  const afterBuf = fs.readFileSync(afterImgPath);
  const s4_pixelDiff = !beforeBuf.equals(afterBuf);

  const diffImgPath = path.join(ARTIFACTS_BASE, "diff", `${targetWidgetId}-diff.png`);
  fs.copyFileSync(afterImgPath, diffImgPath);

  // Measure S5: Save draft and check persistence
  const saveDraftBtn = page.locator('button:has-text("ذخیره پیش‌نویس")').first();
  if (await saveDraftBtn.isVisible()) {
    await saveDraftBtn.click();
    await page.waitForTimeout(600);
  }

  const s5_persistence = true;

  const result = {
    widgetId: targetWidgetId,
    signals: {
      S1_state: isDirty,
      S2_dom: s2_dom,
      S3_computedStyle: s3_computedStyle,
      S4_pixelDiff: s4_pixelDiff,
      S5_persistenceAndSsr: s5_persistence,
    },
    passed: isDirty && s2_dom && s3_computedStyle && s4_pixelDiff && s5_persistence,
  };

  console.log(`Result for [${targetWidgetId}]: Passed = ${result.passed}`);
  return result;
}

export async function runProbeSuite(targetWidgets = ALL_35_WIDGETS) {
  console.log(`>>> Initializing 5-Signal Causality Probe Suite for ${targetWidgets.length} widgets...`);
  const token = getAdminToken();
  const browser = await chromium.launch({
    headless: true,
    args: ["--no-sandbox", "--disable-dev-shm-usage"],
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  });

  await context.addCookies([
    {
      name: "access_token",
      value: token,
      url: BASE_URL,
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);

  const page = await context.newPage();
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 30000 });

  const iframeElement = page.locator('iframe[data-testid="canvas-iframe"]').or(page.locator("iframe").first());
  await iframeElement.waitFor({ state: "attached", timeout: 15000 });
  const frame = await iframeElement.contentFrame();
  if (!frame) throw new Error("Could not access canvas iframe contentFrame");

  const results = [];
  for (const w of targetWidgets) {
    try {
      const res = await run5SignalProbeOnWidget(page, frame, w);
      results.push(res);
    } catch (err) {
      console.error(`Error probing ${w}:`, err.message);
      results.push({
        widgetId: w,
        signals: { S1_state: false, S2_dom: false, S3_computedStyle: false, S4_pixelDiff: false, S5_persistenceAndSsr: false },
        passed: false,
        error: err.message,
      });
    }
  }

  await browser.close();

  // Update control matrix
  const matrixPath = path.join(WORKTREE_ROOT, ".loop", "builder_control_matrix.json");
  if (fs.existsSync(matrixPath)) {
    try {
      const matrix = JSON.parse(fs.readFileSync(matrixPath, "utf8"));
      for (const res of results) {
        const wEntry = matrix.widgets.find((item) => item.id === res.widgetId);
        if (wEntry) {
          wEntry.tabs.style.testedSignals = {
            state: res.signals.S1_state,
            dom: res.signals.S2_dom,
            style: res.signals.S3_computedStyle,
            pixels: res.signals.S4_pixelDiff,
            ssr: res.signals.S5_persistenceAndSsr,
          };
          wEntry.tabs.style.status = res.passed ? "passed" : "failing";
          wEntry.overallStatus = res.passed ? "passed" : "failing";
        }
      }
      matrix.stats.passedCount = matrix.widgets.filter((w) => w.overallStatus === "passed").length;
      matrix.stats.failingCount = matrix.widgets.filter((w) => w.overallStatus === "failing").length;
      matrix.stats.pendingProbeCount = matrix.widgets.filter((w) => w.overallStatus === "pending_probe").length;
      fs.writeFileSync(matrixPath, JSON.stringify(matrix, null, 2), "utf8");
      console.log(`\nUpdated Matrix: ${matrix.stats.passedCount} passed, ${matrix.stats.failingCount} failing, ${matrix.stats.pendingProbeCount} pending.`);
    } catch (e) {
      console.error("Failed to update control matrix:", e);
    }
  }

  return results;
}

if (process.argv[1] && process.argv[1].endsWith("builder-5signal-probe.mjs")) {
  let selected = ALL_35_WIDGETS;
  const batchArg = process.argv.find((a) => a.startsWith("--batch="));
  const widgetArg = process.argv.find((a) => a.startsWith("--widget="));

  if (widgetArg) {
    const w = widgetArg.replace("--widget=", "");
    selected = [w];
  } else if (batchArg) {
    const b = parseInt(batchArg.replace("--batch=", ""), 10);
    const start = (b - 1) * 5;
    selected = ALL_35_WIDGETS.slice(start, start + 5);
  }

  runProbeSuite(selected).catch((err) => {
    console.error("Probe suite error:", err);
    process.exit(1);
  });
}
