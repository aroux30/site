/**
 * Admin referral program panel: contract pins + regression guards.
 *
 * The page is a thin client over three endpoints; the things worth pinning
 * are the contract shapes and the traps this project has hit before:
 *
 * 1. `program_started_at` must never be sent back on update — the backend
 *    owns the stamp, and echoing a stale value could re-open retroactive
 *    payouts. The API module strips it (pin below).
 * 2. The nav entry must exist for /admin/referrals or the reachability test
 *    fails — that test walks the filesystem itself, so here we only pin the
 *    nav registration line.
 * 3. There is NO manual sweep button (owner: a button with no log to check
 *    first is useless) — the history tab replaced it; rewards pay eagerly.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const API_SRC = readFileSync(
  join(process.cwd(), "lib", "api", "referrals-admin.ts"),
  "utf-8",
);
const NAV_SRC = readFileSync(join(process.cwd(), "lib", "admin-nav.ts"), "utf-8");
const PAGE_SRC = readFileSync(
  join(process.cwd(), "app", "admin", "referrals", "page.tsx"),
  "utf-8",
);

describe("referral admin API contract", () => {
  it("uses the exact admin endpoints", () => {
    expect(API_SRC).toContain('"/admin/referrals/config"');
    expect(API_SRC).toContain('"/admin/referrals/history"');
  });

  it("has no manual sweep endpoint anywhere (removed by owner request)", () => {
    expect(API_SRC).not.toContain("/sweep");
    expect(PAGE_SRC).not.toContain("runReferralSweep");
    expect(PAGE_SRC).not.toContain("اجرای تسویه");
  });

  it("strips program_started_at before sending an update", () => {
    // The destructive destructure is the mechanism; if it is removed the
    // stamp would round-trip back to the server.
    expect(API_SRC).toContain("const { program_started_at: _ignored, ...payload } = config;");
    expect(API_SRC).toContain("{ config: payload }");
  });
});

describe("admin nav registration", () => {
  it("registers /admin/referrals in the marketing group", () => {
    const idx = NAV_SRC.indexOf('href: "/admin/referrals"');
    expect(idx).toBeGreaterThan(-1);
    const line = NAV_SRC.slice(idx, idx + 120);
    expect(line).toContain("دعوت دوستان");
    expect(line).toContain("icon: UserPlus");
  });
});

describe("admin page wiring", () => {
  it("calls the real API module functions (not raw fetch)", () => {
    expect(PAGE_SRC).toContain("fetchReferralConfig");
    expect(PAGE_SRC).toContain("updateReferralConfig");
    expect(PAGE_SRC).toContain("fetchRewardHistory");
  });

  it("shows the program-start cut-off state", () => {
    // The operator must see whether the program has started (stamp present)
    // or is still dormant (amounts zero) — this is the retroactive-payout
    // guard made visible.
    expect(PAGE_SRC).toContain("program_started_at");
    expect(PAGE_SRC).toContain("هنوز شروع نشده");
  });

  it("renders RTL and uses Lucide icons only (no emoji in the UI)", () => {
    expect(PAGE_SRC).toContain('dir="rtl"');
    // No emoji characters in JSX text (the owner's admin standard).
    const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    // Strip the notification-template default strings which legitimately
    // carry a 🎁 from the backend defaults — the page shows them as editable
    // text, not decoration. They come from config state, not JSX literals.
    const jsxPart = PAGE_SRC.split("export default function")[1] ?? "";
    const jsxLiterals = jsxPart.replace(/\{[^}]*\}/g, "");
    expect(emoji.test(jsxLiterals)).toBe(false);
  });

  it("percent inputs accept at most two decimal digits (keystroke gate)", () => {
    // The regex is the keystroke filter: a third decimal digit never lands.
    expect(PAGE_SRC).toContain("const PERCENT_INPUT_RE = /^\\d{0,3}(\\.\\d{0,2})?$/;");
    // The gate must actually run on every change.
    expect(PAGE_SRC).toContain("if (!PERCENT_INPUT_RE.test(raw)) return;");
    // Percent fields are text inputs with decimal keyboard (a number input
    // silently accepts a third digit and rounds on read).
    expect(PAGE_SRC).toContain('inputMode="decimal"');
  });
});

describe("history tab", () => {
  it("has a kind filter with all three reward kinds", () => {
    expect(PAGE_SRC).toContain("نوع پاداش");
    expect(API_SRC).toContain('"signup_gift"');
    expect(API_SRC).toContain('"commission"');
    expect(API_SRC).toContain('"recharge_bonus"');
  });

  it("shows who received it and why (context columns)", () => {
    // The audit columns the owner asked for: receiver, reason, amount, date.
    expect(PAGE_SRC).toContain("گیرنده");
    expect(PAGE_SRC).toContain("بابت");
    expect(PAGE_SRC).toContain("مبلغ");
    expect(PAGE_SRC).toContain("تاریخ");
    // Context per kind: invited user / order number / top-up amount.
    expect(PAGE_SRC).toContain("invited_user_name");
    expect(PAGE_SRC).toContain("order_number");
  });

  it("is server-paginated against the real total", () => {
    expect(PAGE_SRC).toContain("serverTotal={total}");
    expect(PAGE_SRC).toContain("onServerPageChange");
  });

  it("every history column carries a Persian columnLabel (no raw keys in the picker)", () => {
    // The DataTable column-visibility control falls back to the column `key`
    // when `columnLabel` is missing — which rendered a picker full of
    // "kind / earner / level …" in the middle of a Persian panel. All six
    // history columns must set it.
    const labelCount = PAGE_SRC.split("columnLabel:").length - 1;
    expect(labelCount).toBeGreaterThanOrEqual(6);
    for (const label of ["نوع پاداش", "گیرنده", "لایه", "بابت", "مبلغ", "تاریخ"]) {
      expect(PAGE_SRC).toContain(`columnLabel: "${label}"`);
    }
  });

  it("has search, date range and CSV export wired to the API", () => {
    // Owner: paging 25-at-a-time through 20k rows is not a search. The tab
    // must offer free-text search, a date range, and an Excel export.
    expect(PAGE_SRC).toContain("جستجو");
    expect(PAGE_SRC).toContain('JalaliDatePicker');
    expect(PAGE_SRC).toContain("exportRewardHistory");
    expect(PAGE_SRC).toContain("خروجی اکسل");
    // The search must be debounced (a fetch per keystroke hammers the DB).
    expect(PAGE_SRC).toContain("setTimeout(() => setDebouncedSearch(search), 400)");
    // Export must send the SAME filters as the table (one filter builder).
    expect(PAGE_SRC).toContain("exportRewardHistory(filters())");
  });

  it("history API sends the filter params the backend expects", () => {
    expect(API_SRC).toContain("date_from");
    expect(API_SRC).toContain("date_to");
    expect(API_SRC).toContain('"/admin/referrals/history/export.csv"');
    expect(API_SRC).toContain('responseType: "blob"');
  });
});
