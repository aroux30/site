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
  const tmp = path.join(BACKEND_DIR, `.gym-r03-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 03: Weight 2 Batch 2 (13 Interactive & Form Widgets + SSR Runtime)", () => {
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

  test("1. All 13 interactive & form widgets insert without errors, nudge in Inspector, persist on reload, and work interactively in SSR", async ({ page }) => {
    test.setTimeout(90000);
    const errors: string[] = [];
    const failedUrls: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        errors.push(msg.text());
      }
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

    // Start from clean root AST
    await page.evaluate(() => {
      const st = (window as any).__builderStore.getState();
      st.initPage(st.pageId, { ...st.ast, rootElements: [] }, st.ast.title, st.ast.slug);
    });

    // 1) Insert form_container and nest the 5 form fields inside it
    await page.evaluate(() => (window as any).__builderStore.getState().selectElement(null));
    const formCard = page.locator('button[data-block-type="form_container"]').first();
    await formCard.scrollIntoViewIfNeeded();
    await formCard.click();

    const formContainerId = await page.evaluate(() => {
      const roots = (window as any).__builderStore.getState().ast.rootElements;
      return roots.find((r: any) => r.widgetType === "form_container")?.id || "";
    });
    expect(formContainerId).toBeTruthy();

    const formFieldTypes = ["form_input", "form_textarea", "form_select", "form_checkbox", "form_radio"];
    for (const ft of formFieldTypes) {
      await page.evaluate((fid) => (window as any).__builderStore.getState().selectElement(fid), formContainerId);
      const card = page.locator(`button[data-block-type="${ft}"]`).first();
      await card.scrollIntoViewIfNeeded();
      await card.click();
    }

    // 2) Insert remaining 7 interactive widgets at root
    const interactiveTypes = ["table", "accordion", "tabs", "countdown", "video", "icon_box", "social_links"];
    for (const it of interactiveTypes) {
      await page.evaluate(() => (window as any).__builderStore.getState().selectElement(null));
      const card = page.locator(`button[data-block-type="${it}"]`).first();
      await card.scrollIntoViewIfNeeded();
      await card.click();
    }

    // Drop of video must NOT fire any Aparat dummy 404 or pageerror
    expect(failedUrls).toEqual([]);

    const idMap = await page.evaluate(() => {
      const m: Record<string, string> = {};
      const walk = (els: any[]) => {
        for (const el of els) {
          if (el.widgetType) m[el.widgetType] = el.id;
          if (el.children?.length) walk(el.children);
        }
      };
      walk((window as any).__builderStore.getState().ast.rootElements);
      return m;
    });

    for (const k of ["form_container", ...formFieldTypes, ...interactiveTypes]) {
      expect(idMap[k]).toBeTruthy();
    }

    // --- Active Nudge Tests across all 13 widgets ---
    // form_container
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_container);
    await page.locator('[data-testid="form-container-submit-label-input"]').fill("ارسال نهایی راند۳");
    await page.locator('[data-testid="form-container-success-input"]').fill("فرم راند۳ با موفقیت ثبت شد!");

    // form_input
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_input);
    await page.locator('[data-testid="form-input-label-input"]').fill("ایمیل تماس");
    await page.locator('[data-testid="form-input-name-input"]').fill("contact_email");
    await page.locator('[data-testid="form-input-placeholder-input"]').fill("user@example.com");
    await page.locator('[data-testid="form-input-type-select"]').click();
    await page.locator('[role="option"]:has-text("ایمیل")').click();
    await page.locator('[data-testid="form-input-required-switch"]').click();

    // form_textarea
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_textarea);
    await page.locator('[data-testid="form-textarea-label-input"]').fill("شرح درخواست");
    await page.locator('[data-testid="form-textarea-rows-input"]').fill("5");
    await page.locator('[data-testid="form-textarea-required-switch"]').click();

    // form_select
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_select);
    await page.locator('[data-testid="form-select-label-input"]').fill("واحد پشتیبانی");
    await page.locator('[data-testid="form-select-options-textarea"]').fill("فروش\nپشتیبانی فنی\nمالی");
    await page.locator('[data-testid="form-select-required-switch"]').click();

    // form_checkbox
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_checkbox);
    await page.locator('[data-testid="form-checkbox-label-input"]').fill("قوانین راند۳ را می‌پذیرم");
    const chkSwitch = page.locator('[data-testid="form-checkbox-required-switch"]');
    if ((await chkSwitch.getAttribute("aria-checked")) !== "true") {
      await chkSwitch.click();
    }

    // form_radio (comma-separated parsing + required toggle)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.form_radio);
    await page.locator('[data-testid="form-radio-label-input"]').fill("نحوه ارسال راند۳");
    await page.locator('[data-testid="form-radio-options-textarea"]').fill("پست پیشتاز، تیپاکس، پیک فوری");
    const radSwitch = page.locator('[data-testid="form-radio-required-switch"]');
    if ((await radSwitch.getAttribute("aria-checked")) !== "true") {
      await radSwitch.click();
    }

    // table (toggle bordered off & on, edit headers)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.table);
    await page.locator('[data-testid="table-headers-input"]').fill("ویژگی، وضعیت، امتیاز");
    await page.locator('[data-testid="table-rows-textarea"]').fill("سرعت، عالی، ۱۰\nکیفیت، تضمینی، ۹");

    // accordion
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.accordion);
    await page.locator('[data-testid="accordion-item-title-0"]').fill("سوال تست راند۳");
    await page.locator('[data-testid="accordion-item-content-0"]').fill("پاسخ دقیق راند۳");
    await page.locator('[data-testid="accordion-add-item-btn"]').click();

    // tabs (edit title/content + verify switching in Canvas)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.tabs);
    await page.locator('[data-testid="tab-title-input-0"]').fill("مشخصات راند۳");
    await page.locator('[data-testid="tab-content-input-0"]').fill("محتوای اول تب راند۳");
    await page.locator('[data-testid="tab-title-input-1"]').fill("نقد و بررسی راند۳");
    await page.locator('[data-testid="tab-content-input-1"]').fill("متن تخصصی دومین تب در راند۳");

    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');
    const canvasTab2Btn = frame.locator(`[data-element-id="${idMap.tabs}"] button:has-text("نقد و بررسی راند۳")`);
    await canvasTab2Btn.click();
    await expect(frame.locator(`[data-element-id="${idMap.tabs}"]`)).toContainText("متن تخصصی دومین تب در راند۳");

    // countdown
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.countdown);
    await page.locator('[data-testid="countdown-title-input"]').fill("فروش فوق‌العاده راند۳");
    await page.locator('[data-testid="countdown-date-input"]').fill("2028-06-15T18:30:00");
    await page.locator('[data-testid="countdown-expired-input"]').fill("زمان جشنواره راند۳ تمام شد");

    // video (verify zero 404 default placeholder & switch video_type selector safely without external 3rd-party player 404)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.video);
    await page.locator('[data-testid="video-type-select"]').click();
    await page.locator('[role="option"]:has-text("یوتیوب")').click();
    await expect(frame.locator(`[data-element-id="${idMap.video}"] [data-widget="video"]`)).toContainText("پخش‌کننده ویدئو");

    // icon_box (switch icon to truck + check SVG + update title)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.icon_box);
    await page.locator('[data-testid="iconbox-icon-select"]').click();
    await page.locator('[role="option"]').filter({ hasText: "Truck" }).first().click();
    await page.locator('[data-testid="iconbox-title-input"]').fill("ارسال اکسپرس راند۳");
    await page.locator('[data-testid="iconbox-desc-textarea"]').fill("توضیحات ارسال اکسپرس راند۳");
    await expect(frame.locator(`[data-element-id="${idMap.icon_box}"] [data-widget="icon_box"]`)).toHaveAttribute("data-icon", "truck");

    // social_links (edit platform + url using distinct inputs)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), idMap.social_links);
    await page.locator('[data-testid="social-platform-input-0"]').fill("تلگرام رسمی");
    await page.locator('[data-testid="social-url-input-0"]').fill("https://t.me/builder_gym_r03");

    // Save Draft -> Reload -> Verify persistence -> Publish
    await page.locator("button:has-text('ذخیره پیش‌نویس')").click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("پیش‌نویس", { timeout: 15000 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await expect(frame.locator(`[data-element-id="${idMap.video}"] [data-widget="video"]`)).toContainText("پخش‌کننده ویدئو", {
      timeout: 15000,
    });
    await expect(frame.locator(`[data-element-id="${idMap.form_container}"] [data-form-submit-preview="true"]`)).toHaveText(
      "ارسال نهایی راند۳"
    );

    await page.locator('[data-testid="publish-page-btn"]').click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("منتشرشده", { timeout: 15000 });

    // --- Public SSR Parity + Real Interactive Verification ---
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    const ssrRoot = page.locator(".builder-rendered-content");
    await expect(ssrRoot).toBeVisible({ timeout: 15000 });

    // 1. SSR Tabs click switches active pane
    await ssrRoot.locator('[data-widget="tabs"] button', { hasText: "نقد و بررسی راند۳" }).click();
    await expect(ssrRoot.locator('[data-widget="tabs"]')).toContainText("متن تخصصی دومین تب در راند۳");

    // 2. SSR Video widget renders clean placeholder without broken empty iframe
    await expect(ssrRoot.locator('[data-widget="video"]')).toContainText("پخش‌کننده ویدئو");
    await expect(ssrRoot.locator('[data-widget="video"] iframe')).toHaveCount(0);

    // 3. SSR Icon Box has Lucide SVG (not emoji)
    await expect(ssrRoot.locator('[data-widget="icon_box"]')).toHaveAttribute("data-icon", "truck");
    await expect(ssrRoot.locator('[data-widget="icon_box"] svg')).toBeVisible();

    // 4. SSR Social Links have exact URL + inline SVG icon
    await expect(ssrRoot.locator('[data-widget="social_links"] a').first()).toHaveAttribute(
      "href",
      "https://t.me/builder_gym_r03"
    );
    await expect(ssrRoot.locator('[data-widget="social_links"] a svg').first()).toBeVisible();

    // 5. SSR Form Radio split 3 options & required stars present
    await expect(ssrRoot.locator('.builder-form-radio input[type="radio"]')).toHaveCount(3);
    await expect(ssrRoot.locator('form[data-form-container="true"] span.text-destructive')).toHaveCount(5);
    await expect(ssrRoot.locator('form[data-form-container="true"] button[type="submit"]')).toHaveText("ارسال نهایی راند۳");

    // 6. SSR Form submission works end-to-end against POST /api/v1/content/forms/submit
    const ssrForm = ssrRoot.locator('form[data-form-container="true"]');
    await ssrForm.locator('input[name="contact_email"]').fill("qa@aroux.test");
    await ssrForm.locator('textarea').fill("تست ارسال واقعی فرم راند ۳");
    await ssrForm.locator('input[type="checkbox"]').check();
    await ssrForm.locator('input[type="radio"]').first().check();
    await ssrForm.locator('button[type="submit"]').click();
    await expect(ssrForm.locator('[data-form-status="1"]')).toHaveText("فرم راند۳ با موفقیت ثبت شد!", { timeout: 10000 });

    expect(failedUrls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
