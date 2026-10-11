/* Capture visual proof screenshots of the tax-rate flow. */
const { chromium } = require("@playwright/test");
const path = require("path");

const OUT = path.join(__dirname, "__screenshots__");

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });

  // Login as admin
  await page.goto("http://localhost:3000/login");
  await page.getByPlaceholder("۰۹۱۲۳۴۵۶۷۸۹").fill("09120000000");
  await page.getByPlaceholder("••••••••").fill("Admin@123456");
  await page.getByRole("button", { name: /ورود به حساب کاربری/ }).click();
  await page.waitForURL((u) => !u.pathname.includes("/login"), { timeout: 30000 });
  await page.waitForTimeout(2000);

  // 1. Admin settings financial tab
  await page.goto("http://localhost:3000/admin/settings");
  await page.getByRole("tab", { name: /مالی و پرداخت/ }).click();
  await page.waitForTimeout(3000);
  await page.screenshot({ path: path.join(OUT, "tax-1-admin-settings.png") });
  console.log("shot 1: admin settings financial tab");

  // Check sidebar has no tax engine
  const taxLink = await page.getByRole("link", { name: /موتور مالیات/ }).count();
  console.log("sidebar «موتور مالیات» links:", taxLink);

  // 2. Add product to cart (guest in the same browser context keeps the cart)
  await page.goto("http://localhost:3000/products");
  const links = page.locator('a[href^="/products/"]');
  await links.first().waitFor({ state: "visible", timeout: 60000 });
  const hrefs = (
    await links.evaluateAll((els) =>
      els.map((el) => el.getAttribute("href")).filter(Boolean),
    )
  ).slice(0, 10);

  let added = false;
  for (const href of hrefs) {
    await page.goto("http://localhost:3000" + href);
    const btn = page.getByRole("button", { name: /افزودن به سبد خرید/ }).first();
    try {
      await btn.waitFor({ state: "visible", timeout: 15000 });
      await btn.click();
      added = true;
      console.log("added product:", href);
      break;
    } catch {
      /* out of stock */
    }
  }
  console.log("product added:", added);

  // 3. Cart page with VAT label
  await page.goto("http://localhost:3000/cart");
  await page.waitForTimeout(4000);
  await page.screenshot({ path: path.join(OUT, "tax-2-cart.png"), fullPage: true });
  const vatText = await page
    .getByText(/مالیات بر ارزش افزوده/)
    .first()
    .innerText()
    .catch(() => "(no VAT row)");
  console.log("cart VAT row:", vatText.replace(/\n/g, " "));

  // 4. Checkout
  await page.goto("http://localhost:3000/checkout");
  await page.waitForTimeout(6000);
  await page.screenshot({ path: path.join(OUT, "tax-3-checkout.png") });
  console.log("checkout captured");

  await browser.close();
  console.log("DONE");
})();
