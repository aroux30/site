#!/usr/bin/env node
/**
 * scripts/loop/sensors.mjs
 * The 4 Deterministic Sensors & Calibration Suite
 */

import { chromium } from "playwright";
import fs from "node:fs";
import path from "node:path";

export async function auditScrollTrap(page) {
  return await page.evaluate(() => {
    const el = document.querySelector("[data-testid=\"inspector-scroll-container\"]") || document.querySelector(".outer");
    if (!el) return { scrollable: false, pass: false };

    const style = window.getComputedStyle(el);
    const hasScrollHeight = el.scrollHeight > el.clientHeight + 2;
    const isOverflowHidden = style.overflowY === "hidden" || style.overflow === "hidden";
    const canScroll = (style.overflowY === "auto" || style.overflowY === "scroll") && hasScrollHeight;

    return {
      hasScrollHeight,
      isOverflowHidden,
      canScroll,
      pass: canScroll && !isOverflowHidden,
    };
  });
}

export async function auditClippedX(page) {
  return await page.evaluate(() => {
    const parent = document.querySelector(".parent") || document.documentElement;
    const child = document.querySelector(".child") || document.body;
    const pRect = parent.getBoundingClientRect();
    const cRect = child.getBoundingClientRect();

    const overflowsParent = cRect.right > pRect.right + 1 || child.scrollWidth > parent.clientWidth + 1;
    const docOverflows = document.documentElement.scrollWidth > document.documentElement.clientWidth + 1;

    const isClipped = overflowsParent || docOverflows;
    return {
      overflowsParent,
      docOverflows,
      isClipped,
      pass: !isClipped,
    };
  });
}

export async function auditMenu(page) {
  const btn = await page.$("[role=\"combobox\"], #menu-btn");
  if (!btn) return { opened: false, optionsCount: 0, pass: false };

  await btn.click();
  await page.waitForTimeout(200);

  return await page.evaluate(() => {
    const listbox = document.querySelector("[role=\"listbox\"], [data-radix-popper-content-wrapper], #dropdown");
    if (!listbox) return { opened: false, optionsCount: 0, pass: false };

    const style = window.getComputedStyle(listbox);
    const rect = listbox.getBoundingClientRect();
    const visible = style.display !== "none" && style.visibility !== "hidden" && rect.width > 20 && rect.height > 20;
    const options = listbox.querySelectorAll("[role=\"option\"], .option");

    return {
      opened: visible,
      optionsCount: options.length,
      pass: visible && options.length >= 2,
    };
  });
}

export async function auditSemanticWidget(page) {
  return await page.evaluate(() => {
    const iconTexts = Array.from(document.querySelectorAll(".icon-text, .icon-slug, span")).map((s) => s.textContent?.trim());
    const hasRawStar = iconTexts.includes("star") || iconTexts.includes("heart");
    const svgs = document.querySelectorAll("svg");
    let validSvg = false;
    for (const svg of svgs) {
      const rect = svg.getBoundingClientRect();
      const hasPath = svg.querySelectorAll("path, polygon, circle, rect").length > 0;
      if (rect.width >= 10 && rect.height >= 10 && hasPath) {
        validSvg = true;
        break;
      }
    }

    return {
      hasRawStar,
      validSvg,
      pass: !hasRawStar && validSvg,
    };
  });
}

export async function auditActionsVisibility(page) {
  return await page.evaluate(() => {
    const actions = document.querySelector(".layer-row .actions, [data-layer-actions]");
    if (!actions) return { visible: false, pass: false };
    const style = window.getComputedStyle(actions);
    const visible = parseFloat(style.opacity) > 0.8 && style.display !== "none" && style.visibility !== "hidden";
    return { visible, opacity: style.opacity, pass: visible };
  });
}

export async function auditColorFormat(page) {
  return await page.evaluate(() => {
    const input = document.querySelector("#color, input[name=\"color\"], [data-color-input]");
    if (!input) return { valid: false, pass: false };
    const val = input.value || "";
    const isInvalid = val.includes("hsl(#") || (val === "#000000" && !input.getAttribute("data-explicit-black"));
    const isHex = /^#[0-9A-Fa-f]{6}$/.test(val) || /^#[0-9A-Fa-f]{3}$/.test(val);
    return { val, isHex, isInvalid, pass: isHex && !isInvalid };
  });
}

// ── CALIBRATION RUNNER ────────────────────────────────────────────────────────
export async function runCalibration() {
  console.log("=== SENSORS CALIBRATION: TESTING RED/GREEN ON FIXTURES ===");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();
  const page = await context.newPage();

  const fixtureDir = path.resolve("scripts/loop/fixtures");
  const tests = [
    {
      name: "SCROLL_TRAP",
      broken: `file://${path.join(fixtureDir, "scroll_trap_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "scroll_trap_healthy.html")}`,
      audit: auditScrollTrap,
    },
    {
      name: "CLIPPED_X",
      broken: `file://${path.join(fixtureDir, "clipped_x_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "clipped_x_healthy.html")}`,
      audit: auditClippedX,
    },
    {
      name: "DEAD_MENU",
      broken: `file://${path.join(fixtureDir, "dead_menu_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "dead_menu_healthy.html")}`,
      audit: auditMenu,
    },
    {
      name: "RAW_ICON_SLUG",
      broken: `file://${path.join(fixtureDir, "raw_icon_slug_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "raw_icon_slug_healthy.html")}`,
      audit: auditSemanticWidget,
    },
    {
      name: "INVISIBLE_ACTIONS",
      broken: `file://${path.join(fixtureDir, "invisible_actions_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "invisible_actions_healthy.html")}`,
      audit: auditActionsVisibility,
    },
    {
      name: "INVALID_COLOR",
      broken: `file://${path.join(fixtureDir, "invalid_color_broken.html")}`,
      healthy: `file://${path.join(fixtureDir, "invalid_color_healthy.html")}`,
      audit: auditColorFormat,
    },
  ];

  let allCalibrated = true;

  for (const t of tests) {
    // 1. Test Broken -> Expect RED (pass === false)
    await page.goto(t.broken);
    const brokenRes = await t.audit(page);
    const brokenIsRed = !brokenRes.pass;

    // 2. Test Healthy -> Expect GREEN (pass === true)
    await page.goto(t.healthy);
    const healthyRes = await t.audit(page);
    const healthyIsGreen = healthyRes.pass;

    const sensorOk = brokenIsRed && healthyIsGreen;
    if (!sensorOk) allCalibrated = false;

    console.log(`[Sensor: ${t.name.padEnd(18)}] Broken=RED: ${brokenIsRed ? "PASS (RED)" : "FAIL (NOT RED)"} | Healthy=GREEN: ${healthyIsGreen ? "PASS (GREEN)" : "FAIL (NOT GREEN)"} => ${sensorOk ? "CALIBRATED OK" : "CALIBRATION ERROR"}`);
  }

  await browser.close();

  if (allCalibrated) {
    console.log("\n[SUCCESS] 100% of sensors verified RED on broken fixtures and GREEN on healthy fixtures.");
  } else {
    console.error("\n[FAILURE] Sensor calibration mismatch detected.");
    process.exit(1);
  }
}

// CLI entry point
const args = process.argv.slice(2);
if (args.includes("--calibrate") || args.includes("--test-fixtures") || args.length === 0) {
  runCalibration().catch((err) => {
    console.error("Calibration error:", err);
    process.exit(1);
  });
}
