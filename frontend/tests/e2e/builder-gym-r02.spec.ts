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
  const tmp = path.join(BACKEND_DIR, `.gym-r02-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 02: Weight 2 Batch 1 (10 Base Widgets & Style/Advanced SSR Parity)", () => {
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
          state: { user: { id: "admin-1", phone: "09120000000", isSuperuser: true, roles: ["super_admin"] }, isAuthenticated: true, isLoading: false },
        })
      );
    });
  });

  test("1. All 10 base widget types insert, nudge in Content/Style/Advanced, persist on reload, and match SSR", async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(String(e)));

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="builder-toolbar-header"]', { timeout: 15000 });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await page.waitForSelector('iframe[data-testid="canvas-iframe"]', { timeout: 15000 });

    // Clean start AST in store so we isolate all base block insertions
    await page.evaluate(() => {
      const st = (window as any).__builderStore.getState();
      st.initPage(st.pageId, { ...st.ast, rootElements: [] }, st.ast.title, st.ast.slug);
    });

    const baseKeys = ["container", "section", "columns", "heading", "text_editor", "image", "button", "spacer", "divider"];
    for (const k of baseKeys) {
      await page.evaluate(() => (window as any).__builderStore.getState().selectElement(null));
      const card = page.locator(`button[data-block-type="${k}"]`).first();
      await card.scrollIntoViewIfNeeded();
      await card.click();
    }

    const map = await page.evaluate(() => {
      const roots = (window as any).__builderStore.getState().ast.rootElements;
      const m: Record<string, string> = {};
      for (const r of roots) {
        const key = r.widgetType || (r.name?.includes("ستون") ? "columns" : r.name?.includes("سکشن") ? "section" : r.type);
        if (!m[key]) m[key] = r.id;
      }
      return m;
    });
    expect(Object.keys(map)).toEqual(expect.arrayContaining(baseKeys));

    // Columns (2 Columns Grid) renders 2 real columns on desktop inside Studio iframe!
    const colGridCols = await page.evaluate((id) => {
      const doc = (document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement)?.contentDocument;
      const el = doc?.querySelector(`[data-element-id="${id}"]`);
      return el ? doc!.defaultView!.getComputedStyle(el).gridTemplateColumns.split(" ").length : 0;
    }, map.columns);
    expect(colGridCols).toBe(2);

    // Container Content nudge: Gap + Boxed Width
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.container);
    await page.locator('[data-testid="container-gap-input"]').fill("28");
    await page.locator('[data-testid="container-width-boxed-btn"]').click();
    await page.locator('[data-testid="container-boxed-width-input"]').fill("960");

    // Heading Content + Style + Advanced nudge
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.heading);
    await page.locator('[data-testid="heading-text-input"]').fill("تیتر راند۲ ۳۶۰");
    await page.locator('[data-testid="heading-tag-select"]').click();
    await page.locator('[role="option"]:has-text("H3")').click();

    await page.locator('button[role="tab"]:has-text("استایل")').click();
    await page.locator('[data-testid="padding-top-input"]').fill("24");
    await page.locator('[data-testid="typography-fontsize-input"]').fill("36");
    await page.locator('[data-testid="typography-color-input"]').fill("#dc2626");
    await page.locator('[data-testid="text-align-left-btn"]').click();
    await page.locator('[data-testid="border-radius-input"]').fill("16px");
    await page.locator('[data-testid="opacity-input"]').fill("0.85");

    await page.locator('button[role="tab"]:has-text("پیشرفته")').click();
    await page.locator('[data-testid="custom-attributes-textarea"]').fill("data-gym|r02-pass");
    await page.locator('[data-testid="transform-rotate-input"]').fill("5");

    // Check Heading inner H3 receives color #dc2626 + fontSize 36px + textAlign left
    const hCanvasCs = await page.evaluate((id) => {
      const doc = (document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement)?.contentDocument;
      const wrap = doc?.querySelector(`[data-element-id="${id}"]`) as HTMLElement;
      const h3 = wrap?.querySelector("h3") as HTMLElement;
      const csH3 = h3 ? doc!.defaultView!.getComputedStyle(h3) : null;
      const csWrap = wrap ? doc!.defaultView!.getComputedStyle(wrap) : null;
      return {
        tag: h3?.tagName.toLowerCase(),
        text: h3?.textContent?.trim(),
        color: csH3?.color,
        fontSize: csH3?.fontSize,
        textAlign: csH3?.textAlign,
        borderRadius: csWrap?.borderTopLeftRadius,
        opacity: csWrap?.opacity,
        dataGym: wrap?.getAttribute("data-gym"),
      };
    }, map.heading);
    expect(hCanvasCs.tag).toBe("h3");
    expect(hCanvasCs.text).toBe("تیتر راند۲ ۳۶۰");
    expect(hCanvasCs.color).toBe("rgb(220, 38, 38)");
    expect(hCanvasCs.fontSize).toBe("36px");
    expect(hCanvasCs.textAlign).toBe("left");
    expect(hCanvasCs.borderRadius).toBe("16px");
    expect(hCanvasCs.opacity).toBe("0.85");
    expect(hCanvasCs.dataGym).toBe("r02-pass");

    // Button Content + Surface Style nudge
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.button);
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="button-label-input"]').fill("دکمه تست راند۲");
    await page.locator('[data-testid="button-url-input"]').fill("https://example.com/r02");
    await page.locator('[data-testid="button-newtab-switch"]').click();

    await page.locator('button[role="tab"]:has-text("استایل")').click();
    await page.locator('[data-testid="typography-color-input"]').fill("#fef2f2");
    await expect.poll(async () => {
      return await page.evaluate((id) => {
        const doc = (document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement)?.contentDocument;
        const a = doc?.querySelector(`[data-element-id="${id}"] a`) as HTMLElement;
        return {
          target: a?.getAttribute("target"),
          color: a ? doc!.defaultView!.getComputedStyle(a).color : null,
        };
      }, map.button);
    }, { timeout: 3000 }).toEqual({ target: "_blank", color: "rgb(254, 242, 242)" });

    // Image Content nudge
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.image);
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="image-alt-input"]').fill("تصویر تست راند۲");

    // Spacer Content nudge
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.spacer);
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="spacer-height-input"]').fill("88");

    // Divider Content nudge (dashed + 3px + 70% width + right align)
    await page.evaluate((id) => (window as any).__builderStore.getState().selectElement(id), map.divider);
    await page.locator('button[role="tab"]:has-text("محتوا")').click();
    await page.locator('[data-testid="divider-style-select"]').click();
    await page.locator('[role="option"]:has-text("خط‌چین")').click();
    await page.locator('[data-testid="divider-weight-input"]').fill("3");
    await page.locator('[data-testid="divider-width-input"]').fill("70");
    await page.locator('[data-testid="divider-align-right-btn"]').click();

    // Save Draft + Reload + Publish -> Verify SSR Output Parity
    await page.locator("button:has-text('ذخیره پیش‌نویس')").click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("پیش‌نویس", { timeout: 15000 });

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');
    await expect(frame.locator(`[data-element-id="${map.heading}"]`)).toBeVisible({ timeout: 15000 });
    const reloadedRadius = await page.evaluate((id) => {
      const doc = (document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement)?.contentDocument;
      const el = doc?.querySelector(`[data-element-id="${id}"]`);
      return el ? doc!.defaultView!.getComputedStyle(el).borderTopLeftRadius : null;
    }, map.heading);
    expect(reloadedRadius).toBe("16px");

    await page.locator('[data-testid="publish-page-btn"]').click();
    await expect(page.locator('[data-testid="page-status-badge"]')).toHaveText("منتشرشده", { timeout: 15000 });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    const ssrRoot = page.locator(".builder-rendered-content");
    await expect(ssrRoot).toBeVisible({ timeout: 15000 });

    const ssr = await page.evaluate(() => {
      const root = document.querySelector(".builder-rendered-content")!;
      const h3 = Array.from(root.querySelectorAll("h3")).find((e) => (e.textContent || "").includes("تیتر راند۲"));
      const btn = Array.from(root.querySelectorAll("a")).find((e) => (e.textContent || "").includes("دکمه تست راند۲"));
      const hr = root.querySelector("hr");
      const spacer = Array.from(root.querySelectorAll("div")).find((d) => d.getAttribute("aria-hidden") === "true" && (d.getAttribute("style") || "").includes("height"));
      const gym = root.querySelector('[data-gym="r02-pass"]');
      return {
        h3FontSize: h3 ? getComputedStyle(h3).fontSize : null,
        h3Color: h3 ? getComputedStyle(h3).color : null,
        h3TextAlign: h3 ? getComputedStyle(h3).textAlign : null,
        h3Radius: h3 ? getComputedStyle(h3).borderTopLeftRadius : null,
        h3Opacity: h3 ? getComputedStyle(h3).opacity : null,
        btnTarget: btn?.getAttribute("target"),
        btnColor: btn ? getComputedStyle(btn).color : null,
        hrStyle: hr ? getComputedStyle(hr).borderTopStyle : null,
        hrWeight: hr ? getComputedStyle(hr).borderTopWidth : null,
        spacerH: spacer ? getComputedStyle(spacer).height : null,
        hasGym: Boolean(gym),
      };
    });

    expect(ssr.h3FontSize).toBe("36px");
    expect(ssr.h3Color).toBe("rgb(220, 38, 38)");
    expect(ssr.h3TextAlign).toBe("left");
    expect(ssr.h3Radius).toBe("16px");
    expect(ssr.h3Opacity).toBe("0.85");
    expect(ssr.btnTarget).toBe("_blank");
    expect(ssr.btnColor).toBe("rgb(254, 242, 242)");
    expect(ssr.hrStyle).toBe("dashed");
    expect(ssr.hrWeight).toBe("3px");
    expect(ssr.spacerH).toBe("88px");
    expect(ssr.hasGym).toBe(true);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
