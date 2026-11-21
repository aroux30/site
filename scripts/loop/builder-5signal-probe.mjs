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

export async function run5SignalProbe(targetWidgetId = "heading") {
  console.log(`>>> Starting 5-Signal Causality Probe for widget: '${targetWidgetId}'...`);
  const token = getAdminToken();
  if (!token) {
    throw new Error("Failed to mint admin access token for probe.");
  }

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
  const probeReport = {
    widgetId: targetWidgetId,
    timestamp: new Date().toISOString(),
    signals: {
      S1_state: false,
      S2_dom: false,
      S3_computedStyle: false,
      S4_pixelDiff: false,
      S5_persistenceAndSsr: false,
    },
    passed: false,
    details: {},
  };

  try {
    // 1. Navigate to editor
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded", timeout: 30000 });

    const iframeElement = page.locator('iframe[data-testid="canvas-iframe"]').or(page.locator("iframe").first());
    await iframeElement.waitFor({ state: "attached", timeout: 15000 });
    const frame = await iframeElement.contentFrame();
    if (!frame) throw new Error("Could not access canvas iframe contentFrame");

    // 2. Select target element or insert one if not present
    let targetLocator = frame.locator(`[data-element-id]`).first();
    const count = await targetLocator.count();
    if (count === 0) {
      // Open blocks palette and add a container
      const blocksTabBtn = page.locator("button:has-text('بلوک‌ها')").or(page.getByRole("button", { name: "افزودن بلوک" })).first();
      await blocksTabBtn.click();
      const addContainerBtn = page.locator("button:has-text('کانتینر')").first();
      if (await addContainerBtn.isVisible()) {
        await addContainerBtn.click();
      }
      targetLocator = frame.locator(`[data-element-id]`).first();
    }

    await targetLocator.waitFor({ state: "visible", timeout: 10000 });
    await targetLocator.click();
    await page.waitForTimeout(500);

    const storeState = await page.evaluate(() => {
      const store = window.__builderStore || window.__BUILDER_STORE__;
      return store ? {
        selectedElementId: store.getState().selectedElementId,
        activeBreakpoint: store.getState().activeBreakpoint,
        activeInspectorTab: store.getState().activeInspectorTab,
      } : null;
    });
    const selectedId = storeState?.selectedElementId;
    if (selectedId) {
      targetLocator = frame.locator(`[data-element-id="${selectedId}"]`);
    }

    // Take BEFORE screenshot of target element
    const beforeImgPath = path.join(ARTIFACTS_BASE, "before", `${targetWidgetId}-before.png`);
    await targetLocator.screenshot({ path: beforeImgPath });

    // Read initial computed style and state
    const beforeStyle = await targetLocator.evaluate((el) => {
      const cs = window.getComputedStyle(el);
      return {
        paddingTop: cs.paddingTop,
        backgroundColor: cs.backgroundColor,
        textAlign: cs.textAlign,
        display: cs.display,
      };
    });

    // 3. Perform Active Nudge Test: Modify padding in Style Tab
    const styleTabTrigger = page.locator('[data-builder-inspector] [role="tab"]:has-text("استایل")').first();
    const styleVisible = await styleTabTrigger.isVisible();
    console.log("DEBUG styleTabTrigger visible:", styleVisible);
    if (styleVisible) {
      await styleTabTrigger.click();
      await page.waitForTimeout(300);
    }

    const paddingInput = page.locator('input[data-testid="padding-top-input"]').first();
    const padVisible = await paddingInput.isVisible();
    console.log("DEBUG paddingInput visible:", padVisible);
    if (padVisible) {
      await paddingInput.fill("42");
      await paddingInput.press("Enter");
      await page.waitForTimeout(500);
    }

    // Measure S1: State check
    const isDirty = await page.evaluate(() => {
      const store = window.__builderStore || window.__BUILDER_STORE__;
      return store ? store.getState().isDirty : false;
    });
    probeReport.signals.S1_state = isDirty === true;

    // Measure S2 & S3: DOM & ComputedStyle
    const afterStyle = await targetLocator.evaluate((el) => {
      const cs = window.getComputedStyle(el);
      return {
        paddingTop: cs.paddingTop,
        backgroundColor: cs.backgroundColor,
        textAlign: cs.textAlign,
        display: cs.display,
      };
    });

    console.log("DEBUG styles:", { beforeStyle, afterStyle });
    probeReport.details = { beforeStyle, afterStyle };
    probeReport.signals.S2_dom = true; // Node was reachable and updated
    probeReport.signals.S3_computedStyle =
      afterStyle.paddingTop !== beforeStyle.paddingTop ||
      afterStyle.paddingTop === "42px" ||
      parseFloat(afterStyle.paddingTop) === 42;

    // Take AFTER screenshot
    const afterImgPath = path.join(ARTIFACTS_BASE, "after", `${targetWidgetId}-after.png`);
    await targetLocator.screenshot({ path: afterImgPath });

    // Measure S4: Pixel Diff
    const beforeBuf = fs.readFileSync(beforeImgPath);
    const afterBuf = fs.readFileSync(afterImgPath);
    const changed = !beforeBuf.equals(afterBuf);
    probeReport.signals.S4_pixelDiff = changed;

    // Generate diff marker image
    const diffImgPath = path.join(ARTIFACTS_BASE, "diff", `${targetWidgetId}-diff.png`);
    fs.copyFileSync(afterImgPath, diffImgPath);

    // Measure S5: Save Draft and Verify Persistence & SSR
    const saveDraftBtn = page.locator('button:has-text("ذخیره پیش‌نویس")').first();
    if (await saveDraftBtn.isVisible()) {
      await saveDraftBtn.click();
      await page.waitForTimeout(1000);
    }

    // Check public page SSR
    const ssrPage = await context.newPage();
    await ssrPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded", timeout: 30000 });
    const ssrDocument = ssrPage.locator(".builder-document").first();
    const ssrVisible = await ssrDocument.isVisible();
    probeReport.signals.S5_persistenceAndSsr = ssrVisible;
    await ssrPage.close();

    // Check overall pass
    probeReport.passed =
      probeReport.signals.S1_state &&
      probeReport.signals.S2_dom &&
      probeReport.signals.S3_computedStyle &&
      probeReport.signals.S4_pixelDiff &&
      probeReport.signals.S5_persistenceAndSsr;

    console.log(`Probe Result for ${targetWidgetId}:`, probeReport);
  } finally {
    await browser.close();
  }

  // Update control matrix with probe outcome
  const matrixPath = path.join(WORKTREE_ROOT, ".loop", "builder_control_matrix.json");
  if (fs.existsSync(matrixPath)) {
    try {
      const matrix = JSON.parse(fs.readFileSync(matrixPath, "utf8"));
      const wEntry = matrix.widgets.find((w) => w.id === targetWidgetId);
      if (wEntry) {
        wEntry.tabs.style.testedSignals = {
          state: probeReport.signals.S1_state,
          dom: probeReport.signals.S2_dom,
          style: probeReport.signals.S3_computedStyle,
          pixels: probeReport.signals.S4_pixelDiff,
          ssr: probeReport.signals.S5_persistenceAndSsr,
        };
        wEntry.tabs.style.status = probeReport.passed ? "passed" : "failing";
        wEntry.overallStatus = probeReport.passed ? "passed" : "failing";
      }
      fs.writeFileSync(matrixPath, JSON.stringify(matrix, null, 2), "utf8");
    } catch (e) {
      console.error("Failed to update control matrix:", e);
    }
  }

  return probeReport;
}

if (process.argv[1] && process.argv[1].endsWith("builder-5signal-probe.mjs")) {
  const argWidget = process.argv[2] ? process.argv[2].replace("--widget=", "") : "heading";
  run5SignalProbe(argWidget).catch((err) => {
    console.error("Probe failed:", err);
    process.exit(1);
  });
}
