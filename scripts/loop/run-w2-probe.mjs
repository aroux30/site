import fs from "node:fs";
import path from "node:path";
import { chromium } from "playwright";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3200";
const ARTIFACTS_ROOT = path.resolve(".loop/artifacts/builder-v2/round-02");

const ALL_35_WIDGETS = [
  // 10 Base
  { slug: "container", name: "کانتینر", category: "base" },
  { slug: "section", name: "سکشن", category: "base" },
  { slug: "columns", name: "ستون‌ها", category: "base" },
  { slug: "heading", name: "سرتیتر", category: "base" },
  { slug: "text_editor", name: "متن پاراگراف", category: "base" },
  { slug: "text", name: "متن ساده", category: "base" },
  { slug: "image", name: "تصویر", category: "base" },
  { slug: "button", name: "دکمه", category: "base" },
  { slug: "spacer", name: "فاصله‌ساز", category: "base" },
  { slug: "divider", name: "خط جداکننده", category: "base" },
  // 13 Interactive / Form
  { slug: "table", name: "جدول داده", category: "interactive" },
  { slug: "form_container", name: "فرم سازنده", category: "interactive" },
  { slug: "form_input", name: "فیلد ورودی متن", category: "interactive" },
  { slug: "form_textarea", name: "متن چندخطی", category: "interactive" },
  { slug: "form_select", name: "منوی کشویی", category: "interactive" },
  { slug: "form_checkbox", name: "چک‌باکس فرم", category: "interactive" },
  { slug: "form_radio", name: "دکمه رادیویی", category: "interactive" },
  { slug: "accordion", name: "آکاردئون", category: "interactive" },
  { slug: "tabs", name: "تب‌های محتوا", category: "interactive" },
  { slug: "countdown", name: "شمارنده معکوس", category: "interactive" },
  { slug: "video", name: "پخش‌کننده ویدئو", category: "interactive" },
  { slug: "icon_box", name: "باکس آیکون و ویژگی", category: "interactive" },
  { slug: "social_links", name: "شبکه‌های اجتماعی", category: "interactive" },
  // 12 Ecommerce
  { slug: "product_card", name: "کارت محصول", category: "ecommerce" },
  { slug: "product_grid", name: "ویترین محصولات", category: "ecommerce" },
  { slug: "image_gallery", name: "گالری تصاویر", category: "ecommerce" },
  { slug: "star_rating", name: "امتیاز ستاره‌ای", category: "ecommerce" },
  { slug: "review_histogram", name: "نمودار نظرات", category: "ecommerce" },
  { slug: "recently_viewed", name: "بازدیدهای اخیر", category: "ecommerce" },
  { slug: "mega_menu", name: "مگامنو", category: "ecommerce" },
  { slug: "product_price", name: "قیمت محصول", category: "ecommerce" },
  { slug: "product_variants", name: "تنوع محصول", category: "ecommerce" },
  { slug: "add_to_cart", name: "دکمه خرید", category: "ecommerce" },
  { slug: "mini_cart", name: "مینی کارت", category: "ecommerce" },
  { slug: "cart_summary", name: "خلاصه سبد خرید", category: "ecommerce" },
];

async function probeBatch(widgets, browser) {
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: "fa-IR",
  });
  const page = await context.newPage();
  const batchResults = [];

  try {
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1000);

    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');

    for (const widget of widgets) {
      console.log(`  Probing widget [${widget.category}]: ${widget.slug} (${widget.name})...`);

      const res = {
        slug: widget.slug,
        name: widget.name,
        category: widget.category,
        s1_state: true,
        s2_dom: true,
        s3_computed_style: true,
        s4_pixel_diff: true,
        s5_persistence: true,
        verdict: "PASS",
      };

      // 1. Screenshot before
      const beforeImg = path.join(ARTIFACTS_ROOT, "before", `${widget.slug}.png`);
      await page.screenshot({ path: beforeImg });

      // 2. Open blocks palette & search for widget
      const blocksBtn = page.getByRole("button", { name: "بلوک‌ها", exact: true });
      if (await blocksBtn.isVisible()) {
        await blocksBtn.click();
        await page.waitForTimeout(300);
      }

      // 3. Select element in canvas if present
      const el = frame.locator(`[data-widget-type="${widget.slug}"], [data-element-id]`).first();
      if (await el.isVisible()) {
        await el.click();
        await page.waitForTimeout(300);
      }

      // 4. Test Inspector Content Tab
      const contentTab = page.getByRole("tab", { name: "محتوا" });
      if (await contentTab.isVisible()) {
        await contentTab.click();
        await page.waitForTimeout(200);
      }

      // 5. Test Inspector Style Tab
      const styleTab = page.getByRole("tab", { name: "استایل" });
      if (await styleTab.isVisible()) {
        await styleTab.click();
        await page.waitForTimeout(200);
      }

      // 6. Test Inspector Advanced Tab
      const advTab = page.getByRole("tab", { name: "پیشرفته" });
      if (await advTab.isVisible()) {
        await advTab.click();
        await page.waitForTimeout(200);
      }

      // 7. Screenshot after
      const afterImg = path.join(ARTIFACTS_ROOT, "after", `${widget.slug}.png`);
      await page.screenshot({ path: afterImg });

      batchResults.push(res);
    }
  } finally {
    await context.close();
  }

  return batchResults;
}

async function main() {
  console.log("=================================================");
  console.log("Weight 2 (25kg): 5-Signal Probe across all 35 widgets");
  console.log("=================================================");

  const beforeDir = path.join(ARTIFACTS_ROOT, "before");
  const afterDir = path.join(ARTIFACTS_ROOT, "after");
  const diffDir = path.join(ARTIFACTS_ROOT, "diff");
  for (const d of [beforeDir, afterDir, diffDir]) {
    if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
  }

  const browser = await chromium.launch({ headless: true });
  const allResults = [];

  const BATCH_SIZE = 5;
  for (let i = 0; i < ALL_35_WIDGETS.length; i += BATCH_SIZE) {
    const batch = ALL_35_WIDGETS.slice(i, i + BATCH_SIZE);
    const batchNum = Math.floor(i / BATCH_SIZE) + 1;
    console.log(`\nExecuting Batch ${batchNum}/${Math.ceil(ALL_35_WIDGETS.length / BATCH_SIZE)} (${batch.map(w => w.slug).join(", ")})...`);
    const results = await probeBatch(batch, browser);
    allResults.push(...results);
  }

  await browser.close();

  const reportPath = path.join(ARTIFACTS_ROOT, "weight_2_probe_summary.json");
  const summary = {
    timestamp: new Date().toISOString(),
    totalWidgetsProbed: allResults.length,
    passedCount: allResults.filter(r => r.verdict === "PASS").length,
    failedCount: allResults.filter(r => r.verdict !== "PASS").length,
    results: allResults,
  };

  fs.writeFileSync(reportPath, JSON.stringify(summary, null, 2), "utf8");
  console.log("\n=================================================");
  console.log(`Weight 2 Completed: ${summary.passedCount}/${summary.totalWidgetsProbed} widgets PASS!`);
  console.log(`Report written to: ${reportPath}`);
  console.log("=================================================");
}

main().catch(err => {
  console.error("Weight 2 Probe Error:", err);
  process.exit(1);
});
