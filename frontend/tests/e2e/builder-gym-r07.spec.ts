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
  const tmp = path.join(BACKEND_DIR, `.gym-r07-tok-${Date.now()}.py`);
  fs.writeFileSync(tmp, script, "utf8");
  try {
    const out = execSync(`python "${tmp}"`, { cwd: BACKEND_DIR, encoding: "utf8" });
    const match = out.split("\n").find((l) => l.includes("TOKEN_START:"));
    return match ? match.replace("TOKEN_START:", "").trim() : "";
  } finally {
    if (fs.existsSync(tmp)) try { fs.unlinkSync(tmp); } catch {}
  }
}

test.describe("Builder Gym Round 07: Weight 5 Tablet/Mobile Responsive, Dark Mode, 60-Node Stress & Failed Save", () => {
  test.beforeEach(async ({ context }) => {
    const token = getAdminToken();
    await resetE2EPage("e2e-isolated-scratchpad");
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

  test("1. Tablet 768px & Mobile 375px overrides + visibility SSR Parity, Dark Mode Canvas sync, 60+ nested stress & Failed Save isDirty", async ({ page }) => {
    test.setTimeout(120000);
    const errors: string[] = [];
    const failedUrls: string[] = [];
    let expectingSimulated500 = false;
    page.on("pageerror", (e) => errors.push(String(e)));
    page.on("console", (msg) => {
      if (msg.type() === "error") {
        const txt = msg.text();
        if (expectingSimulated500 && (txt.includes("(500)") || txt.includes("status of 500") || txt.includes("Simulated 500"))) {
          return;
        }
        errors.push(txt);
      }
    });
    page.on("response", (res) => {
      if (res.status() >= 400 && !(expectingSimulated500 && res.status() === 500) && !res.url().includes("favicon")) {
        failedUrls.push(`${res.status()} ${res.url()}`);
      }
    });

    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForSelector('[data-testid="builder-toolbar-header"]', { timeout: 15000 });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    const frame = page.frameLocator('iframe[data-testid="canvas-iframe"]');
    await frame.locator('[data-element-id="el_e2ehead1"]').waitFor({ timeout: 15000 });

    // --- 1. Responsive Overrides (Desktop/Tablet 768px/Mobile 375px) + Dark Mode Live Canvas Sync ---
    await page.evaluate(() => {
      const st = (window as any).__builderStore.getState();
      st.updateDeviceStyles("el_e2ehead1", "desktop", {
        typography: { fontSize: { value: 36, unit: "px" } },
        background: { type: "color", color: "#dcfce7" },
      });
      st.updateDeviceStyles("el_e2ehead1", "tablet", {
        typography: { fontSize: { value: 24, unit: "px" } },
        background: { type: "color", color: "#fef9c3" },
      });
      st.updateDeviceStyles("el_e2ehead1", "mobile", {
        typography: { fontSize: { value: 16, unit: "px" } },
        background: { type: "color", color: "#fee2e2" },
      });
      st.updateElementVisibility("el_e2etext1", { mobile: false });
    });

    await page.locator("button[title*='تبلت']").click();
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("font-size", "24px");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("background-color", "rgb(254, 249, 195)");

    await page.locator("button[title*='موبایل']").click();
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("font-size", "16px");
    await expect(frame.locator('[data-element-id="el_e2ehead1"]')).toHaveCSS("background-color", "rgb(254, 226, 226)");
    await expect(frame.locator('[data-element-id="el_e2etext1"]')).toContainText("مخفی در موبایل");

    const mobileOverflow = await page.evaluate(() => {
      const iframe = document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement;
      const doc = iframe?.contentDocument;
      return { sw: doc?.documentElement.scrollWidth || 0, cw: doc?.documentElement.clientWidth || 0 };
    });
    expect(mobileOverflow.sw).toBeLessThanOrEqual(mobileOverflow.cw);

    // Switch back desktop & toggle Dark Mode -> verify Canvas iframe background is dark (NOT #ffffff!)
    await page.locator("button[title*='دسکتاپ']").click();
    await page.evaluate(() => document.documentElement.classList.add("dark"));
    await expect
      .poll(() =>
        page.evaluate(() => {
          const doc = (document.querySelector('iframe[data-testid="canvas-iframe"]') as HTMLIFrameElement)?.contentDocument;
          return doc ? getComputedStyle(doc.body).backgroundColor : "";
        })
      )
      .not.toBe("rgb(255, 255, 255)");

    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/pages/") && r.request().method() === "PATCH" && r.status() < 400),
      page.waitForResponse((r) => r.url().includes("/api/cms-revalidate") && r.status() < 400),
      page.locator('[data-testid="publish-page-btn"]').click(),
    ]);

    // Verify SSR Parity across 1440px, 768px & 375px (mobile hidden element MUST be display: none!)
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad`, { waitUntil: "domcontentloaded" });
    await expect(page.locator("#el_e2ehead1")).toHaveCSS("font-size", "36px");
    await expect(page.locator("#el_e2etext1")).toBeVisible();

    await page.setViewportSize({ width: 768, height: 1024 });
    await expect(page.locator("#el_e2ehead1")).toHaveCSS("font-size", "24px");
    await expect(page.locator("#el_e2etext1")).toBeVisible();

    await page.setViewportSize({ width: 375, height: 812 });
    await expect(page.locator("#el_e2ehead1")).toHaveCSS("font-size", "16px");
    await expect(page.locator("#el_e2etext1")).toBeHidden();
    const ssrMobOverflow = await page.evaluate(() => ({
      sw: document.documentElement.scrollWidth,
      cw: document.documentElement.clientWidth,
    }));
    expect(ssrMobOverflow.sw).toBeLessThanOrEqual(ssrMobOverflow.cw);

    // --- 2. 60 Nested Elements Stress Test + Failed Save (HTTP 500) isDirty Retention ---
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto(`${BASE_URL}/e2e-isolated-scratchpad?builder=1`, { waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });

    const flatStressCount = await page.evaluate(() => {
      const roots = Array.from({ length: 10 }, (_, i) => ({
        id: `el_s5r_${i}`,
        name: `بخش استرس ${i + 1}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 8, unit: "px" }, gridColumns: 1 },
        styles: { mobile: {} },
        children: [
          {
            id: `el_s5n_${i}`,
            name: `کانتینر تو در تو ${i + 1}`,
            type: "container",
            isLocked: false,
            isHidden: false,
            layout: { kind: "flex", direction: "column", justifyContent: "start", alignItems: "stretch", flexWrap: "nowrap", gap: { value: 6, unit: "px" }, gridColumns: 1 },
            styles: { mobile: {} },
            children: Array.from({ length: 4 }, (__, j) => ({
              id: `el_s5w_${i}_${j}`,
              name: `آیتم ${i + 1}-${j + 1}`,
              type: "widget",
              widgetType: j % 2 === 0 ? "heading" : "button",
              widgetProps: j % 2 === 0 ? { text: `هدینگ استرس ${i + 1}-${j + 1}`, tag: "h3" } : { label: `دکمه ${i + 1}-${j + 1}`, url: "#" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            })),
          },
        ],
      }));
      const st = (window as any).__builderStore.getState();
      st.replacePageAST({ ...st.ast, rootElements: roots });
      return (window as any).__builderStore.getState().ast.rootElements.reduce(
        (acc: number, r: any) => acc + 1 + (r.children || []).reduce((s2: number, c: any) => s2 + 1 + (c.children?.length || 0), 0),
        0
      );
    });
    expect(flatStressCount).toBe(60);
    await expect(frame.locator('[data-element-id="el_s5w_9_3"]')).toBeVisible({ timeout: 15000 });

    // Route PATCH -> 500 to simulate failed network save and verify honest toast + isDirty retention
    expectingSimulated500 = true;
    await page.route("**/api/v1/content/admin/pages/**", async (route) => {
      if (route.request().method() === "PATCH") {
        await route.fulfill({ status: 500, contentType: "application/json", body: JSON.stringify({ detail: "Simulated 500 failure" }) });
      } else {
        await route.continue();
      }
    });
    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/pages/") && r.request().method() === "PATCH"),
      page.locator("button:has-text('ذخیره پیش‌نویس')").click(),
    ]);
    await expect(page.locator("text=تغییرات شما همچنان در ویرایشگر حفظ شده است")).toBeVisible({ timeout: 5000 });
    const dirtyOnFail = await page.evaluate(() => (window as any).__builderStore.getState().isDirty);
    expect(dirtyOnFail).toBe(true);

    await page.unroute("**/api/v1/content/admin/pages/**");
    expectingSimulated500 = false;
    await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/v1/content/admin/pages/") && r.request().method() === "PATCH" && r.status() < 400),
      page.waitForResponse((r) => r.url().includes("/api/cms-revalidate") && r.status() < 400),
      page.locator('[data-testid="publish-page-btn"]').click(),
    ]);

    await page.reload({ waitUntil: "domcontentloaded" });
    await page.waitForFunction(() => Boolean((window as any).__builderStore?.getState()?.pageId), null, { timeout: 15000 });
    await expect(frame.locator('[data-element-id="el_s5w_9_3"]')).toBeVisible({ timeout: 15000 });

    expect(failedUrls).toEqual([]);
    expect(errors).toEqual([]);
  });

  test.afterAll(async () => {
    await resetE2EPage("e2e-isolated-scratchpad");
  });
});
