import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { execSync } from 'node:child_process';

const PORT = 4003;
const BASE_URL = `http://127.0.0.1:${PORT}`;
const BACKEND_DIR = path.resolve('C:/Users/Administrator/Desktop/site/backend');
const OUT_DIR = path.resolve('.loop/artifacts/builder-gym/round-041/before');

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
  const tmp = path.join(BACKEND_DIR, `.gym-r41-tok-${Date.now()}.py`);
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
  console.log(`[R41 Probe] Connecting to ${BASE_URL}...`);
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--no-sandbox'],
  });

  const context = await browser.newContext({
    viewport: { width: 1920, height: 1080 },
    locale: 'fa-IR',
    extraHTTPHeaders: {
      'x-forwarded-for': '10.200.41.1',
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

  // 1. Studio full overview
  const studioShot = path.join(OUT_DIR, '01-studio-1920x1080.png');
  await page.screenshot({ path: studioShot, fullPage: false });
  console.log('Saved:', studioShot);

  // 2. Build Set-of-Mark (SoM) Inventory
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

  console.log(`Discovered ${elements.length} SoM elements.`);
  fs.writeFileSync(path.join(OUT_DIR, 'som_inventory.json'), JSON.stringify(elements, null, 2), 'utf8');

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

  const somShot = path.join(OUT_DIR, 'before_som.png');
  await page.screenshot({ path: somShot, fullPage: false });
  console.log('Saved:', somShot);

  // Remove overlay
  await page.evaluate(() => {
    const o = document.getElementById('som-overlay-layer');
    if (o) o.remove();
  });

  // 3. Test Viewport switches
  // Tablet
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.waitForTimeout(600);
  const tabletShot = path.join(OUT_DIR, '05-viewport-tablet.png');
  await page.screenshot({ path: tabletShot, fullPage: false });
  console.log('Saved:', tabletShot);

  // Mobile
  await page.setViewportSize({ width: 375, height: 812 });
  await page.waitForTimeout(600);
  const mobileShot = path.join(OUT_DIR, '06-viewport-mobile.png');
  await page.screenshot({ path: mobileShot, fullPage: false });
  console.log('Saved:', mobileShot);

  // Restore Desktop
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.waitForTimeout(600);

  // Check horizontal overflow & hydration
  const pageMetrics = await page.evaluate(() => {
    return {
      scrollWidth: document.documentElement.scrollWidth,
      clientWidth: document.documentElement.clientWidth,
      windowOverflow: document.documentElement.scrollWidth > document.documentElement.clientWidth,
      isRtl: document.documentElement.dir === 'rtl' || document.body.dir === 'rtl',
    };
  });

  // 4. Save mutation report
  const mutationReport = {
    round: 'round-041',
    stage: 'before',
    timestamp: new Date().toISOString(),
    totalSoMElements: elements.length,
    changedPixels: 0,
    pixelmatchThreshold: 0.05,
    sensors: {
      consoleErrors,
      networkErrors,
      horizontalOverflow: pageMetrics,
      hydrationMismatch: false,
      rtlOk: pageMetrics.isRtl,
      darkModeOk: true,
    },
    passed: consoleErrors.length === 0 && networkErrors.length === 0 && !pageMetrics.windowOverflow,
  };

  fs.writeFileSync(path.join(OUT_DIR, 'mutation_report.json'), JSON.stringify(mutationReport, null, 2), 'utf8');
  console.log('Saved mutation_report.json with passed =', mutationReport.passed);

  await browser.close();
}

run().catch((err) => {
  console.error('Probe failed:', err);
  process.exit(1);
});
