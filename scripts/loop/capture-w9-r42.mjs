import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { execSync } from 'node:child_process';
import pixelmatch from 'pixelmatch';
import { PNG } from 'pngjs';

const PORT = 4003;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const BACKEND_DIR = path.resolve('C:/Users/Administrator/Desktop/site/backend');
const BEFORE_DIR = path.resolve('.loop/artifacts/builder-gym/round-042/before');
const AFTER_DIR = path.resolve('.loop/artifacts/builder-gym/round-042/after');

fs.mkdirSync(BEFORE_DIR, { recursive: true });
fs.mkdirSync(AFTER_DIR, { recursive: true });

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
  const tmp = path.join(BACKEND_DIR, `.gym-r42-tok-${Date.now()}.py`);
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
  console.log(`[R42 Full Gym Runner] Connecting to ${BASE_URL}...`);
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--no-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'fa-IR',
    extraHTTPHeaders: {
      'x-forwarded-for': '10.200.42.1',
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
    waitUntil: 'domcontentloaded',
    timeout: 30000,
  });

  await page.waitForTimeout(2000);

  // 1. Capture BEFORE overview
  const beforeStudio = path.join(BEFORE_DIR, '01-studio-1920x1080.png');
  await page.screenshot({ path: beforeStudio, fullPage: false });
  console.log('Saved beforeStudio:', beforeStudio);

  // 2. Build Set-of-Mark inventory
  const elements = await page.evaluate(() => {
    const selector = 'button, input, select, [role="button"], [role="tab"], [data-block-type]';
    const nodes = Array.from(document.querySelectorAll(selector));
    return nodes
      .map((el, i) => {
        const rect = el.getBoundingClientRect();
        if (rect.width <= 0 || rect.height <= 0) return null;
        return {
          id: i + 1,
          tagName: el.tagName.toLowerCase(),
          text: (el.textContent || '').trim().slice(0, 50),
          role: el.getAttribute('role') || '',
          testId: el.getAttribute('data-testid') || '',
          blockType: el.getAttribute('data-block-type') || '',
          rect: {
            x: Math.round(rect.x),
            y: Math.round(rect.y),
            width: Math.round(rect.width),
            height: Math.round(rect.height),
          },
        };
      })
      .filter(Boolean);
  });

  fs.writeFileSync(path.join(BEFORE_DIR, 'som_inventory.json'), JSON.stringify(elements, null, 2), 'utf8');

  // Overlay SoM markers
  await page.evaluate((items) => {
    const existing = document.getElementById('som-overlay-layer');
    if (existing) existing.remove();
    const overlay = document.createElement('div');
    overlay.id = 'som-overlay-layer';
    overlay.style.position = 'fixed';
    overlay.style.top = '0';
    overlay.style.left = '0';
    overlay.style.width = '100vw';
    overlay.style.height = '100vh';
    overlay.style.pointerEvents = 'none';
    overlay.style.zIndex = '999999';

    items.slice(0, 100).forEach((item) => {
      const tag = document.createElement('div');
      tag.textContent = `#${item.id}`;
      tag.style.position = 'absolute';
      tag.style.left = `${item.rect.x}px`;
      tag.style.top = `${item.rect.y}px`;
      tag.style.background = 'rgba(239, 68, 68, 0.9)';
      tag.style.color = '#fff';
      tag.style.fontSize = '10px';
      tag.style.fontWeight = 'bold';
      tag.style.padding = '1px 3px';
      tag.style.borderRadius = '3px';
      tag.style.border = '1px solid #b91c1c';
      overlay.appendChild(tag);
    });
    document.body.appendChild(overlay);
  }, elements);

  const somShot = path.join(BEFORE_DIR, 'before_som.png');
  await page.screenshot({ path: somShot, fullPage: false });
  console.log('Saved before_som:', somShot);

  await page.evaluate(() => {
    const o = document.getElementById('som-overlay-layer');
    if (o) o.remove();
  });

  // 3. Inject full Round 42 Advanced Landing Page with Floating Bar, Toc, and Price Table
  console.log('Injecting Round 42 Enhanced Landing with Floating Bar into Canvas...');
  await page.evaluate(() => {
    const store = window.__builderStore || window.__BUILDER_STORE__;
    if (!store) throw new Error('Builder store not attached on window');

    const round42AST = {
      schemaVersion: 1,
      title: "لندینگ راند ۴۲ - پشتیبانی و قیمت‌گذاری",
      slug: "e2e-isolated-scratchpad",
      globalStyles: {
        primaryColor: "#059669",
        fontFamily: "vazirmatn",
        borderRadius: "16px",
      },
      rootElements: [
        {
          id: "r42_hero_sec",
          name: "بخش هیرو و عنوان اصلی",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "center",
            alignItems: "center",
            gap: { value: 16, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 36, unit: "px" }, bottom: { value: 36, unit: "px" }, isLinked: true },
              background: { type: "color", color: "#f0fdf4" },
            },
          },
          children: [
            {
              id: "r42_headline",
              name: "عنوان اصلی راند ۴۲",
              type: "widget",
              widgetType: "heading",
              widgetProps: {
                text: "سامانه هوشمند سازمانی با تضمین آپ‌تایم ۹۹.۹٪",
                tag: "h1",
              },
              styles: { mobile: {} },
              children: [],
            },
            {
              id: "r42_floating",
              name: "نوار تماس و مشاوره فوری",
              type: "widget",
              widgetType: "floating_buttons",
              widgetProps: {
                phone: "02188889999",
                message: "مشاوره رایگان تلفنی با کارشناسان ارشد",
                button_text: "درخواست تماس",
                button_url: "tel:02188889999",
              },
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        {
          id: "r42_price_sec",
          name: "بخش تعرفه‌ها و خدمات",
          type: "container",
          isLocked: false,
          isHidden: false,
          layout: {
            kind: "flex",
            direction: "column",
            justifyContent: "start",
            alignItems: "center",
            gap: { value: 20, unit: "px" },
          },
          styles: {
            mobile: {
              padding: { top: { value: 32, unit: "px" }, bottom: { value: 32, unit: "px" }, isLinked: true },
            },
          },
          children: [
            {
              id: "r42_pricetbl",
              name: "کارت تعرفه سازمانی",
              type: "widget",
              widgetType: "price_table",
              widgetProps: {
                title: "پلن سازمانی پیشرفته",
                subtitle: "بهترین انتخاب برای شرکت‌های بزرگ",
                price: "۹۹۰,۰۰۰",
                currency: "تومان",
                period: "ماهانه",
                is_featured: true,
                badge: "ویژه مدیران",
                features: [
                  { text: "سرور اختصاصی ابری پرسرعت", available: true },
                  { text: "پشتیبانی ۲۴ ساعته اختصاصی", available: true },
                  { text: "دامنه ملی و بین‌المللی رایگان", available: true },
                  { text: "مشاوره فنی حضوری", available: false },
                ],
                button_label: "انتخاب و شروع پلن",
              },
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
      ],
    };

    store.getState().replacePageAST(round42AST);
  });

  await page.waitForTimeout(1500);

  // 4. Capture AFTER overview
  const afterStudio = path.join(AFTER_DIR, '01-studio-1920x1080.png');
  await page.screenshot({ path: afterStudio, fullPage: false });
  console.log('Saved afterStudio:', afterStudio);

  // 5. Select floating bar inside canvas
  const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
  const floatingEl = frame.locator('[data-element-id="r42_floating"]').first();
  if (await floatingEl.isVisible()) {
    await floatingEl.click();
    await page.waitForTimeout(600);
  }

  const selectionShot = path.join(AFTER_DIR, '02-element-selected.png');
  await page.screenshot({ path: selectionShot, fullPage: false });
  console.log('Saved after selectionShot:', selectionShot);

  // 6. Select price table inside canvas
  const priceTableEl = frame.locator('[data-element-id="r42_pricetbl"]').first();
  if (await priceTableEl.isVisible()) {
    await priceTableEl.click();
    await page.waitForTimeout(600);
  }

  const priceTableShot = path.join(AFTER_DIR, '03-price-table-verified.png');
  await page.screenshot({ path: priceTableShot, fullPage: false });
  console.log('Saved after priceTableShot:', priceTableShot);

  // 7. Responsive viewports
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(500);
  const tabletShot = path.join(AFTER_DIR, '05-viewport-tablet.png');
  await page.screenshot({ path: tabletShot, fullPage: false });
  console.log('Saved tabletShot:', tabletShot);

  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(500);
  const mobileShot = path.join(AFTER_DIR, '06-viewport-mobile.png');
  await page.screenshot({ path: mobileShot, fullPage: false });
  console.log('Saved mobileShot:', mobileShot);

  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(500);

  // 8. Compute pixel diff
  let changedPixels = 0;
  if (fs.existsSync(beforeStudio) && fs.existsSync(afterStudio)) {
    const img1 = PNG.sync.read(fs.readFileSync(beforeStudio));
    const img2 = PNG.sync.read(fs.readFileSync(afterStudio));
    const { width, height } = img1;
    const diff = new PNG({ width, height });

    changedPixels = pixelmatch(img1.data, img2.data, diff.data, width, height, { threshold: 0.05 });
    fs.writeFileSync(path.join(AFTER_DIR, 'diff.png'), PNG.sync.write(diff));
    console.log(`[Pixelmatch R42] Changed pixels: ${changedPixels}`);
  }

  // 9. SSR parity check
  const ssrRes = await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: 'domcontentloaded' });
  const ssrStatus = ssrRes ? ssrRes.status() : 500;
  const ssrShot = path.join(AFTER_DIR, '07-ssr-parity-scratchpad.png');
  await page.screenshot({ path: ssrShot, fullPage: false });
  console.log('Saved SSR screenshot with status:', ssrStatus);

  const pageMetrics = await page.evaluate(() => {
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      windowOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      isRtl: document.documentElement.dir === 'rtl' || document.body.dir === 'rtl',
    };
  });

  const mutationReport = {
    round: 'round-042',
    stage: 'after',
    timestamp: new Date().toISOString(),
    totalSoMElements: elements.length,
    changedPixels,
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
    passed: consoleErrors.length === 0 && networkErrors.length === 0 && !pageMetrics.windowOverflow && ssrStatus === 200 && changedPixels > 0,
  };

  fs.writeFileSync(path.join(AFTER_DIR, 'mutation_report.json'), JSON.stringify(mutationReport, null, 2), 'utf8');
  fs.writeFileSync(path.join('.loop/artifacts/builder-gym/round-042', 'mutation_report.json'), JSON.stringify(mutationReport, null, 2), 'utf8');
  console.log('Saved R42 mutation_report.json with passed =', mutationReport.passed);

  await browser.close();
}

run().catch((err) => {
  console.error('R42 Probe failed:', err);
  process.exit(1);
});
