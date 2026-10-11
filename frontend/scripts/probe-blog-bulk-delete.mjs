// Click the bulk "انتقال به سطل زباله" button exactly as a user would:
// select rows, then press the bulk action.
//
// The bulk bar only appears once rows are selected, and its handler calls
// `handleBulk`, which posts to /admin/blog/posts/bulk/trash. This probe records
// the confirm dialog, the request, the response, and the toast — so "nothing
// happened" can be attributed to a specific step instead of guessed at.
//
// Usage: node scripts/probe-blog-bulk-delete.mjs [baseUrl]

import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:3000";

const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();

const log = { dialogs: [], requests: [], consoleErrors: [] };

page.on("dialog", async (d) => {
  log.dialogs.push(`${d.type()}: ${d.message().slice(0, 70)}`);
  await d.accept();
});
page.on("request", (r) => {
  if (r.method() !== "GET") log.requests.push(`${r.method()} ${r.url().replace(base, "").slice(0, 90)}`);
});
page.on("response", (r) => {
  if (r.request().method() !== "GET") log.requests.push(`  -> ${r.status()}`);
});
page.on("console", (m) => {
  if (m.type() === "error") log.consoleErrors.push(m.text().slice(0, 160));
});

// Log in through the UI.
await page.goto(`${base}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.fill('input[type="tel"], input#phone', "09120000000").catch(() => {});
await page.fill('input[type="password"], input#password', "Admin@123456").catch(() => {});
await page.click('button[type="submit"]').catch(() => {});
await page.waitForTimeout(3500);

await page.goto(`${base}/admin/blog`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2500);

const rowsBefore = await page.locator("tbody tr").count();
console.log("rows before:", rowsBefore);

// Select the first two rows. The row checkboxes are Radix buttons carrying an
// aria-label, not native inputs — `input[type=checkbox]` matches nothing here,
// which is how an earlier version of this probe measured "0 checkboxes" and
// silently tested the row-level button instead of the bulk one.
const checkboxes = page.getByRole("checkbox", { name: /^انتخاب ردیف/ });
const n = Math.min(2, await checkboxes.count());
console.log("row checkboxes found:", await checkboxes.count(), "- clicking", n);
for (let i = 0; i < n; i++) {
  await checkboxes.nth(i).click();
  await page.waitForTimeout(250);
}
await page.waitForTimeout(800);

// The bulk bar is a separate region with an aria-label. Scope to it so the
// row-level trash icons (which share the label text) are not clicked instead.
const bulkBar = page.getByRole("toolbar", { name: "کنش‌های گروهی" });
const barVisible = await bulkBar.count();
console.log("bulk bar present:", barVisible);
const bulkTrash = bulkBar.getByRole("button", { name: "انتقال به سطل زباله" });
console.log("bulk trash buttons inside the bar:", await bulkTrash.count());

if (await bulkTrash.count()) {
  await bulkTrash.first().click();
  await page.waitForTimeout(3000);
}

const after = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("tbody tr")];
  return {
    rowCount: rows.length,
    firstRowText: rows[0]?.innerText?.replace(/\s+/g, " ").slice(0, 60) ?? null,
    // A toast is the user-visible result of a bulk run.
    toastText: [...document.querySelectorAll('[role="status"], [role="alert"], li[data-radix-collection-item]')]
      .map((e) => e.innerText?.replace(/\s+/g, " ").slice(0, 70))
      .filter(Boolean)
      .slice(0, 4),
  };
});

console.log("dialogs:", log.dialogs);
console.log("requests:", log.requests);
console.log("console errors:", log.consoleErrors);
console.log("after:", JSON.stringify(after, null, 2));
await page.screenshot({ path: "scripts/probe-blog-bulk-delete.png" });
console.log("screenshot: scripts/probe-blog-bulk-delete.png");

await browser.close();
