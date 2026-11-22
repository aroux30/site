// Round-2 visual check (N1-N9). Seeds real data via the :3200 proxy (cookie
// auth — the login response has no access_token, only cookies), opens the admin
// console + widget, asserts the new render behaviors, cleans up.
const { chromium } = require("playwright");
const BASE = "http://localhost:3200";
const P = `${BASE}/api/v1`; // proxy origin: cookies + access token both work
const ADMIN = { phone: "09120000000", password: "Admin@123456" };
const KEY = "probe_r2_final";

const results = [];
const rec = (check, pass, detail = "") => results.push({ check, pass, detail });

(async () => {
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();
  const errors = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));
  page.on("pageerror", (e) => errors.push(String(e)));

  await page.request.post(`${P}/auth/login`, { data: ADMIN });

  // Snapshot the FULL widget config so teardown can restore EVERY field, not
  // just the ones this script remembers touching. (A crashed run once left
  // `proactive_enabled:true` behind — the popup would then show to real
  // visitors. Snapshot-before / write-back-after is the safe pattern.)
  const configSnapshot = (await (await page.request.get(`${P}/admin/chat/config`)).json()).config;

  // Seed: session + presence + a visitor msg + admin msgs exercising markers.
  await page.request.post(`${P}/chat/session`, { data: { session_key: KEY, user_name: "پروب نهایی" } });
  await page.request.post(`${P}/chat/heartbeat`, {
    data: { session_key: KEY, tab_id: "t1", page_url: "https://shop.test/product/42", page_title: "صفحه محصول" },
  });
  await page.request.post(`${P}/chat/message`, { data: { session_key: KEY, message: "سلام" } });
  for (const msg of [
    "[Voice Message](https://shop.test/media/v.webm)",
    "[Attachment: photo.png](https://shop.test/media/photo.png)",
    "ببین اینجا https://shop.test/help و ادامه",
  ]) {
    const r = await page.request.post(`${P}/admin/chat/send`, { data: { session_key: KEY, message: msg } });
    rec(`seed admin send ${msg.slice(0, 14)}`, r.status() === 201, `status=${r.status()}`);
  }

  // ── Admin console ──────────────────────────────────────────────────
  await page.goto(`${BASE}/admin/chat?session=${encodeURIComponent(KEY)}`, { waitUntil: "networkidle" });
  await page.waitForTimeout(3500);
  const scroller = page.locator('div[class*="space-y-2"][class*="overflow-y-auto"]').first();
  const audioN = await scroller.locator("audio").count();
  rec("N1 audio player in thread", audioN > 0, `audio=${audioN}`);
  rec("N1 image preview in thread", (await scroller.locator('img[src*="photo.png"]').count()) > 0);
  const threadText = await scroller.innerText();
  rec("N1 no raw marker in thread", !threadText.includes("[Voice Message]") && !threadText.includes("[Attachment:"));
  rec("N1 bare URL is a link", (await scroller.locator('a[href="https://shop.test/help"]').count()) > 0);
  rec("N9 avatars rendered", (await scroller.locator('div[class*="rounded-full"]').count()) >= 2);

  // ── Online tab ─────────────────────────────────────────────────────
  await page.getByRole("button", { name: /کاربران آنلاین/ }).click();
  await page.waitForTimeout(2000);
  const onlineText = await page.locator("body").innerText();
  rec("N4 UA parsed (device — browser / os)", /—/.test(onlineText));
  rec("N4 current-page card present", onlineText.includes("صفحه فعلی"));

  await browser.close();

  // Cleanup: delete the seeded session (this cascades its own presence rows —
  // delete_session purges `session_key|%`). NOTE — the browser page loads in
  // this run each mint a FRESH session key and heartbeat, so those keys leave
  // presence rows that no delete call targets. Purge them from the DB after:
  //   DELETE FROM chat_presence WHERE last_seen < now() - interval '30 seconds'
  // (safe — a genuinely-live tab keeps re-writing its row). The 1001 cycle hit
  // this same residue class.
  await fetch(`${P}/admin/chat/delete-session`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_key: KEY }),
  });

  // Restore the FULL config snapshot — every field this run (or a crashed prior
  // run) might have changed, so a test can never leave the widget misconfigured
  // for real visitors.
  await fetch(`${P}/admin/chat/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config: configSnapshot }),
  }).catch(() => {});

  const failed = results.filter((r) => !r.pass);
  console.log(JSON.stringify({ results, failed: failed.length, consoleErrors: errors.slice(0, 8) }, null, 2));
  process.exit(failed.length ? 1 : 0);
})().catch((e) => {
  console.error("FATAL", e);
  process.exit(2);
});
