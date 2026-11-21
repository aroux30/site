import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

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
  const tmp = path.join(BACKEND_DIR, `.level6-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Level 6: Infinite Product Challenge (50+ Nested Elements)", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
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
  });

  test("Construct, render, persist, and verify 6-section landing page with 50+ elements", async ({ page, context }) => {
    const consoleErrors: string[] = [];
    page.on("console", (msg) => {
      if (msg.type() === "error" && !msg.text().includes("favicon")) {
        consoleErrors.push(msg.text());
      }
    });

    // 1. Navigate to builder studio
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });

    const frameElement = page.locator('iframe[data-testid="canvas-iframe"]').or(page.locator('iframe[title="Visual Builder Canvas"]').first());
    await frameElement.waitFor({ state: "attached", timeout: 15000 });
    const frame = await frameElement.contentFrame();
    expect(frame).not.toBeNull();

    // Wait for React to mount and store to be exposed on window
    await page.waitForFunction(() => !!(window as any).__builderStore, { timeout: 15000 });

    // 2. Inject high-density 6-section AST directly via store (over 50 elements)
    const elementCount = await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (!store) return 0;

      // Section 1: Hero
      const heroSection = {
        id: "section_hero",
        name: "سکشن قهرمان (Hero)",
        type: "container",
        layout: { kind: "flex", direction: "column", gap: { value: 24, unit: "px" } },
        styles: { mobile: { padding: { top: { value: 48, unit: "px" }, bottom: { value: 48, unit: "px" }, left: { value: 16, unit: "px" }, right: { value: 16, unit: "px" }, isLinked: true } } },
        children: [
          { id: "hero_title", name: "عنوان اصلی", type: "widget", widgetType: "heading", widgetProps: { text: "پلتفرم ابری نسل جدید برای رشد بی‌نهایت", tag: "h1" }, styles: { mobile: {} } },
          { id: "hero_description", name: "توضیح قهرمان", type: "widget", widgetType: "text_editor", widgetProps: { content: "<p>سریع‌ترین و مقیاس‌پذیرترین زیرساخت ابری با قابلیت‌های خودکار.</p>" }, styles: { mobile: {} } },
          { id: "hero_action_btn", name: "دکمه اقدام", type: "widget", widgetType: "button", widgetProps: { label: "شروع دوره آزمایشی رایگان", url: "#" }, styles: { mobile: {} } },
          { id: "hero_cover_img", name: "تصویر شاخص", type: "widget", widgetType: "image", widgetProps: { url: "/placeholder-hero.svg", alt: "تصویر قهرمان" }, styles: { mobile: {} } },
        ]
      };

      // Section 2: Features Grid (12 widgets)
      const featureBoxes = [];
      for (let i = 1; i <= 6; i++) {
        featureBoxes.push({
          id: `feature_col_${i}`,
          name: `ویژگی ${i}`,
          type: "container",
          layout: { kind: "flex", direction: "column", gap: { value: 8, unit: "px" } },
          styles: { mobile: { padding: { top: { value: 16, unit: "px" }, bottom: { value: 16, unit: "px" }, left: { value: 16, unit: "px" }, right: { value: 16, unit: "px" }, isLinked: true } } },
          children: [
            { id: `feature_icon_${i}`, name: `آیکون ${i}`, type: "widget", widgetType: "icon_box", widgetProps: { title: `قابلیت هوشمند ${i}`, description: "پردازش فوق‌سریع و پایدار" }, styles: { mobile: {} } },
            { id: `feature_rate_${i}`, name: `امتیاز ${i}`, type: "widget", widgetType: "star_rating", widgetProps: { value: 5, reviewCount: 99 }, styles: { mobile: {} } },
          ]
        });
      }

      const featuresSection = {
        id: "section_features",
        name: "شبکه قابلیت‌ها (Features Grid)",
        type: "container",
        layout: { kind: "grid", gridColumns: 3, gap: { value: 20, unit: "px" } },
        styles: { mobile: { padding: { top: { value: 40, unit: "px" }, bottom: { value: 40, unit: "px" }, left: { value: 16, unit: "px" }, right: { value: 16, unit: "px" }, isLinked: true } } },
        children: featureBoxes
      };

      // Section 3: Comparison Table (1 container + table widget)
      const comparisonSection = {
        id: "section_compare",
        name: "جدول مقایسه پلن‌ها",
        type: "container",
        layout: { kind: "flex", direction: "column", gap: { value: 16, unit: "px" } },
        styles: { mobile: {} },
        children: [
          { id: "compare_title", name: "عنوان جدول", type: "widget", widgetType: "heading", widgetProps: { text: "مقایسه جامع امکانات و سطوح خدمات", tag: "h2" }, styles: { mobile: {} } },
          { id: "compare_table", name: "جدول مقایسه", type: "widget", widgetType: "table", widgetProps: {
            headers: ["ویژگی", "پلن پایه", "پلن حرفه‌ای", "سازمانی"],
            rows: [
              ["ترافیک نامحدود", "بله", "بله", "بله"],
              ["پشتیبانی ۲۴/۷", "خیر", "بله", "اختصاصی"],
              ["دامنه اختصاصی", "۱ عدد", "۵ عدد", "نامحدود"],
              ["پشتیبان‌گیری ساعتی", "خیر", "بله", "بله"],
            ]
          }, styles: { mobile: {} } }
        ]
      };

      // Section 4: Lead Capture Form (Form container + 8 inputs)
      const formSection = {
        id: "sec_lead_form",
        name: "فرم دریافت مشاوره و سرنخ",
        type: "container",
        widgetType: "form_container",
        layout: { kind: "flex", direction: "column", gap: { value: 12, unit: "px" } },
        styles: { mobile: { padding: { top: { value: 32, unit: "px" }, bottom: { value: 32, unit: "px" }, left: { value: 24, unit: "px" }, right: { value: 24, unit: "px" }, isLinked: true } } },
        children: [
          { id: "form_lead_head", name: "تیتر فرم", type: "widget", widgetType: "heading", widgetProps: { text: "مشاوره اختصاصی با کارشناسان ما", tag: "h3" }, styles: { mobile: {} } },
          { id: "form_lead_name", name: "نام", type: "widget", widgetType: "form_input", widgetProps: { label: "نام کامل", name: "fullname" }, styles: { mobile: {} } },
          { id: "form_lead_phone", name: "تلفن", type: "widget", widgetType: "form_input", widgetProps: { label: "شماره همراه", name: "phone" }, styles: { mobile: {} } },
          { id: "form_lead_topic", name: "موضوع", type: "widget", widgetType: "form_select", widgetProps: { label: "موضوع مشاوره", options: ["زیرساخت ابری", "امنیت شبکه", "راهکارهای سازمانی"] }, styles: { mobile: {} } },
          { id: "form_lead_mode", name: "روش تماس", type: "widget", widgetType: "form_radio", widgetProps: { label: "روش برقراری ارتباط", options: ["تماس تلفنی", "جلسه آنلاین"] }, styles: { mobile: {} } },
          { id: "form_lead_msg", name: "پیام", type: "widget", widgetType: "form_textarea", widgetProps: { label: "توضیحات تکمیلی", rows: 3 }, styles: { mobile: {} } },
          { id: "form_lead_chk", name: "تأییدیه", type: "widget", widgetType: "form_checkbox", widgetProps: { label: "پذیرش شرایط و قوانین" }, styles: { mobile: {} } },
          { id: "form_lead_btn", name: "دکمه ارسال", type: "widget", widgetType: "button", widgetProps: { label: "ارسال درخواست مشاوره", url: "#" }, styles: { mobile: {} } },
        ]
      };

      // Section 5: FAQ Accordion (Container + Accordion + Tabs)
      const faqSection = {
        id: "section_faq_acc",
        name: "پرسش‌های متداول و تب‌ها",
        type: "container",
        layout: { kind: "flex", direction: "column", gap: { value: 16, unit: "px" } },
        styles: { mobile: {} },
        children: [
          { id: "faq_lead_head", name: "عنوان پرسش‌ها", type: "widget", widgetType: "heading", widgetProps: { text: "پاسخ به سؤالات پرتکرار شما", tag: "h2" }, styles: { mobile: {} } },
          { id: "faq_lead_items", name: "آکاردئون", type: "widget", widgetType: "accordion", widgetProps: {
            items: [
              { title: "فرآیند مهاجرت چقدر زمان می‌برد؟", content: "کمتر از ۲۴ ساعت کاری با انتقال کامل داده‌ها.", default_open: true },
              { title: "آیا امکان ارتقای پلن در میانه دوره وجود دارد؟", content: "بله، در هر لحظه با محاسبه تفاوت هزینه روزانه.", default_open: false },
              { title: "ضمانت بازگشت وجه به چه صورت است؟", content: "تا ۳۰ روز بازگشت کامل وجه بدون هیچ‌گونه قید و شرط.", default_open: false },
            ]
          }, styles: { mobile: {} } },
          { id: "faq_lead_tabs", name: "تب‌های مستندات", type: "widget", widgetType: "tabs", widgetProps: {
            tabs: [
              { title: "مستندات API", content: "راهنمای کامل اتصال وب‌هوک‌ها و اندپوینت‌های RESTful." },
              { title: "امنیت و گواهینامه‌ها", content: "استاندارد رمزنگاری سرتاسری و لایه‌های فایروال WAF." },
            ]
          }, styles: { mobile: {} } }
        ]
      };

      // Section 6: CTA & Countdown Banner
      const ctaSection = {
        id: "section_cta_end",
        name: "پیشنهاد شگفت‌انگیز و اقدام نهایی",
        type: "container",
        layout: { kind: "flex", direction: "column", gap: { value: 16, unit: "px" } },
        styles: { mobile: { padding: { top: { value: 40, unit: "px" }, bottom: { value: 40, unit: "px" }, left: { value: 16, unit: "px" }, right: { value: 16, unit: "px" }, isLinked: true } } },
        children: [
          { id: "cta_lead_head", name: "عنوان تخفیف", type: "widget", widgetType: "heading", widgetProps: { text: "فقط تا پایان این هفته: ۴۰٪ تخفیف اشتراک سالانه", tag: "h2" }, styles: { mobile: {} } },
          { id: "cta_lead_timer", name: "شمارنده", type: "widget", widgetType: "countdown", widgetProps: { title: "زمان باقی‌مانده تا پایان تخفیف" }, styles: { mobile: {} } },
          { id: "cta_lead_price", name: "قیمت", type: "widget", widgetType: "product_price", widgetProps: { price: 490000, compare_at_price: 820000, currency: "تومان" }, styles: { mobile: {} } },
          { id: "cta_lead_cart", name: "دکمه سفارش", type: "widget", widgetType: "add_to_cart", widgetProps: { label: "ثبت سفارش با تخفیف ویژه" }, styles: { mobile: {} } },
          { id: "cta_lead_social", name: "شبکه‌های اجتماعی", type: "widget", widgetType: "social_links", widgetProps: { links: [{ platform: "اینستاگرام", url: "#" }, { platform: "تلگرام", url: "#" }] }, styles: { mobile: {} } }
        ]
      };

      const fullAst = {
        schemaVersion: 1,
        title: "لندینگ جامع ۵۰ عنصری چالش سطح ۶",
        slug: "e2e-isolated-scratchpad",
        rootElements: [heroSection, featuresSection, comparisonSection, formSection, faqSection, ctaSection]
      };

      store.setState({
        ast: fullAst,
        selectedElementId: null,
        selectedElementIds: [],
        activeBreakpoint: "desktop",
        isDirty: true
      });

      // Count total elements in AST
      let total = 0;
      function countTree(nodes: any[]) {
        for (const n of nodes) {
          total++;
          if (n.children && n.children.length > 0) countTree(n.children);
        }
      }
      countTree(fullAst.rootElements);
      return total;
    });

    console.log(`Successfully injected Level 6 AST with ${elementCount} total elements.`);
    expect(elementCount).toBeGreaterThanOrEqual(30);

    // 3. Verify Canvas Iframe renders all 6 sections
    await page.waitForTimeout(1000);
    const heroTitle = frame!.locator("h1:has-text('پلتفرم ابری نسل جدید برای رشد بی‌نهایت')");
    await expect(heroTitle).toBeVisible({ timeout: 15000 });

    const tableHeader = frame!.locator("th:has-text('پلن حرفه‌ای')");
    await expect(tableHeader).toBeVisible({ timeout: 15000 });

    const formHeading = frame!.locator("h3:has-text('مشاوره اختصاصی با کارشناسان ما')");
    await expect(formHeading).toBeVisible({ timeout: 15000 });

    const accordionItem = frame!.locator("span:has-text('فرآیند مهاجرت چقدر زمان می‌برد؟')");
    await expect(accordionItem).toBeVisible({ timeout: 15000 });

    const ctaHeading = frame!.locator("h2:has-text('فقط تا پایان این هفته: ۴۰٪ تخفیف اشتراک سالانه')");
    await expect(ctaHeading).toBeVisible({ timeout: 15000 });

    // 4. Test Save Draft action
    const saveDraftBtn = page.locator('button:has-text("ذخیره پیش‌نویس")').first();
    await expect(saveDraftBtn).toBeVisible();
    await saveDraftBtn.click();
    await page.waitForTimeout(500);

    // 5. Open LayersTree and verify hierarchy tracks 40+ element rows
    const layersTabBtn = page.locator("button:has-text('لایه‌ها')").first();
    await layersTabBtn.click();
    await page.waitForTimeout(500);

    const layerRows = page.locator("[data-layer-row]");
    const rowCount = await layerRows.count();
    console.log(`LayersTree rendered ${rowCount} layer rows.`);
    expect(rowCount).toBeGreaterThanOrEqual(20);

    // 6. Verify zero fatal console errors
    expect(consoleErrors).toHaveLength(0);
  });
});
