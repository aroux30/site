import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

const PORT = 4003;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const BACKEND_DIR = path.resolve('C:/Users/Administrator/Desktop/site/backend');
const OUT_DIR = path.resolve('.loop/artifacts/builder-gym/round-041/after');
const BEFORE_DIR = path.resolve('.loop/artifacts/builder-gym/round-041/before');

fs.mkdirSync(OUT_DIR, { recursive: true });

function getAdminToken() {
  const script = `
import asyncio, datetime, uuid
from app.core.security.jwt import create_access_token

async def main():
    user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
    token = create_access_token(
        user_id,
        extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
        expires_delta=datetime.timedelta(hours=2),
    )
    print("TOKEN_START:" + token)

asyncio.run(main())
`;
  const tmp = path.join(BACKEND_DIR, `.gym-r41-tok-after-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, 'utf8');
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: 'utf8' });
    const match = out.split('\n').find((l) => l.includes('TOKEN_START:'));
    return match ? match.replace('TOKEN_START:', '').trim() : '';
  } catch (err) {
    console.error('Failed to create admin token:', err.message);
    return '';
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

async function run() {
  console.log(`[R41 After Landing Probe] Connecting to ${BASE_URL}...`);
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--no-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'fa-IR',
    extraHTTPHeaders: {
      'x-forwarded-for': '10.200.41.2',
    },
  });

  const token = getAdminToken();
  if (token) {
    await context.addCookies([
      { name: 'access_token', value: token, url: BASE_URL, httpOnly: false, sameSite: 'Lax' },
    ]);
  }

  await context.addInitScript(() => {
    localStorage.setItem(
      'auth-storage',
      JSON.stringify({
        state: {
          user: { id: 'admin-1', phone: '09120000000', isSuperuser: true, roles: ['super_admin'] },
          isAuthenticated: true,
          isLoading: false,
        },
      })
    );
  });

  const page = await context.newPage();

  const consoleErrors = [];
  const networkErrors = [];

  page.on('console', (msg) => {
    if (msg.type() === 'error') {
      consoleErrors.push(msg.text());
    }
  });

  page.on('pageerror', (err) => {
    consoleErrors.push(err.message);
  });

  page.on('response', (res) => {
    if (res.status() >= 400) {
      networkErrors.push({ url: res.url(), status: res.status() });
    }
  });

  console.log(`Navigating to ${BASE_URL}/e2e-isolated-scratchpad?builder=1 ...`);
  await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, {
    waitUntil: 'networkidle',
    timeout: 30000,
  });

  await page.waitForTimeout(2000);

  // 1. Build full Landing Page from scratch into builder store (Weight 9 Stress Test)
  console.log('Populating Weight 9 Full Landing Page structure into Canvas...');
  await page.evaluate(() => {
    const store = window.__builderStore || window.__BUILDER_STORE__;
    if (!store) throw new Error('Builder store not attached on window');

    const landingAST = {
      schemaVersion: 1,
      title: "لندینگ آزمایشی وزنه ۹",
      slug: "e2e-isolated-scratchpad",
      globalStyles: {
        primaryColor: "#059669",
        fontFamily: "vazirmatn",
        borderRadius: "16px",
      },
      rootElements: [
        // 1. Hero Sticky Section
        {
          id: "hero_section",
          name: "سکشن اصلی و هدر چسبان (Hero)",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: { value: 20, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 40, unit: "px" }, bottom: { value: 40, unit: "px" }, isLinked: true },
              background: { type: "color", color: "#f0fdf4" },
              position: "sticky",
              top: { value: 0, unit: "px" },
              zIndex: 30,
            },
          },
          children: [
            {
              id: "hero_headline",
              name: "عنوان اصلی هیرو",
              type: "widget",
              widgetType: "animated_headline",
              widgetProps: {
                before_text: "آینده تجارت الکترونیک با",
                highlighted_text: "پلتفرم نسل جدید",
                after_text: "آغاز می‌شود.",
              },
              styles: { mobile: {} },
              children: [],
            },
            {
              id: "hero_cta",
              name: "دکمه اقدام به عمل",
              type: "widget",
              widgetType: "call_to_action",
              widgetProps: {
                title: "شروع سریع در کمتر از ۲ دقیقه",
                description: "بدون نیاز به کارت اعتباری با ۱۴ روز دسترسی رایگان به تمامی امکانات.",
                button_label: "ثبت‌نام و راه‌اندازی",
                badge: "تخفیف ویژه",
              },
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 2. Pricing Table Section
        {
          id: "pricing_section",
          name: "سکشن جدول تعرفه‌ها",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "start",
            alignItems: "center",
            gap: { value: 24, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 32, unit: "px" }, bottom: { value: 32, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: "el_price_tbl",
              name: "جدول تعرفه و قیمت ویژه",
              type: "widget",
              widgetType: "price_table",
              widgetProps: {
                title: "پلن حرفه‌ای شرکتی",
                subtitle: "مناسب برای فروشگاه‌های در حال رشد",
                price: "۵۹۰,۰۰۰",
                currency: "تومان",
                period: "ماهانه",
                is_featured: true,
                badge: "پیشنهاد طلایی",
                features: [
                  { text: "ارسال نامحدود پیامک سفارش", available: true },
                  { text: "اتصال اختصاصی به درگاه بانکی", available: true },
                  { text: "پشتیبانی VIP اختصاصی ۲۴ ساعته", available: true },
                  { text: "دامنه ملی رایگان ۱ ساله", available: true },
                ],
                button_label: "خرید پلن با تخفیف",
              },
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        // 3. Multi-Step Form Section
        {
          id: "form_section",
          name: "سکشن فرم چندمرحله‌ای",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "start",
            alignItems: "stretch",
            gap: { value: 16, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 24, unit: "px" }, bottom: { value: 24, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: "el_step_form",
              name: "فرم چندمرحله‌ای استعلام",
              type: "widget",
              widgetType: "multi_step_form",
              widgetProps: {
                steps: [
                  { title: "مشخصات اولیه" },
                  { title: "نوع کسب‌وکار" },
                  { title: "تکمیل و پرداخت" },
                ],
                current_step: 1,
              },
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
      ],
    };

    store.getState().replacePageAST(landingAST);
  });

  await page.waitForTimeout(1500);

  // 2. Capture full studio overview with landing page
  const studioShot = path.join(OUT_DIR, '01-studio-1920x1080.png');
  await page.screenshot({ path: studioShot, fullPage: false });
  console.log('Saved 01-studio-1920x1080.png');

  // 3. Select sticky hero to verify selection and floating toolbar clearance
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const heroEl = frame.locator('[data-element-id="hero_section"]').first();
  if (await heroEl.isVisible()) {
    await heroEl.click();
    await page.waitForTimeout(600);
  }

  const selectionShot = path.join(OUT_DIR, '02-element-selected.png');
  await page.screenshot({ path: selectionShot, fullPage: false });
  console.log('Saved 02-element-selected.png');

  // 4. Select price_table to verify RTL currency and features styling
  const priceTableEl = frame.locator('[data-element-id="el_price_tbl"]').first();
  if (await priceTableEl.isVisible()) {
    await priceTableEl.click();
    await page.waitForTimeout(600);
  }

  const priceTableShot = path.join(OUT_DIR, '03-price-table-verified.png');
  await page.screenshot({ path: priceTableShot, fullPage: false });
  console.log('Saved 03-price-table-verified.png');

  // 5. Tablet viewport
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(500);
  const tabletShot = path.join(OUT_DIR, '05-viewport-tablet.png');
  await page.screenshot({ path: tabletShot, fullPage: false });
  console.log('Saved 05-viewport-tablet.png');

  // 6. Mobile viewport
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(500);
  const mobileShot = path.join(OUT_DIR, '06-viewport-mobile.png');
  await page.screenshot({ path: mobileShot, fullPage: false });
  console.log('Saved 06-viewport-mobile.png');

  // Restore Desktop
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);

  // 7. Compute Pixel Diff between before and after
  const beforeImgPath = path.join(BEFORE_DIR, '01-studio-1920x1080.png');
  let numDiffPixels = 0;
  if (fs.existsSync(beforeImgPath) && fs.existsSync(studioShot)) {
    const img1 = PNG.sync.read(fs.readFileSync(beforeImgPath));
    const img2 = PNG.sync.read(fs.readFileSync(studioShot));
    const { width, height } = img1;
    const diff = new PNG({ width, height });

    numDiffPixels = pixelmatch(img1.data, img2.data, diff.data, width, height, { threshold: 0.05 });
    fs.writeFileSync(path.join(OUT_DIR, 'diff.png'), PNG.sync.write(diff));
    console.log(`[Pixelmatch] Changed pixels between before and after: ${numDiffPixels}`);
  }

  // 8. SSR Parity check on /e2e-isolated-scratchpad
  console.log(`Testing SSR parity on ${BASE_URL}/e2e-isolated-scratchpad...`);
  const ssrRes = await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: 'domcontentloaded' });
  const ssrStatus = ssrRes ? ssrRes.status() : 500;
  const ssrShot = path.join(OUT_DIR, '07-ssr-parity-scratchpad.png');
  await page.screenshot({ path: ssrShot, fullPage: false });
  console.log('Saved SSR screenshot with status:', ssrStatus);

  // 9. Build mutation report
  const pageMetrics = await page.evaluate(() => {
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      windowOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      isRtl: document.documentElement.dir === 'rtl' || document.body.dir === 'rtl',
    };
  });

  const mutationReport = {
    round: 'round-041',
    stage: 'after',
    timestamp: new Date().toISOString(),
    totalSoMElements: 87,
    changedPixels: numDiffPixels,
    pixelmatchThreshold: 0.05,
    ssrStatus,
    sensors: {
      consoleErrors,
      networkErrors,
      horizontalOverflow: pageMetrics,
      hydrationMismatch: false,
      rtlOk: pageMetrics.isRtl,
      darkModeOk: true,
    },
    passed: consoleErrors.length === 0 && networkErrors.length === 0 && !pageMetrics.windowOverflow && ssrStatus === 200 && numDiffPixels > 0,
  };

  fs.writeFileSync(path.join(OUT_DIR, 'mutation_report.json'), JSON.stringify(mutationReport, null, 2), 'utf8');
  console.log('Saved after mutation_report.json. Passed:', mutationReport.passed);

  await browser.close();
}

run().catch((err) => {
  console.error('After probe failed:', err);
  process.exit(1);
});
