// Click the row-level trash icon on the blog list, exactly as reported, and
// capture everything needed to say why nothing appeared to happen:
// the confirm dialog, the network call, its status, and any toast.
//
// The row icon is a ghost button whose `title` is "انتقال به سطل زباله" — the
// same string as the bulk button, which is how an earlier probe clicked the
// wrong one.
//
// Usage: node scripts/probe-blog-row-delete.mjs [baseUrl]

import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:3000";

const browser = await chromium.launch();
const page = await browser.newPage();

const dialogs = [];
const net = [];
const consoleErrors = [];
const pageErrors = [];

page.on("dialog", async (d) => {
  dialogs.push(`${d.type()} :: ${d.message().slice(0, 90)}`);
  await d.accept();
});
page.on("request", (r) => {
  if (r.method() !== "GET") net.push(`>> ${r.method()} ${r.url().replace(base, "")}`);
});
page.on("response", async (r) => {
  if (r.request().method() !== "GET") net.push(`<< ${r.status()} ${r.url().replace(base, "")}`);
});
page.on("console", (m) => {
  if (m.type() === "error") consoleErrors.push(m.text().slice(0, 200));
});
page.on("pageerror", (e) => pageErrors.push(e.message.slice(0, 200)));

// Log in through the UI.
await page.goto(`${base}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.fill('input[type="tel"], input#phone', "09120000000").catch(() => {});
await page.fill('input[type="password"], input#password', "Admin@123456").catch(() => {});
await page.click('button[type="submit"]').catch(() => {});
await page.waitForTimeout(3500);

await page.goto(`${base}/admin/blog`, { waitUntil: "networkidle", timeout: 60000 });
await page.waitForTimeout(2500);

const before = await page.locator("tbody tr").count();
console.log("rows before:", before);

// The row-level trash icon, scoped to the first row's action cell.
const rowTrash = page.locator('tbody tr').first().locator('button[title="انتقال به سطل زباله"]');
console.log("row trash buttons in first row:", await rowTrash.count());
if (await rowTrash.count()) {
  await rowTrash.first().click();
  await page.waitForTimeout(3500);
}

const after = await page.evaluate(() => {
  const rows = [...document.querySelectorAll("tbody tr")];
  const toasts = [...document.querySelectorAll('[role="status"], [role="alert"], [data-radix-toast-viewport] li')]
    .map((e) => e.innerText?.replace(/\s+/g, " ").slice(0, 80))
    .filter(Boolean);
  return { rowCount: rows.length, toasts };
});

console.log("dialogs:", dialogs);
console.log("network:", net);
console.log("console errors:", consoleErrors);
console.log("page errors:", pageErrors);
console.log("rows after:", after.rowCount, "| toasts:", after.toasts);

await page.screenshot({ path: "scripts/probe-blog-row-delete.png" });
console.log("screenshot: scripts/probe-blog-row-delete.png");
await browser.close();
