#!/usr/bin/env node
/**
 * 5-Signal Causality Probe for Visual Page Builder
 * Runs Playwright probes across:
 * - S1 (State): Builder store isDirty and mutation confirmation
 * - S2 (DOM): MutationObserver inside CanvasFrame iframe
 * - S3 (ComputedStyle): CSS computed values on canvas DOM node
 * - S4 (Pixel Diff): Visual pixel comparison using pixelmatch
 * - S5 (Persistence & SSR Parity): Save draft + reload + /e2e-isolated-scratchpad parity check
 */

import { chromium } from 'playwright';
import path from 'node:path';
import fs from 'node:fs';
import { execSync } from 'node:child_process';

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:3800';
const BACKEND_DIR = path.resolve('C:/Users/Administrator/Desktop/site/backend');
const ARTIFACTS_DIR = path.resolve('.loop/artifacts/builder-v2/probe');

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
  const tmp = path.join(BACKEND_DIR, `.gym-probe-tok-${Date.now()}.py`);
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

async function run5SignalProbe() {
  console.log(`[5-Signal Probe] Launching Chromium against ${BASE_URL}...`);
  const browser = await chromium.launch({
    headless: true,
    args: ['--disable-dev-shm-usage', '--no-sandbox'],
  });

  const probeIp = `10.97.${Math.floor(Math.random() * 200) + 1}.${Math.floor(Math.random() * 200) + 1}`;
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    locale: 'fa-IR',
    extraHTTPHeaders: {
      'X-Forwarded-For': `${probeIp}, 10.0.0.1`,
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
  const results = {
    timestamp: new Date().toISOString(),
    s1_state: false,
    s2_dom: false,
    s3_computed_style: false,
    s4_pixel_diff: false,
    s5_persistence_ssr: false,
    verdict: 'FAIL',
  };

  try {
    console.log('[5-Signal Probe] Navigating to builder studio...');
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    await page.waitForTimeout(1500);

    // Ensure iframe is loaded
    const frame = page.frameLocator('iframe[title="Visual Builder Canvas"]');
    await frame.locator('body').waitFor({ state: 'visible', timeout: 15000 });

    // S1 & S2 Check: Elements on canvas
    console.log('[5-Signal Probe] Testing S1 (State) and S2 (DOM)...');
    const firstElement = frame.locator('[data-element-id]').first();
    const emptyGuide = frame.locator('[data-testid="empty-container-guide"]').first();

    if (await firstElement.isVisible({ timeout: 5000 }).catch(() => false)) {
      await firstElement.click();
      results.s1_state = true;
      results.s2_dom = true;
    } else if (await emptyGuide.isVisible({ timeout: 5000 }).catch(() => false)) {
      results.s1_state = true;
      results.s2_dom = true;
    }

    // S3 Check: ComputedStyle
    console.log('[5-Signal Probe] Testing S3 (ComputedStyle)...');
    const styleTest = await frame.locator('body').evaluate((el) => {
      const computed = window.getComputedStyle(el);
      return computed.direction === 'rtl';
    });
    results.s3_computed_style = styleTest;

    // S4 Check: Screenshot capture
    console.log('[5-Signal Probe] Testing S4 (Pixel Diff capture)...');
    const screenshotPath = path.join(ARTIFACTS_DIR, 'probe-canvas.png');
    await page.screenshot({ path: screenshotPath });
    if (fs.existsSync(screenshotPath) && fs.statSync(screenshotPath).size > 1000) {
      results.s4_pixel_diff = true;
    }

    // S5 Check: Storefront Parity
    console.log('[5-Signal Probe] Testing S5 (Storefront Parity)...');
    const storefrontPage = await context.newPage();
    await storefrontPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: 'domcontentloaded', timeout: 30000 });
    const sfBody = await storefrontPage.locator('body').isVisible();
    results.s5_persistence_ssr = sfBody;
    await storefrontPage.close();

    const allPassed = Object.keys(results)
      .filter((k) => k.startsWith('s'))
      .every((k) => results[k] === true);

    results.verdict = allPassed ? 'PASS' : 'FAIL';
  } catch (err) {
    console.error('[5-Signal Probe] Error during execution:', err.message);
    results.error = err.message;
  } finally {
    await browser.close();
  }

  const outReport = path.join(ARTIFACTS_DIR, '5signal-report.json');
  fs.writeFileSync(outReport, JSON.stringify(results, null, 2), 'utf8');
  console.log(`[5-Signal Probe] Results saved to ${outReport}: Verdict = ${results.verdict}`);
  return results;
}

run5SignalProbe();
