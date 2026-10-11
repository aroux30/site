// Open the blog article in a real browser and report what a reader actually
// sees: console errors, failed requests, and the visible error UI.
//
// The SSR HTML is clean for this page, so a plain HTTP fetch cannot see the
// failure — it happens after hydration, in the client. This drives Chromium so
// the question "what does the page show?" is answered by the page.
//
// Usage: node scripts/probe-blog-page.mjs [url] [port-for-api-logging]

import { chromium } from "playwright";

const url = process.argv[2] || "http://localhost:3200/blog/pubg-mobile";

const browser = await chromium.launch();
const page = await browser.newPage();

const consoleErrors = [];
const failedRequests = [];
const badResponses = [];

page.on("console", (msg) => {
  if (msg.type() === "error") consoleErrors.push(msg.text().slice(0, 300));
});
page.on("pageerror", (err) => consoleErrors.push(`[pageerror] ${err.message}`.slice(0, 300)));
page.on("requestfailed", (req) => {
  failedRequests.push(`${req.method()} ${req.url().slice(0, 160)} :: ${req.failure()?.errorText}`);
});
page.on("response", (res) => {
  if (res.status() >= 400) badResponses.push(`${res.status()} ${res.request().method()} ${res.url().slice(0, 160)}`);
});

await page.goto(url, { waitUntil: "networkidle", timeout: 60000 });
// Let the client-side fetches settle (comments, options, avatars).
await page.waitForTimeout(4000);

const visible = await page.evaluate(() => {
  const body = document.body.innerText || "";
  const article = document.querySelector("article");
  return {
    title: document.title,
    h1: document.querySelector("h1")?.innerText?.slice(0, 120) ?? null,
    articlePresent: Boolean(article),
    articleTextLength: article ? article.innerText.length : 0,
    // Next's error boundary renders into <body>; catch its markers.
    looksLikeErrorBoundary: /Application error|Internal Server Error|خطای داخلی|مشکلی پیش آمد/i.test(body),
    // The site-level "failed to load" UI.
    showsLoadFailure: /مشکلی در بارگذاری|بارگذاری این صفحه|اتصال به سرویس/i.test(body),
    bodyHead: body.slice(0, 400).replace(/\s+/g, " "),
  };
});

console.log("URL:", url);
console.log("--- what the page shows ---");
console.log(JSON.stringify(visible, null, 2));
console.log("--- console errors (" + consoleErrors.length + ") ---");
for (const e of [...new Set(consoleErrors)].slice(0, 12)) console.log("  " + e);
console.log("--- failed requests (" + failedRequests.length + ") ---");
for (const e of [...new Set(failedRequests)].slice(0, 12)) console.log("  " + e);
console.log("--- 4xx/5xx responses (" + badResponses.length + ") ---");
for (const e of [...new Set(badResponses)].slice(0, 15)) console.log("  " + e);

await page.screenshot({ path: "scripts/probe-blog-page.png", fullPage: false });
console.log("screenshot: scripts/probe-blog-page.png");

await browser.close();
