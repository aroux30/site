/**
 * Visual check for the live-chat widget + admin console.
 *
 * Drives a real Chromium against the running preview (port 3100): opens the
 * storefront, opens the widget, exercises tabs, sends a message; then logs in
 * as a real admin and opens /admin/chat, screenshots the console and settings.
 * Captures console errors and failed requests so a broken surface is visible.
 */
const { chromium } = require("playwright");

const BASE = "http://localhost:3100";
const OUT = ".claude/chat-shots";

async function main() {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
  const errors = [];
  const page = await ctx.newPage();
  page.on("console", (m) => {
    if (m.type() === "error") errors.push(`console: ${m.text().slice(0, 200)}`);
  });
  page.on("requestfailed", (r) => errors.push(`reqfail: ${r.url().slice(0, 120)}`));

  // 1. Storefront — widget present?
  await page.goto(BASE + "/", { waitUntil: "networkidle", timeout: 60000 });
  await page.waitForTimeout(2500);
  // The Next.js dev overlay (nextjs-portal) intercepts clicks; report its text
  // if present (it flags a real compile/runtime error), then force through it.
  const overlayText = await page
    .locator("nextjs-portal")
    .first()
    .textContent()
    .catch(() => "");
  if (overlayText && overlayText.trim()) {
    console.log("NEXT DEV OVERLAY TEXT:", overlayText.slice(0, 400));
  }
  const toggle = page.locator('button[aria-label="گفتگوی زنده"], button[aria-label="بستن گفتگو"]').first();
  const hasWidget = (await toggle.count()) > 0;
  console.log("widget toggle present:", hasWidget);
  await page.screenshot({ path: `${OUT}/01-storefront-widget-closed.png` });

  if (hasWidget) {
    await toggle.click({ force: true });
    await page.waitForTimeout(1500);
    await page.screenshot({ path: `${OUT}/02-widget-open.png` });

    // Tabs
    for (const [label, name] of [["سوالات", "faqs"], ["اخبار", "news"]]) {
      const tab = page.locator(`button:has-text("${label}")`).last();
      if (await tab.count()) {
        await tab.click({ force: true });
        await page.waitForTimeout(1000);
        await page.screenshot({ path: `${OUT}/03-tab-${name}.png` });
      }
    }

    // Go to chat: click the "گفتگو" tab, then "شروع گفتگو" if the welcome CTA shows.
    const chatTab = page.locator('button:has-text("گفتگو")').last();
    if (await chatTab.count()) {
      await chatTab.click({ force: true });
      await page.waitForTimeout(800);
    }
    const startBtn = page.locator('button:has-text("شروع گفتگو")').first();
    if (await startBtn.count()) {
      await startBtn.click({ force: true });
      await page.waitForTimeout(1500);
      await page.screenshot({ path: `${OUT}/04a-prechat-form.png` });
      // Fill any pre-chat fields and submit.
      const formInputs = page.locator('form input, form textarea');
      const n = await formInputs.count();
      for (let i = 0; i < n; i++) {
        await formInputs.nth(i).fill("تست").catch(() => {});
      }
      const submit = page.locator('form button[type="submit"]').first();
      if (await submit.count()) {
        await submit.click({ force: true });
        await page.waitForTimeout(1500);
      }
    }

    // Send a message
    const input = page.locator('input[placeholder="پیام خود را بنویسید..."]').first();
    if (await input.count()) {
      await input.fill("سلام، این یک پیام تستی است");
      await page.keyboard.press("Enter");
      await page.waitForTimeout(3000);
      await page.screenshot({ path: `${OUT}/04-message-sent.png` });
      console.log("message sent");
    } else {
      console.log("composer input not found");
      await page.screenshot({ path: `${OUT}/04-no-composer.png` });
    }
  }

  // 2. Admin console — real login (phone + password)
  const admin = await ctx.newPage();
  admin.on("console", (m) => {
    if (m.type() === "error") errors.push(`admin console: ${m.text().slice(0, 200)}`);
  });
  await admin.goto(BASE + "/login", { waitUntil: "networkidle", timeout: 60000 });
  await admin.waitForTimeout(1500);
  const phoneInput = admin.locator('input[type="tel"], input[inputmode="tel"]').first();
  const pwInput = admin.locator('input[type="password"]').first();
  if ((await phoneInput.count()) && (await pwInput.count())) {
    await phoneInput.fill("09120000000");
    await pwInput.fill("Admin@123456");
    await admin.screenshot({ path: `${OUT}/05-login-filled.png` });
    // The password form's own submit button (not the OTP form's).
    const loginBtn = admin.locator('form:has(input[type="password"]) button[type="submit"]').first();
    console.log("login button count:", await loginBtn.count());
    await loginBtn.click({ force: true }).catch((e) => console.log("click err:", e.message));
    await admin.waitForTimeout(6000);
    console.log("after login url:", admin.url());
    await admin.screenshot({ path: `${OUT}/06-after-login.png` });
  } else {
    console.log("login inputs not found (phone:", await phoneInput.count(), "pw:", await pwInput.count(), ")");
  }

  // Admin chat console
  await admin.goto(BASE + "/admin/chat", { waitUntil: "networkidle", timeout: 60000 });
  await admin.waitForTimeout(3500);
  console.log("admin chat url:", admin.url());
  await admin.screenshot({ path: `${OUT}/07-admin-chat.png` });
  // Settings tab
  const settingsTab = admin.locator('button:has-text("تنظیمات")').first();
  if (await settingsTab.count()) {
    await settingsTab.click({ force: true });
    await admin.waitForTimeout(2000);
    await admin.screenshot({ path: `${OUT}/08-admin-settings.png` });
  }
  // Online tab
  const onlineTab = admin.locator('button:has-text("کاربران آنلاین")').first();
  if (await onlineTab.count()) {
    await onlineTab.click({ force: true });
    await admin.waitForTimeout(2000);
    await admin.screenshot({ path: `${OUT}/09-admin-online.png` });
  }

  await browser.close();
  console.log("\n--- console/network errors ---");
  console.log(errors.length ? errors.slice(0, 20).join("\n") : "(none)");
}

main().catch((e) => {
  console.error("FAILED:", e.message);
  process.exit(1);
});
