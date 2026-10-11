// Reproduce the reported "delete button does nothing" inside an embedded frame.
//
// The row and bulk delete handlers both begin with `confirm(...)`. Per spec, a
// document inside a sandboxed iframe **without** `allow-modals` has `confirm`
// return `false` immediately, with no dialog. The handler then returns before
// issuing any request, and shows no toast — so the button looks dead.
//
// This loads the real admin page inside such a frame and clicks the real
// button, then reports whether any request left the page.
//
// Usage: node scripts/probe-blog-delete-embedded.mjs [baseUrl]

import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:3000";

const browser = await chromium.launch();
const page = await browser.newPage();

const dialogs = [];
const requests = [];
page.on("dialog", async (d) => {
  dialogs.push(`${d.type()} :: ${d.message().slice(0, 60)}`);
  await d.accept();
});
page.on("request", (r) => {
  if (r.method() !== "GET") requests.push(`${r.method()} ${r.url().replace(base, "").slice(0, 80)}`);
});

// Log in on the top-level page first, so the session cookie exists for the
// framed document too (same origin).
await page.goto(`${base}/login`, { waitUntil: "domcontentloaded", timeout: 60000 });
await page.fill('input[type="tel"], input#phone', "09120000000").catch(() => {});
await page.fill('input[type="password"], input#password', "Admin@123456").catch(() => {});
await page.click('button[type="submit"]').catch(() => {});
await page.waitForTimeout(3500);
console.log("logged in, url:", page.url());

// Build the embedded frame WITHOUT allow-modals — the reported environment.
await page.evaluate((url) => {
  document.body.innerHTML = "";
  const f = document.createElement("iframe");
  f.id = "embed";
  f.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-popups");
  f.style.cssText = "width:1200px;height:800px;border:0";
  f.src = url;
  document.body.appendChild(f);
}, `${base}/admin/blog`);

const frame = page.frameLocator("#embed");
await page.waitForTimeout(6000);

const rowsBefore = await frame.locator("tbody tr").count();
console.log("rows in embedded frame:", rowsBefore);

const confirmWorks = await page.evaluate(() => {
  const f = document.getElementById("embed");
  try {
    return f.contentWindow.confirm("probe");
  } catch (e) {
    return `threw: ${e.message}`;
  }
});
console.log("confirm() inside the embedded frame returned:", JSON.stringify(confirmWorks));

// Target a throwaway row by title, never the first row: the first row is real
// content, and a probe that trashes it needs a manual restore every run.
const targetRow = frame.locator("tbody tr", { hasText: /verify-confirm|probe/ }).first();
const rowTrash = targetRow.locator('button[title="انتقال به سطل زباله"]');
console.log("row trash buttons in the throwaway row:", await rowTrash.count());
if (await rowTrash.count()) {
  await rowTrash.first().click();
  await page.waitForTimeout(1500);

  // The in-app confirmation replaced `window.confirm`. Find its confirm button
  // inside the frame and press it — the dialog is the whole point of the fix,
  // so the probe must exercise it, not just the opening click.
  const dialogConfirm = frame.getByRole("button", { name: /^(انتقال|حذف|تأیید|بازگردانی)$/ });
  const dialogCount = await dialogConfirm.count();
  console.log("in-app confirm buttons visible:", dialogCount);
  if (dialogCount) {
    await dialogConfirm.last().click();
    await page.waitForTimeout(3500);
  } else {
    console.log("no in-app dialog appeared — the fix did not take effect");
  }
}

const rowsAfter = await frame.locator("tbody tr").count();
console.log("rows after clicking delete:", rowsAfter);
console.log("dialogs seen:", dialogs.length ? dialogs : "(none)");
console.log("non-GET requests:", requests.filter((r) => !r.includes("login") && !r.includes("cart")));

await page.screenshot({ path: "scripts/probe-blog-delete-embedded.png" });
console.log("screenshot: scripts/probe-blog-delete-embedded.png");
await browser.close();
