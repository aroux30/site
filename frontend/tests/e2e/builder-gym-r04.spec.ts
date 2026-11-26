import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { resetE2EPage } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const BACKEND_DIR = path.resolve("C:/Users/Administrator/Desktop/site/backend");

function getAdminToken() {
  const script = `
import datetime, uuid
from app.core.security.jwt import create_access_token
user_id = str(uuid.UUID("47f274da-3abd-4d91-bc9c-83ba913fc66f"))
print("TOKEN_START:" + create_access_token(
    user_id,
    extra_claims={"roles": ["super_admin"], "is_superuser": True, "permissions": ["*"]},
    expires_delta=datetime.timedelta(hours=2),
))
`;
  const tmp = path.join(BACKEND_DIR, `.gym-r04-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 04: Weight 2 Batch 3 (12 Shop Widgets + SSR Runtime Parity)", () => {
  test.beforeEach(async ({ context }) => {
    await resetE2EPage("e2e-isolated-scratchpad");
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
          state: {
            user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] },
            isAuthenticated: true,
            isLoading: false,
          },
        })
      );
    });
  });

  test("1. All 12 shop widgets insert with zero 404s, nudge in Inspector, persist on reload, and match interactive SSR output", async ({ page }) => {
    test.setTimeout(90000);
    const errors: string[] = [];
    const failedUrls: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (msg) => {
      if (msg.type() === "error") errors.push(msg.text());
    });
    page.on("response", (res) => {
      if (res.status() >= 400 && !res.url().includes("favicon")) {
        failedUrls.push(`${res.status()} ${res.url()}`);
      }
    });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="builder-toolbar-header"]', { timeout: 15000 });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await page.waitForSelector('iframe[data-testid="canvas-iframe"]', { timeout: 15000 });

    await page.evaluate(() => {
      const st = (window as any).__builderStore.getState();
      st.initPage(st.pageId, { ...st.ast, rootElements: [] }, st.ast.title, st.ast.slug);
    });

    const shopWidgets = [
      "product_card",
      "product_grid",
      "image_gallery",
      "star_rating",
      "review_histogram",
      "recently_viewed",
      "mega_menu",
      "product_price",
      "product_variants",
      "add_to_cart",
      "mini_cart",
      "cart_summary",
    ];

    for (const w of shopWidgets) {
      await page.evaluate(() => (window as any).__builderStore.getState().selectElement(null));
      const card = page.locator(`button[data-block-type="${w}"]`).first();
      await card.scrollIntoViewIfNeeded();
      await card.click();
    }

    // Zero broken assets (no /placeholder.svg 404s)
    expect(failedUrls).toEqual([]);

    const idMap = await page.evaluate(() => {
      const m: Record<string, string> = {};
      for (const el of (window as any).__builderStore.getState().ast.rootElements) {
        if (el.widgetType) m[el.widgetType] = el.id;
      }
      return m;
    });
    for (const w of shopWidgets) {
      expect(idMap[w]).toBeTruthy();
    }

    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');

    // 1. product_card
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.product_card);
    await page.locator('[data-testid="product-card-name-input"]').fill("گوشی پرچمدار راند۴");
    await page.locator('[data-testid="product-card-min-price-input"]').fill("4500000");
    await page.locator('[data-testid="product-card-max-price-input"]').fill("5200000");
    await page.locator('[data-testid="product-card-stock-switch"]').click();
    await expect(frame.locator(`[data-element-id="${idMap.product_card}"]`)).toContainText("ناموجود");

    // 2. product_grid (sync filter select -> Canvas pills + pagination switch)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.product_grid);
    await page.locator('[data-testid="product-grid-limit-input"]').fill("2");
    await page.locator('[data-testid="product-grid-filter-select"]').click();
    await page.locator('[role="option"]:has-text("کالاهای ویژه")').click();
    await expect(frame.locator(`[data-element-id="${idMap.product_grid}"]`)).toContainText("کالای ویژه شماره 1");
    await page.locator('[data-testid="product-grid-pagination-switch"]').click();

    // 3. star_rating (toggle showValue OFF + set value 3.7)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.star_rating);
    await page.locator('[data-testid="star-rating-value-input"]').fill("3.7");
    await page.locator('[data-testid="star-rating-reviews-input"]').fill("99");
    await page.locator('[data-testid="star-rating-show-value-switch"]').click();

    // 4. review_histogram
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.review_histogram);
    await page.locator('[data-testid="review-histogram-avg-input"]').fill("4.2");
    await page.locator('[data-testid="review-histogram-total-input"]').fill("310");
    await page.locator('[data-testid="review-histogram-verified-input"]').fill("245");

    // 5. recently_viewed
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.recently_viewed);
    await page.locator('[data-testid="recently-viewed-title-input"]').fill("تازه‌های دیده شده راند۴");
    await page.locator('[data-testid="recently-viewed-limit-input"]').fill("2");

    // 6. mega_menu
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.mega_menu);
    await page.locator('[data-testid="mega-menu-label-input"]').fill("منوی راند۴");

    // 7. product_price (set price, compare_at_price, toggle show_discount OFF)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.product_price);
    await page.locator('[data-testid="product-price-input"]').fill("980000");
    await page.locator('[data-testid="product-compare-price-input"]').fill("1400000");
    await page.locator('[data-testid="product-price-show-discount-switch"]').click();

    // 8. product_variants (rename title & add variant 3)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.product_variants);
    await page.locator('[data-testid="product-variants-title-input"]').fill("رنگ‌بندی راند۴");
    await page.locator('[data-testid="product-variants-add-btn"]').click();
    await page.locator('[data-testid="product-variant-title-2"]').fill("آبی تیتانیوم");

    // 9. add_to_cart (custom label, keep qty stepper visible so we can test stepper on SSR)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.add_to_cart);
    await page.locator('[data-testid="add-to-cart-label-input"]').fill("خرید فوری راند۴");

    // 10. mini_cart (custom label, badge enabled so add_to_cart updates it live on SSR)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.mini_cart);
    await page.locator('[data-testid="mini-cart-label-input"]').fill("کیف خرید راند۴");

    // 11. cart_summary (custom title, button label, checkout url, toggle discount OFF -> verify Canvas hides row!)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.cart_summary);
    await page.locator('[data-testid="cart-summary-title-input"]').fill("فاکتور نهایی راند۴");
    await page.locator('[data-testid="cart-summary-btn-input"]').fill("پرداخت امن راند۴");
    await page.locator('[data-testid="cart-summary-url-input"]').fill("/cart");
    await page.locator('[data-testid="cart-summary-discount-switch"]').click();
    await expect(frame.locator(`[data-element-id="${idMap.cart_summary}"] [data-cs-discount="1"]`)).toHaveCount(0);

    // 12. image_gallery (add 3rd slide using valid SVG)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.image_gallery);
    await page.locator('[data-testid="image-gallery-add-btn"]').click();
    await page.locator('[data-testid="image-gallery-url-1"]').fill("/placeholder-product.svg");

    // Save Draft -> Reload -> Verify persistence -> Publish
    await page.locator("button:has-text('ذخیره پیش‌نویس')").click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("پیش‌نویس", { timeout: 15000 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await expect(frame.locator(`[data-element-id="${idMap.cart_summary}"]`)).toContainText("فاکتور نهایی راند۴", { timeout: 15000 });

    await page.locator('[data-testid="publish-page-btn"]').click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("منتشرشده", { timeout: 15000 });

    // --- Public SSR Interactive & Parity Verification ---
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    const ssrRoot = page.locator(".builder-rendered-content");
    await expect(ssrRoot).toBeVisible({ timeout: 15000 });

    // 1. product_card has del max_price, out of stock disabled btn & compact max-w-sm
    const card = ssrRoot.locator('[data-widget="product_card"]');
    await expect(card.locator("del")).toContainText("تومان");
    await expect(card.locator("button:disabled")).toHaveText("ناموجود");

    // 2. image_gallery thumb click swaps main stage src
    const gal = ssrRoot.locator('[data-widget="image_gallery"]');
    await gal.locator('[data-gallery-thumb="1"]').click();
    await expect(gal.locator('[data-gallery-main="1"]')).toHaveAttribute("src", "/placeholder-product.svg");

    // 3. star_rating renders 5 stars & hides 3.7 score when showValue=false
    const star = ssrRoot.locator('[data-widget="star_rating"]');
    await expect(star.locator("svg")).toHaveCount(5);
    await expect(star).not.toContainText("3.7");

    // 4. review_histogram has 5 bars & verifiedCount
    const hist = ssrRoot.locator('[data-widget="review_histogram"]');
    await expect(hist.locator(".h-2")).toHaveCount(5);
    await expect(hist).toContainText(/(245|۲۴۵) خرید تأییدشده/);

    // 5. recently_viewed reflects custom title & 2 cards
    const recent = ssrRoot.locator('[data-widget="recently_viewed"]');
    await expect(recent).toContainText("تازه‌های دیده شده راند۴");
    await expect(recent.locator("img")).toHaveCount(2);

    // 6. mega_menu toggle opens interactive dropdown panel
    const mega = ssrRoot.locator('[data-widget="mega_menu"]');
    await mega.locator('[data-mega-menu-toggle="1"]').click();
    await expect(mega.locator('[data-mega-menu-panel="1"]')).not.toHaveClass(/hidden/);
    await expect(mega.locator('[data-mega-menu-panel="1"] a').first()).toBeVisible();

    // 7. product_price hides discount when show_discount=false & formats commas
    const price = ssrRoot.locator('[data-widget="product_price"]');
    await expect(price).toContainText("۹۸۰,۰۰۰");
    await expect(price).not.toContainText("تخفیف");

    // 8. product_variants selection updates add_to_cart data-variant-id, stepper & mini_cart live badge
    const variants = ssrRoot.locator('[data-widget="product_variants"]');
    const thirdVarBtn = variants.locator("button[data-variant-id]").nth(2);
    const thirdVarId = await thirdVarBtn.getAttribute("data-variant-id");
    await thirdVarBtn.click();
    await expect(ssrRoot.locator(".builder-add-to-cart")).toHaveAttribute("data-variant-id", thirdVarId || "");

    const atcWrap = ssrRoot.locator('[data-widget="add_to_cart"]');
    await atcWrap.locator('[data-qty-inc="1"]').click();
    await expect(atcWrap.locator('[data-qty-val="1"]')).toHaveText("2");
    await atcWrap.locator(".builder-add-to-cart").click();
    await expect(ssrRoot.locator('[data-widget="mini_cart"] [data-mc-badge="1"]')).toHaveText("2");
    await expect(ssrRoot.locator('[data-widget="mini_cart"]')).toContainText("کیف خرید راند۴");

    // 9. cart_summary respects custom title, btn label, checkout_url, hidden discount
    const cartSum = ssrRoot.locator('[data-widget="cart_summary"]');
    await expect(cartSum).toContainText("فاکتور نهایی راند۴");
    await expect(cartSum.locator('a[href="/cart"]')).toHaveText("پرداخت امن راند۴");
    await expect(cartSum).not.toContainText("تخفیف:");

    // 10. product_grid interactive filter pill click updates data-filter
    const grid = ssrRoot.locator('[data-widget="product_grid"]');
    await expect(grid).toHaveAttribute("data-filter", "featured");
    await grid.locator('[data-grid-filter="best_sellers"]').click();
    await expect(grid).toHaveAttribute("data-filter", "best_sellers");

    expect(failedUrls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
