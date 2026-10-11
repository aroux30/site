// Reproduce "the delete button does nothing" in the admin blog table.
//
// Two delete affordances exist and the report covers both: the row-level trash
// icon and the bulk "انتقال به سطل زباله" button in the bulk action bar.
//
// The handler for both starts with `confirm(...)`. A confirm that is dismissed
// — or blocked by the embedding context — returns false and the function
// returns *before* any request, with no toast and no error. That is
// indistinguishable from "the button is dead", so this probe records whether a
// dialog appeared and how it was answered.
//
// Usage: node scripts/probe-blog-delete.mjs [baseUrl]

import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:3000";

const browser = await chromium.launch();
const ctx = await browser.newContext();
const page = await ctx.newPage();

const dialogs = [];
const requests = [];
const toasts = [];

page.on("dialog", async (d) => {
  dialogs.push(`${d.type()}: ${d.message().slice(0, 80)}`);
  await d.accept(); // answer "OK", the way a user confirming would
});
page.on("request", (r) => {
  if (r.method() !== "GET") requests.push(`${r.method()} ${r.url().slice(0, 120)}`);
});
page.on("response", async (r) => {
  if (r.request().method() === "DELETE" || r.url().includes("bulk")) {
    requests.push(`  -> ${r.status()} ${r.url().slice(0, 100)}`);
  }
});

// Log in through the UI so the session cookie is a real one.
await page.goto(`${base}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.fill('input[name="phone"], input[type="tel"], input#phone', "09120000000").catch(() => {});
await page.fill('input[type="password"], input#password', "Admin@123456").catch(() => {});
await page.click('button[type="submit"]').catch(() => {});
await page.waitForTimeout(3500);
console.log("after login, url:", page.url());

await page.goto(`${base}/admin/blog`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2500);

const before = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("tbody tr")];
  return {
    rowCount: rows.length,
    firstTitle: rows[0]?.innerText?.split("\n")[0]?.slice(0, 50) ?? null,
    hasError: /خطایی در بارگذاری|یافت نشد/.test(document.body.innerText),
  };
});
console.log("table before:", JSON.stringify(before));

// ── Row-level trash icon (the Trash2 button in the actions column) ──────────
const rowTrash = page.locator('tbody tr').first().locator('button[title="انتقال به سطل زباله"]');
console.log("row trash button count:", await rowTrash.count());
if (await rowTrash.count()) {
  await rowTrash.first().click();
  await page.waitForTimeout(2500);
}

const afterRow = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("tbody tr")];
  return {
    rowCount: rows.length,
    bodyText: (document.body.innerText || "").slice(0, 200).replace(/\s+/g, " "),
  };
});
console.log("dialogs seen:", dialogs);
console.log("non-GET requests:", requests);
console.log("table after row-trash click:", JSON.stringify(afterRow));

await page.screenshot({ path: "scripts/probe-blog-delete.png" });
console.log("screenshot: scripts/probe-blog-delete.png");

await browser.close();
