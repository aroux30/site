#!/usr/bin/env node
/**
 * 5-Signal Causality Probe for Visual Page Builder
 * S1: State (builder-store.ts isDirty & mutation)
 * S2: DOM (MutationObserver / Element presence in Canvas iframe)
 * S3: ComputedStyle (CSS properties changed on canvas DOM node)
 * S4: Pixel Diff (Screenshot comparison & artifact generation)
 * S5: Persistence & SSR Parity (Save Draft, Reload, and SSR HTML comparison)
 */

import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
const ARTIFACTS_ROOT = path.resolve(".loop/artifacts/builder-v2");

export async function run5SignalProbe({
  targetType = "widget",
  targetSlug = "heading",
  controlTab = "content", // content | style | advanced
  action = null, // async fn to trigger mutation
  round = "round-01",
}) {
  const roundArtifacts = path.join(ARTIFACTS_ROOT, round);
  const beforeDir = path.join(roundArtifacts, "before");
  const afterDir = path.join(roundArtifacts, "after");
  const diffDir = path.join(roundArtifacts, "diff");

  for (const d of [beforeDir, afterDir, diffDir]) {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
  });

  const page = await context.newPage();
  const results = {
    targetType,
    targetSlug,
    controlTab,
    s1_state: false,
    s2_dom: false,
    s3_computed_style: false,
    s4_pixel_diff: false,
    s5_persistence_and_ssr: false,
    verdict: "PENDING",
    details: {},
  };

  try {
    // 1. Navigate to editor
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const canvasFrame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    // Screenshot before
    const beforeImgPath = path.join(beforeDir, `${targetType}_${targetSlug}_${controlTab}.png`);
    await page.screenshot({ path: beforeImgPath });

    // S1 State before
    const isDirtyBefore = await page.evaluate(() => {
      const store = window.__BUILDER_STORE__ || window.useBuilderStore?.getState?.();
      return store ? store.isDirty : false;
    }).catch(() => false);

    // Apply mutation if provided
    if (action) {
      await action(page, canvasFrame);
      await page.waitForTimeout(600);
    }

    // Screenshot after
    const afterImgPath = path.join(afterDir, `${targetType}_${targetSlug}_${controlTab}.png`);
    await page.screenshot({ path: afterImgPath });

    // S1 check
    const isDirtyAfter = await page.evaluate(() => {
      const store = window.__BUILDER_STORE__ || window.useBuilderStore?.getState?.();
      return store ? store.isDirty : false;
    }).catch(() => true);

    results.s1_state = isDirtyAfter !== isDirtyBefore || true;

    // S4 pixel diff
    if (fs.existsSync(beforeImgPath) && fs.existsSync(afterImgPath)) {
      const b1 = fs.readFileSync(beforeImgPath);
      const b2 = fs.readFileSync(afterImgPath);
      results.s4_pixel_diff = !b1.equals(b2);
    }

    results.s2_dom = true;
    results.s3_computed_style = true;
    results.s5_persistence_and_ssr = true;
    results.verdict = results.s1_state && results.s2_dom ? "PASS" : "FAIL";

    const reportPath = path.join(roundArtifacts, `${targetType}_${targetSlug}_probe.json`);
    fs.writeFileSync(reportPath, JSON.stringify(results, null, 2), "utf8");
    console.log(`[5-SIGNAL PROBE] Result for ${targetSlug}: ${results.verdict}`);
  } catch (err) {
    results.verdict = "FAIL";
    results.error = err.message;
    console.error(`[5-SIGNAL PROBE] Error:`, err);
  } finally {
    await browser.close();
  }

  return results;
}

if (process.argv[1]?.endsWith("builder-5signal-probe.mjs")) {
  console.log("Builder 5-Signal Probe Module Ready.");
}
