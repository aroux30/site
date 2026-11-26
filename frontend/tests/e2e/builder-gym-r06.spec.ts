import { test, expect } from "@playwright/test";
import path from "node:path";
import fs from "node:fs";
import { execSync } from "node:child_process";
import { resetE2EPage } from "./helpers/admin-token";

const BASE_URL = process.env.PLAYWRIGHT_BASE_URL || "http://127.0.0.1:3000";
const API_BASE = "http://127.0.0.1:8000/api/v1";
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
  const tmp = path.join(BACKEND_DIR, `.gym-r06-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 06: Weight 4 Elementor UX, Templates, Global Components & Auth SSR Parity", () => {
  const createdTemplateIds: string[] = [];
  let adminToken = "";

  test.beforeEach(async ({ context }) => {
    adminToken = getAdminToken();
    await resetE2EPage("e2e-isolated-scratchpad");
    if (adminToken) {
      await context.addCookies([
        { name: "access_token", value: adminToken, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
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

  test("1. DnD, Undo/Redo, Copy/Paste Styles, Multi-Select, Save/Import Templates, Global Components & Auth SSR Parity", async ({ page, browser }) => {
    test.setTimeout(120000);
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
    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');
    await frame.locator('[data-element-id="el_e2ehead1"]').waitFor({ timeout: 15000 });

    // --- 1. Drag & Drop: Palette -> Canvas AND LayersTree Re-parenting ---
    await page.locator('button[data-block-type="button"]').first().dragTo(frame.locator('[data-element-id="el_e2econt2"]'));
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).__builderStore.getState().ast.rootElements.find((e: any) => e.id === "el_e2econt2")?.children?.length || 0)
      )
      .toBe(1);

    await page.locator('[data-testid="sidebar-tab-layers"]').click();
    await page.locator('[data-layer-row][data-element-id="el_e2etext1"]').dragTo(
      page.locator('[data-layer-row][data-element-id="el_e2econt2"]')
    );
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).__builderStore.getState().ast.rootElements.find((e: any) => e.id === "el_e2econt2")?.children?.some((c: any) => c.id === "el_e2etext1"))
      )
      .toBe(true);

    // Drag el_e2etext1 back into el_e2econt1 and clean the test button from el_e2econt2
    await page.locator('[data-layer-row][data-element-id="el_e2etext1"]').dragTo(
      page.locator('[data-layer-row][data-element-id="el_e2econt1"]')
    );
    const draggedBtnId = await page.evaluate(
      () => (window as any).__builderStore.getState().ast.rootElements.find((e: any) => e.id === "el_e2econt2")?.children?.[0]?.id || ""
    );
    if (draggedBtnId) {
      await page.evaluate((id) => (window as any).__builderStore.getState().deleteElement(id), draggedBtnId);
    }

    // --- 2. Keyboard Shortcuts (Ctrl+Z Undo, Ctrl+Y Redo, Ctrl+C / Ctrl+V) & Copy/Paste Styles ---
    await frame.locator('[data-element-id="el_e2ehead1"]').click();
    await page.locator('[data-testid="heading-text-input"]').fill("تیتر ویرایش‌شده راند۶");
    await page.locator('[data-testid="builder-toolbar-header"]').click({ position: { x: 400, y: 10 } });

    await page.keyboard.press("Control+z");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toContainText("سرتیتر اول");
    await page.keyboard.press("Control+y");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toContainText("تیتر ویرایش‌شده راند۶");

    // Set real background style via Inspector Style Tab, copy styles & paste onto el_e2etext1
    await page.locator('button[role="tab"]:has-text("استایل")').click();
    await page.locator('[data-testid="style-bg-color-input"]').fill("#dbeafe");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("background-color", "rgb(219, 234, 254)");

    await page.locator('[data-layer-row][data-element-id="el_e2ehead1"]').click({ button: "right" });
    await page.locator("button:has-text('کپی استایل')").click();
    await page.locator('[data-layer-row][data-element-id="el_e2etext1"]').click({ button: "right" });
    await page.locator("button:has-text('جای‌گذاری استایل')").click();
    await expect(frame.locator('[data-element-id="el_e2etext1"]')).toHaveCSS("background-color", "rgb(219, 234, 254)");

    // Ctrl+C / Ctrl+V duplicate via clipboard + LayersTree Multi-Select Ctrl+Click + Delete
    await page.locator('[data-layer-row][data-element-id="el_e2ehead1"]').click();
    await page.locator('[data-testid="builder-toolbar-header"]').click({ position: { x: 400, y: 10 } });
    await page.keyboard.press("Control+c");
    await page.keyboard.press("Control+v");
    await expect
      .poll(() =>
        page.evaluate(() => (window as any).__builderStore.getState().ast.rootElements.find((e: any) => e.id === "el_e2econt1")?.children?.length || 0)
      )
      .toBe(3);

    const clonedHeadingId = await page.evaluate(
      () => (window as any).__builderStore.getState().selectedElementId as string
    );
    expect(clonedHeadingId).toBeTruthy();

    await page.locator(`[data-layer-row][data-element-id="el_e2etext1"]`).click();
    await page.locator(`[data-layer-row][data-element-id="${clonedHeadingId}"]`).click({ modifiers: ["Control"] });
    const multiIds = await page.evaluate(() => (window as any).__builderStore.getState().selectedElementIds);
    expect(multiIds).toContain("el_e2etext1");
    expect(multiIds).toContain(clonedHeadingId);

    await page.locator('[data-testid="builder-toolbar-header"]').click({ position: { x: 400, y: 10 } });
    await page.keyboard.press("Delete");
    await expect(frame.locator(`[data-element-id="${clonedHeadingId}"]`)).toHaveCount(0);
    await expect(frame.locator('[data-element-id="el_e2etext1"]')).toHaveCount(0);

    // Undo Delete so el_e2etext1 comes back
    await page.keyboard.press("Control+z");
    await expect(frame.locator('[data-element-id="el_e2etext1"]')).toHaveCount(1);

    // --- 3. Save Section Template via Context Menu + Import from "My Templates" ---
    await page.locator('[data-layer-row][data-element-id="el_e2econt1"]').click({ button: "right" });
    await page.locator('[data-testid="navigator-save-template-btn"]').click();
    const secDialog = page.locator('[data-testid="save-section-template-dialog"]');
    await expect(secDialog).toBeVisible({ timeout: 5000 });
    await page.locator("button:has-text('انصراف')").click();
    await expect(secDialog).toBeHidden();

    // Also open from Canvas Context Menu on empty container el_e2econt2
    await frame.locator('[data-element-id="el_e2econt2"]').click({ button: "right" });
    await expect(page.locator('[data-testid="builder-context-menu"]')).toBeVisible({ timeout: 5000 });
    await page.locator('[data-testid="context-menu-save-template"]').click();
    await expect(secDialog).toBeVisible({ timeout: 5000 });
    const secTplTitle = `قالب بخش راند۶ ${Date.now()}`;
    await page.locator('[data-testid="save-section-template-title-input"]').fill(secTplTitle);
    const [secCreateRes] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/templates") && r.request().method() === "POST"),
      page.locator('[data-testid="save-section-template-submit-btn"]').click(),
    ]);
    expect(secCreateRes.status()).toBeLessThan(400);
    const secCreatedJson = await secCreateRes.json();
    if (secCreatedJson?.id) createdTemplateIds.push(secCreatedJson.id);
    await expect(secDialog).toBeHidden();

    // --- 4. Save Page Template + Import & Apply Page Template ---
    await page.locator('[data-testid="save-page-template-btn"]').click();
    const pageDialog = page.locator('[data-testid="save-page-template-dialog"]');
    await expect(pageDialog).toBeVisible({ timeout: 5000 });
    const pageTplTitle = `قالب برگه راند۶ ${Date.now()}`;
    await page.locator('[data-testid="save-page-template-title-input"]').fill(pageTplTitle);
    const [pageCreateRes] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/templates") && r.request().method() === "POST"),
      page.locator('[data-testid="save-page-template-submit-btn"]').click(),
    ]);
    expect(pageCreateRes.status()).toBeLessThan(400);
    const pageCreatedJson = await pageCreateRes.json();
    if (pageCreatedJson?.id) createdTemplateIds.push(pageCreatedJson.id);
    await expect(pageDialog).toBeHidden();

    await page.locator('[data-testid="sidebar-tab-blocks"]').click();
    await page.locator("aside button:has-text('قالب‌های من')").click();
    const secTplCard = page.locator(`[data-template-title="${secTplTitle}"]`).first();
    const pageTplCard = page.locator(`[data-template-title="${pageTplTitle}"]`).first();
    await expect(secTplCard).toBeVisible({ timeout: 10000 });
    await expect(pageTplCard).toBeVisible({ timeout: 10000 });
    const rootCountBeforeTpl = await page.evaluate(() => (window as any).__builderStore.getState().ast.rootElements.length);
    // Clear selection via Escape so the section template inserts cleanly at root level
    await page.keyboard.press("Escape");
    await secTplCard.click();
    await expect
      .poll(() => page.evaluate(() => (window as any).__builderStore.getState().ast.rootElements.length))
      .toBe(rootCountBeforeTpl + 1);

    // --- 5. Global Component Make Global -> Duplicate -> Live Sync Click -> Detach ---
    await frame.locator('[data-element-id="el_e2ehead1"]').click();
    await page.locator('button[role="tab"]:has-text("پیشرفته")').click();
    await page.locator("button:has-text('تبدیل به کامپوننت همگام سراسری')").click();
    await page.keyboard.press("Control+d");

    const gcInfo = await page.evaluate(() => {
      const cont = (window as any).__builderStore.getState().ast.rootElements.find((e: any) => e.id === "el_e2econt1");
      const hs = (cont?.children || []).filter((c: any) => c.widgetType === "heading");
      return hs.map((h: any) => h.id);
    });
    expect(gcInfo.length).toBeGreaterThanOrEqual(2);

    // Click first instance directly without overlay obstruction!
    await frame.locator(`[data-element-id="${gcInfo[0]}"]`).click();
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="heading-text-input"]').fill("تیتر همگام‌سازی زنده");
    await expect(frame.locator(`[data-element-id="${gcInfo[0]}"]`)).toContainText("تیتر همگام‌سازی زنده");
    await expect(frame.locator(`[data-element-id="${gcInfo[1]}"]`)).toContainText("تیتر همگام‌سازی زنده");

    // Detach second instance and verify divergence
    await frame.locator(`[data-element-id="${gcInfo[1]}"]`).click();
    await page.locator('button[role="tab"]:has-text("پیشرفته")').click();
    await page.locator("button:has-text('جدا کردن از کامپوننت سراسری')").click();

    await frame.locator(`[data-element-id="${gcInfo[0]}"]`).click();
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="heading-text-input"]').fill("فقط نسخه همگام اصلی");
    await expect(frame.locator(`[data-element-id="${gcInfo[0]}"]`)).toContainText("فقط نسخه همگام اصلی");
    await expect(frame.locator(`[data-element-id="${gcInfo[1]}"]`)).toContainText("تیتر همگام‌سازی زنده");

    // --- 6. authVisibility SSR Parity (Guest vs Authenticated Visitor) ---
    await page.evaluate(() => {
      const st = (window as any).__builderStore.getState();
      const updated = st.ast.rootElements.map((c: any) =>
        c.id === "el_e2econt1"
          ? {
              ...c,
              children: [
                {
                  id: "el_authonly6",
                  name: "بخش اعضا",
                  type: "widget",
                  widgetType: "heading",
                  widgetProps: { text: "محتوای محرمانه اعضا", tag: "h2" },
                  authVisibility: "authenticated",
                  styles: { mobile: {} },
                  children: [],
                },
                {
                  id: "el_guestonly6",
                  name: "بخش مهمان",
                  type: "widget",
                  widgetType: "heading",
                  widgetProps: { text: "پیام خوشامد مهمان", tag: "h2" },
                  authVisibility: "guest",
                  styles: { mobile: {} },
                  children: [],
                },
                {
                  id: "el_allvis6",
                  name: "بخش عمومی",
                  type: "widget",
                  widgetType: "heading",
                  widgetProps: { text: "محتوای عمومی برای همه", tag: "h2" },
                  authVisibility: "all",
                  styles: { mobile: {} },
                  children: [],
                },
              ],
            }
          : c
      );
      st.replacePageAST({ ...st.ast, rootElements: updated });
    });

    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/pages/") && r.request().method() === "PATCH" && r.status() < 400),
      page.waitForResponse((r) => r.url().includes("/api/cms-revalidate") && r.status() < 400),
      page.locator('[data-testid="publish-page-btn"]').click(),
    ]);
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("منتشرشده", { timeout: 15000 });

    // Guest visitor (no cookies)
    const guestCtx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
    const guestPage = await guestCtx.newPage();
    await guestPage.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    const guestDoc = guestPage.locator(".builder-rendered-content .builder-document");
    await expect(guestDoc).toBeVisible({ timeout: 15000 });
    const guestHtml = await guestDoc.innerHTML();
    expect(guestHtml).not.toContain("محتوای محرمانه اعضا");
    expect(guestHtml).toContain("پیام خوشامد مهمان");
    expect(guestHtml).toContain("محتوای عمومی برای همه");
    await guestCtx.close();

    // Authenticated visitor (with access_token cookie, no ?builder=1)
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    const authDoc = page.locator(".builder-rendered-content .builder-document");
    await expect(authDoc).toBeVisible({ timeout: 15000 });
    const authHtml = await authDoc.innerHTML();
    expect(authHtml).toContain("محتوای محرمانه اعضا");
    expect(authHtml).not.toContain("پیام خوشامد مهمان");
    expect(authHtml).toContain("محتوای عمومی برای همه");

    expect(failedUrls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    const token = adminToken || getAdminToken();
    for (const id of createdTemplateIds) {
      await fetch(`${API_BASE}/content/admin/templates/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      }).catch(() => {});
    }
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
