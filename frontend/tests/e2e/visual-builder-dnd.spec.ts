import { expect, test, type Page, type FrameLocator } from "@playwright/test";
import { createAccessTokenForE2E } from "./helpers/admin-token";

/**
 * Visual Builder Studio — real drag-and-drop E2E (P0/P1 close-out).
 *
 * These drive the actual browser: a real mouse press/move/release for canvas
 * reordering, and real DragEvent dispatch for palette→canvas. The canvas
 * lives in an iframe with its own React root, so every locator goes through
 * `frameLocator`.
 *
 * The suite needs a CMS page that HAS builder_data (`showcase`). It mints an
 * admin token with the backend's own signer rather than typing a password
 * that is not in the repo.
 */

const CANVAS = 'iframe[title="Visual Builder Canvas"]';
const BASE_URL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000";

async function openStudio(page: Page): Promise<FrameLocator> {
  const token = await createAccessTokenForE2E();
  await page.context().addCookies([
    { name: "access_token", value: token, url: BASE_URL, httpOnly: false, sameSite: "Lax" },
  ]);
  await page.goto("/showcase?visual_editor=true");
  await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({
    timeout: 30_000,
  });
  const frame = page.frameLocator(CANVAS);
  await expect(frame.locator('[data-testid="builder-canvas-root"]')).toBeVisible({
    timeout: 20_000,
  });
  return frame;
}

async function childIds(frame: FrameLocator): Promise<string[]> {
  return frame.locator("[data-element-id]").evaluateAll((els) => {
    const container = els[0];
    return Array.from(
      container?.querySelectorAll(":scope > [data-element-id]") ?? []
    ).map((e) => e.getAttribute("data-element-id")!);
  });
}

async function mouseDrag(
  page: Page,
  from: { x: number; y: number; width: number; height: number },
  to: { x: number; y: number; width: number; height: number }
) {
  const fx = from.x + from.width / 2;
  const fy = from.y + from.height / 2;
  const tx = to.x + to.width / 2;
  const ty = to.y + to.height / 2;
  await page.mouse.move(fx, fy);
  await page.mouse.down();
  await page.waitForTimeout(80);
  for (let i = 1; i <= 14; i++) {
    await page.mouse.move(fx + ((tx - fx) * i) / 14, fy + ((ty - fy) * i) / 14, {
      steps: 2,
    });
    await page.waitForTimeout(30);
  }
  await page.waitForTimeout(120);
  await page.mouse.up();
  await page.waitForTimeout(600);
}

test.describe("Visual Builder Studio — drag & drop", () => {
  test("adds a block from the palette by click", async ({ page }) => {
    const frame = await openStudio(page);
    const before = await frame.locator("[data-element-id]").count();
    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator('button:has-text("دکمه")').first().click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before + 1);
  });

  test("adds a block from the palette with a real drag onto the canvas", async ({
    page,
  }) => {
    const frame = await openStudio(page);
    const before = await frame.locator("[data-element-id]").count();

    await page.locator('button:has-text("سرتیتر")').first().evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData(
        "application/json",
        JSON.stringify({ type: "block_def", blockType: "heading" })
      );
      el.dispatchEvent(new DragEvent("dragstart", { bubbles: true, dataTransfer: dt }));
    });
    await frame.locator('[data-testid="builder-canvas-root"]').evaluate((el) => {
      const dt = new DataTransfer();
      dt.setData(
        "application/json",
        JSON.stringify({ type: "block_def", blockType: "heading" })
      );
      el.dispatchEvent(
        new DragEvent("dragover", { bubbles: true, cancelable: true, dataTransfer: dt })
      );
      el.dispatchEvent(
        new DragEvent("drop", { bubbles: true, cancelable: true, dataTransfer: dt })
      );
    });

    await expect(frame.locator("[data-element-id]")).toHaveCount(before + 1);
  });

  test("reorders siblings inside a container with a real mouse drag", async ({
    page,
  }) => {
    const frame = await openStudio(page);
    const ids = await childIds(frame);
    expect(ids.length).toBeGreaterThanOrEqual(2);

    await frame.locator(`[data-element-id="${ids[1]}"]`).click();
    const handle = await frame.locator('[title="جابه‌جایی"]').first().boundingBox();
    const target = await frame.locator(`[data-element-id="${ids[0]}"]`).boundingBox();
    expect(handle && target).toBeTruthy();

    await mouseDrag(page, handle!, target!);

    const after = await childIds(frame);
    expect(after[0]).toBe(ids[1]);
    expect(after[1]).toBe(ids[0]);
  });

  test("moves an element into a different container", async ({ page }) => {
    const frame = await openStudio(page);
    const roots = await frame
      .locator('[data-testid="builder-canvas-root"] > [data-element-id]')
      .evaluateAll((els) => els.map((e) => e.getAttribute("data-element-id")!));
    test.skip(roots.length < 2, "needs two root elements");

    const [source, destination] = roots;
    await frame.locator(`[data-element-id="${source}"]`).click();
    const handle = await frame.locator('[title="جابه‌جایی"]').first().boundingBox();
    const targetBox = await frame.locator(`[data-element-id="${destination}"]`).boundingBox();
    expect(handle && targetBox).toBeTruthy();

    await mouseDrag(page, handle!, targetBox!);

    const destChildren = await frame
      .locator(`[data-element-id="${destination}"]`)
      .evaluate((el) => el.querySelectorAll(":scope > [data-element-id]").length);
    expect(destChildren).toBeGreaterThan(0);
  });

  test("deletes and duplicates an element", async ({ page }) => {
    const frame = await openStudio(page);
    const before = await frame.locator("[data-element-id]").count();

    await frame.locator("[data-element-id]").nth(1).click();
    await page.locator('[title="تکثیر (Duplicate)"]').click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before + 1);

    await page.locator('[title="حذف"]').click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before);
  });

  test("undo and redo restore the tree", async ({ page }) => {
    const frame = await openStudio(page);
    const before = await frame.locator("[data-element-id]").count();

    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator('button:has-text("دکمه")').first().click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before + 1);

    await page.locator('button[title*="بازگشت"]').click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before);

    await page.locator('button[title*="انجام مجدد"]').click();
    await expect(frame.locator("[data-element-id]")).toHaveCount(before + 1);
  });

  test("saves a draft and restores it after reload", async ({ page }) => {
    const frame = await openStudio(page);

    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator('button:has-text("دکمه")').first().click();
    const expected = await frame.locator("[data-element-id]").count();

    await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click();
    await expect(page.getByText("ذخیره شد")).toBeVisible({ timeout: 15_000 });

    await page.reload();
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toBeVisible({
      timeout: 30_000,
    });
    await expect(page.frameLocator(CANVAS).locator("[data-element-id]")).toHaveCount(
      expected,
      { timeout: 20_000 }
    );
  });

  test("autosaves 1.5s after an edit", async ({ page }) => {
    const frame = await openStudio(page);
    const saveStatuses: number[] = [];
    page.on("response", (r) => {
      if (r.request().method() === "PATCH" && r.url().includes("/content/admin/pages")) {
        saveStatuses.push(r.status());
      }
    });

    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator('button:has-text("دکمه")').first().click();
    await expect.poll(() => saveStatuses.length, { timeout: 12_000 }).toBeGreaterThan(0);
    expect(saveStatuses.every((s) => s === 200)).toBe(true);
    await expect(frame.locator("[data-element-id]")).not.toHaveCount(0);
  });

  test("a failed save keeps local edits and shows the error", async ({ page }) => {
    const frame = await openStudio(page);
    await page.route("**/content/admin/pages/**", (route) =>
      route.request().method() === "PATCH"
        ? route.fulfill({ status: 500, body: "boom" })
        : route.continue()
    );

    await page.getByRole("button", { name: "افزودن بلوک" }).click();
    await page.locator('button:has-text("دکمه")').first().click();
    await page.getByRole("button", { name: "ذخیره پیش‌نویس" }).click();

    await expect(page.getByText("خطای ذخیره خودکار")).toBeVisible({ timeout: 15_000 });
    await expect(frame.locator("[data-element-id]")).not.toHaveCount(0);
  });

  test("a non-admin never reaches the studio", async ({ page }) => {
    await page.goto("/showcase?visual_editor=true");
    await expect(page.getByRole("button", { name: "افزودن بلوک" })).toHaveCount(0);
    await expect(page.locator(CANVAS)).toHaveCount(0);
  });
});
