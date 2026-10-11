// Sweep the storefront for pages killed by the same class of bug: an image URL
// on a host `next/image` rejects. The blog article failed this way, but any
// page rendering a stored or user-supplied image URL has the same exposure.
//
// Reports, per URL: HTTP status, whether Next's error boundary took over, the
// page's <h1>, and any console error naming an unconfigured host.
//
// Usage: node scripts/sweep-image-host-pages.mjs [baseUrl]

import { chromium } from "playwright";

const base = process.argv[2] || "http://localhost:3000";
const PATHS = [
  "/",
  "/products",
  "/blog",
  "/blog/pubg-mobile",
  "/blog/category/pubg-mobile",
  "/blog/tag/ gaming",
  "/cart",
  "/search?q=پابجی",
  "/account",
  "/login",
  "/contact",
  "/about",
];

const browser = await chromium.launch();
const page = await browser.newPage();
let bad = 0;

for (const path of PATHS) {
  const errors = [];
  const onConsole = (m) => {
    if (m.type() === "error") errors.push(m.text());
  };
  const onErr = (e) => errors.push(`[pageerror] ${e.message}`);
  page.on("console", onConsole);
  page.on("pageerror", onErr);

  let status = "?", h1 = "", boundary = false, note = "";
  try {
    const res = await page.goto(base + path, { waitUntil: "networkidle", timeout: 45000 });
    status = res ? res.status() : "?";
    await page.waitForTimeout(1200);
    const info = await page.evaluate(() => ({
      h1: document.querySelector("h1")?.innerText?.trim()?.slice(0, 70) ?? "(no h1)",
      boundary: /خطایی در بارگذاری صفحه|Application error|Internal Server Error/i.test(
        document.body.innerText || "",
      ),
      textLen: (document.body.innerText || "").length,
    }));
    h1 = info.h1;
    boundary = info.boundary;
    note = `${info.textLen} chars`;
  } catch (err) {
    note = `NAV FAIL: ${String(err).split("\n")[0].slice(0, 90)}`;
  }

  const imgErr = errors.find((e) => /not configured under images|Invalid src prop/i.test(e));
  const realErr = errors.filter((e) => !/favicon|Download the React DevTools/i.test(e));
  const ok = !boundary && !imgErr;
  if (!ok) bad++;
  page.off("console", onConsole);
  page.off("pageerror", onErr);

  console.log(
    `${ok ? "ok  " : "FAIL"} ${String(status).padEnd(4)} ${path.padEnd(30)} h1=${h1.slice(0, 40).padEnd(42)} ${note}`,
  );
  if (imgErr) console.log(`       image host error: ${imgErr.split("\n")[0].slice(0, 130)}`);
  else if (realErr.length) console.log(`       console: ${realErr[0].split("\n")[0].slice(0, 130)}`);
}

console.log(`\n${bad === 0 ? "all pages clean" : `${bad} page(s) broken`}`);
await browser.close();
process.exit(bad === 0 ? 0 : 1);
