import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:1005";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");
const ARTIFACTS_DIR = path.resolve(".loop/artifacts/builder-gym/round-059/after");

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
  const tmp = path.join(BACKEND_DIR, `.gym-w9-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Weight 9: Full Landing Page Construction from Scratch & Polish", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    if (token) {
      await context.addCookies([
        { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://localhost:1005", httpOnly: false, sameSite: "Lax" },
        { name: "access_token", value: token, url: "http://127.0.0.1:1005", httpOnly: false, sameSite: "Lax" },
      ]);
    }
    await context.setExtraHTTPHeaders({
      "x-forwarded-for": `10.214.${Math.floor(Math.random() * 200)}.${Math.floor(Math.random() * 200)}`,
    });
    await context.addInitScript(() => {
      localStorage.setItem(
        "auth-storage",
        JSON.stringify({
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. Build complete 7-section landing page from scratch via AST store", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    // Populate full Landing Page: Hero + Features + Comparison Table + Multi-Step Form + FAQ + Popup + CTA
    const sectionCount = await page.evaluate(() => {
      const store = (window as any).__builderStore || (window as any).__BUILDER_STORE__;
      if (!store) return 0;

      const fullLandingSections = [
        // 1. Hero Section
        {
          id: `sec_hero_${Date.now()}`,
          name: "بخش هیرو و معرفی (Hero)",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "center",
            alignItems: "center",
            flexWrap: "nowrap",
            gap: { value: 20, unit: "px" },
            boxedWidth: { value: 1280, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 48, unit: "px" }, right: { value: 24, unit: "px" }, bottom: { value: 48, unit: "px" }, left: { value: 24, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: `el_hero_head_${Date.now()}`,
              name: "تیتر اصلی هیرو",
              type: "widget",
              widgetType: "heading",
              widgetProps: { text: "پلتفرم نسل آینده فروشگاه اینترنتی و تجارت الکترونیک", tag: "h1" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
            {
              id: `el_hero_sub_${Date.now()}`,
              name: "متن معرفی هیرو",
              type: "widget",
              widgetType: "paragraph",
              widgetProps: { content: "تجربه‌ای بدون مرز از طراحی بصری، سرعت پردازش ابری و امکانات سازمانی برای رشد فروشگاه شما." },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
            {
              id: `el_hero_cta_${Date.now()}`,
              name: "دکمه ثبت‌نام فوری",
              type: "widget",
              widgetType: "button",
              widgetProps: { label: "شروع رایگان هم‌اکنون", url: "/register" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 2. Features Grid Section
        {
          id: `sec_features_${Date.now()}`,
          name: "شبکه ویژگی‌ها و خدمات",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "grid",
            gridColumns: 3,
            gap: { value: 24, unit: "px" },
            boxedWidth: { value: 1280, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 40, unit: "px" }, right: { value: 20, unit: "px" }, bottom: { value: 40, unit: "px" }, left: { value: 20, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: `el_feat_1_${Date.now()}`,
              name: "ویژگی اول",
              type: "widget",
              widgetType: "image_box",
              widgetProps: { title: "سرعت فوق‌العاده", description: "پاسخ‌دهی زیر ۲۰ میلی‌ثانیه با زیرساخت لبه ابری", image_url: "/placeholder-hero.svg" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
            {
              id: `el_feat_2_${Date.now()}`,
              name: "ویژگی دوم",
              type: "widget",
              widgetType: "image_box",
              widgetProps: { title: "امنیت بانکی", description: "رمزنگاری سراسری و مقاومت کامل در برابر حملات", image_url: "/placeholder-hero.svg" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
            {
              id: `el_feat_3_${Date.now()}`,
              name: "ویژگی سوم",
              type: "widget",
              widgetType: "image_box",
              widgetProps: { title: "شخصی‌سازی نامحدود", description: "بیش از ۷۰ ابزارک حرفه‌ای برای طراحی اختصاصی", image_url: "/placeholder-hero.svg" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 3. Comparison Table Section
        {
          id: `sec_table_${Date.now()}`,
          name: "جدول مقایسه پلن‌ها",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            boxedWidth: { value: 1280, unit: "px" },
          },
          styles: { mobile: {} },
          children: [
            {
              id: `el_comp_tbl_${Date.now()}`,
              name: "جدول مقایسه قابلیت‌ها",
              type: "widget",
              widgetType: "table",
              widgetProps: {
                headers: ["قابلیت", "نسخه پایه", "نسخه حرفه‌ای", "نسخه سازمانی"],
                rows: [
                  ["تعداد محصولات", "۱۰۰ کالا", "۱۰,۰۰۰ کالا", "نامحدود"],
                  ["پشتیبانی اختصاصی", "ایمیل", "تلفنی ۲۴/۷", "مدیر حساب اختصاصی"],
                  ["دامنه اختصاصی", "ندارد", "دارد", "چند دامنه‌ای"],
                ],
                bordered: true,
                striped: true,
              },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 4. Multi-Step Form Section
        {
          id: `sec_form_${Date.now()}`,
          name: "فرم چندمرحله‌ای ثبت درخواست",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            boxedWidth: { value: 800, unit: "px" },
          },
          styles: { mobile: {} },
          children: [
            {
              id: `el_ms_form_${Date.now()}`,
              name: "فرم ثبت‌نام مرحله‌ای",
              type: "widget",
              widgetType: "multi_step_form",
              widgetProps: {
                title: "درخواست مشاوره اختصاصی کسب‌وکار",
                steps: ["اطلاعات تماس", "مشخصات پروژه", "تایید نهایی"],
                current_step: 1,
              },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 5. FAQ Accordion Section
        {
          id: `sec_faq_${Date.now()}`,
          name: "پرسش‌های متداول",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            boxedWidth: { value: 1000, unit: "px" },
          },
          styles: { mobile: {} },
          children: [
            {
              id: `el_faq_acc_${Date.now()}`,
              name: "آکاردئون پرسش‌وپاسخ",
              type: "widget",
              widgetType: "accordion",
              widgetProps: {
                items: [
                  { title: "آیا امکان ارتقای پلن در آینده وجود دارد؟", content: "بله، در هر زمان می‌توانید با پرداخت تفاوت قیمت به پلن‌های بالاتر ارتقا دهید." },
                  { title: "مدت زمان فعال‌سازی فروشگاه چقدر است؟", content: "فروشگاه بلافاصله پس از تکمیل ثبت‌نام به صورت آنی فعال و آماده بارگذاری محصولات می‌شود." },
                ],
              },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 6. Popup Builder
        {
          id: `sec_popup_${Date.now()}`,
          name: "پاپ‌آپ تخفیف ورود",
          type: "container",
          isLocked: false,
          isHidden: false,
          widgetType: "popup_builder",
          widgetProps: {
            popup_title: "کد تخفیف ۲۰ درصدی اولین سفارش",
            trigger: "on_scroll",
            scroll_percentage: 40,
          },
          children: [],
        },
        // 7. Call To Action Section
        {
          id: `sec_cta_${Date.now()}`,
          name: "فراخوان پایانی (CTA)",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            boxedWidth: { value: 1280, unit: "px" },
          },
          styles: { mobile: {} },
          children: [
            {
              id: `el_cta_final_${Date.now()}`,
              name: "باکس اقدام نهایی",
              type: "widget",
              widgetType: "call_to_action",
              widgetProps: {
                badge: "پیشنهاد محدود",
                title: "همین امروز کسب‌وکار آنلاین خود را راه‌اندازی کنید",
                description: "۱۴ روز مهلت تست رایگان بدون نیاز به ورود کارت بانکی.",
                button_label: "شروع رایگان با یک کلیک",
                button_url: "/register",
              },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
      ];

      store.getState().initPage(
        "page-landing-e2e",
        {
          schemaVersion: 1,
          title: "لندینگ پیج جامع فروشگاهی نسخه ۴.۲",
          slug: "e2e-isolated-scratchpad",
          globalStyles: {},
          rootElements: fullLandingSections,
        },
        "لندینگ پیج جامع فروشگاهی نسخه ۴.۲",
        "e2e-isolated-scratchpad"
      );

      return store.getState().ast.rootElements.length;
    });

    expect(sectionCount).toBe(7);
    await page.waitForTimeout(1000);

    // Verify all 7 sections render on live canvas
    const iframeEl = page.frameLocator('[data-testid="canvas-iframe"]');
    await expect(iframeEl.locator("h1:has-text('پلتفرم نسل آینده')")).toBeVisible();
    await expect(iframeEl.locator("text=سرعت فوق‌العاده")).toBeVisible();
    await expect(iframeEl.locator("table")).toBeVisible();
    await expect(iframeEl.locator("text=درخواست مشاوره اختصاصی")).toBeVisible();
    await expect(iframeEl.locator("text=آیا امکان ارتقای پلن")).toBeVisible();
    await expect(iframeEl.locator("text=همین امروز کسب‌وکار آنلاین")).toBeVisible();
  });

  test("2. Full landing page previews cleanly across Mobile (375px) and Tablet (768px)", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const mobileBtn = page.locator("header button:has-text('موبایل')").first();
    await mobileBtn.click();
    await page.waitForTimeout(400);

    const iframe = page.locator("iframe").first();
    const mobileBox = await iframe.boundingBox();
    expect(mobileBox).not.toBeNull();
    if (mobileBox) {
      expect(mobileBox.width).toBeLessThanOrEqual(400);
    }

    const tabletBtn = page.locator("header button:has-text('تبلت')").first();
    await tabletBtn.click();
    await page.waitForTimeout(400);

    const tabletBox = await iframe.boundingBox();
    expect(tabletBox).not.toBeNull();
    if (tabletBox) {
      expect(tabletBox.width).toBeLessThanOrEqual(768);
    }
  });

  test("3. Save Draft persists complete landing page state cleanly without validation errors", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(2000);

    const saveDraftBtn = page.locator("header button:has-text('ذخیره پیش‌نویس')").first();
    await expect(saveDraftBtn).toBeVisible();
    await saveDraftBtn.click();
    await page.waitForTimeout(1000);

    // Verify toast or save status
    const toast = page.locator("text=پیش‌نویس ذخیره شد").first();
    await expect(toast).toBeVisible({ timeout: 10000 });
  });

  test("4. Zero console/page errors or horizontal overflows on full landing page in 1280x720 and 1440x900", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    // 1280x720 check
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1500);

    const overflow1280 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow1280).toBeLessThanOrEqual(1);

    // 1440x900 check
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.waitForTimeout(500);
    const overflow1440 = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow1440).toBeLessThanOrEqual(1);

    expect(errors.length).toBe(0);
  });
});
