/**
 * Admin USD→Toman updater panel: contract pins + regression guards.
 *
 * The page is a thin client over the currency admin endpoints. The things
 * worth pinning are the traps this project has hit before:
 *
 * 1. `last_*` runtime fields are server-owned — the API module must strip
 *    them before an update (the referrals `program_started_at` lesson).
 * 2. The nav entry must exist for /admin/currency or the reachability test
 *    fails.
 * 3. The log switch must NOT gate the price update in copy or code — the
 *    WordPress plugin stopped updating when its log switch was off; the UI
 *    text here must say what actually happens.
 * 4. USD numbers on the wire are STRINGS (pydantic Decimal) — the type says
 *    so, so nobody does arithmetic on them.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const API_SRC = readFileSync(
  join(process.cwd(), "lib", "api", "currency-admin.ts"),
  "utf-8",
);
const NAV_SRC = readFileSync(join(process.cwd(), "lib", "admin-nav.ts"), "utf-8");
const PAGE_SRC = readFileSync(
  join(process.cwd(), "app", "admin", "currency", "page.tsx"),
  "utf-8",
);
const SERVICES_SRC = readFileSync(
  join(process.cwd(), "lib", "api", "services.ts"),
  "utf-8",
);

describe("currency admin API contract", () => {
  it("uses the exact admin endpoints", () => {
    expect(API_SRC).toContain('"/admin/currency/config"');
    expect(API_SRC).toContain('"/admin/currency/update-now"');
    expect(API_SRC).toContain('"/admin/currency/history"');
    expect(API_SRC).toContain('"/admin/currency/history/export.csv"');
  });

  it("strips server-owned last_* fields before sending an update", () => {
    // The loop is the mechanism; without it the stale runtime state would
    // round-trip back to the server.
    expect(API_SRC).toContain("const SERVER_OWNED_PREFIX = \"last_\";");
    expect(API_SRC).toContain("if (key.startsWith(SERVER_OWNED_PREFIX)) continue;");
  });

  it("types USD decimal fields as strings (pydantic Decimal on the wire)", () => {
    // Arithmetic on a string is a bug; the comment must stay next to the type.
    expect(SERVICES_SRC).toContain("usd_price?: string | null;");
    expect(SERVICES_SRC).toContain("usd_sale_price?: string | null;");
    expect(SERVICES_SRC).toContain("serializes them as STRINGS");
  });
});

describe("admin nav registration", () => {
  it("registers /admin/currency in the store group", () => {
    const idx = NAV_SRC.indexOf('href: "/admin/currency"');
    expect(idx).toBeGreaterThan(-1);
    const line = NAV_SRC.slice(idx, idx + 120);
    expect(line).toContain("به‌روزرسانی قیمت دلاری");
    expect(line).toContain("icon: CircleDollarSign");
  });
});

describe("admin page wiring", () => {
  it("calls the real API module functions (not raw fetch)", () => {
    expect(PAGE_SRC).toContain("fetchUsdRateConfig");
    expect(PAGE_SRC).toContain("updateUsdRateConfig");
    expect(PAGE_SRC).toContain("runUsdRateUpdateNow");
    expect(PAGE_SRC).toContain("fetchRateHistory");
    expect(PAGE_SRC).toContain("exportRateHistory");
  });

  it("shows the status panel: current rate, last run, next run, managed count", () => {
    expect(PAGE_SRC).toContain("last_rate_rial");
    expect(PAGE_SRC).toContain("next_run_at");
    expect(PAGE_SRC).toContain("managed_variants");
    expect(PAGE_SRC).toContain("last_error");
  });

  it("says the log switch does NOT stop price updates", () => {
    // The plugin's trap, denied in the UI copy so the operator cannot
    // believe turning logging off pauses pricing.
    expect(PAGE_SRC).toContain("خاموش‌کردن آن فقط ثبت تاریخچه را متوقف می‌کند");
  });

  it("sets dir=rtl on the Tabs root (Radix defaults it to LTR)", () => {
    // Measured live 2026-10-16: with the prop absent, Radix renders the Tabs
    // root div with dir="ltr", which flipped every descendant back to LTR —
    // switches landed on the left and the status columns read backwards.
    // The fix is the explicit prop; this pin keeps it from being dropped.
    const idx = PAGE_SRC.indexOf("<Tabs defaultValue=");
    expect(idx).toBeGreaterThan(-1);
    const tag = PAGE_SRC.slice(idx, PAGE_SRC.indexOf(">", idx));
    expect(tag).toContain('dir="rtl"');
  });

  it("renders RTL and uses Lucide icons only (no emoji in the UI)", () => {
    expect(PAGE_SRC).toContain('dir="rtl"');
    const emoji = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}]/u;
    const jsxPart = PAGE_SRC.split("export default function")[1] ?? "";
    const jsxLiterals = jsxPart.replace(/\{[^}]*\}/g, "");
    expect(emoji.test(jsxLiterals)).toBe(false);
  });

  it("has a status filter with success and failed", () => {
    expect(PAGE_SRC).toContain("وضعیت اجرا");
    expect(PAGE_SRC).toContain('{ value: "success"');
    expect(PAGE_SRC).toContain('{ value: "failed"');
  });

  it("is server-paginated against the real total", () => {
    expect(PAGE_SRC).toContain("serverTotal={total}");
    expect(PAGE_SRC).toContain("onServerPageChange");
    expect(PAGE_SRC).toContain("HISTORY_PAGE_SIZE");
  });

  it("shows per-variant before/after detail (the plugin's log lines)", () => {
    expect(PAGE_SRC).toContain("old_price");
    expect(PAGE_SRC).toContain("new_price");
    expect(PAGE_SRC).toContain("usd_price");
  });

  it("edits the manual rate in Toman on a rial wire (money-unit trap)", () => {
    expect(PAGE_SRC).toContain("tomanToRial");
    expect(PAGE_SRC).toContain("fmtToman");
  });
});

describe("product editor USD fields", () => {
  const PRODUCTS_SRC = readFileSync(
    join(process.cwd(), "app", "admin", "products", "page.tsx"),
    "utf-8",
  );

  it("has both USD inputs with a two-decimal keystroke gate", () => {
    expect(PRODUCTS_SRC).toContain("prodUsdPrice");
    expect(PRODUCTS_SRC).toContain("prodUsdSalePrice");
    expect(PRODUCTS_SRC).toContain("if (!/^\\d{0,10}(\\.\\d{0,2})?$/.test(raw)) return;");
  });

  it("sends USD prices on the nested variant at create", () => {
    const idx = PRODUCTS_SRC.indexOf("usd_price: usdPrice");
    expect(idx).toBeGreaterThan(-1);
  });

  it("applies USD prices to the first variant on edit (variant PATCH)", () => {
    // The variant id resolves on demand when the edit modal's detail fetch
    // has not landed before a fast save — so the patch targets
    // variantIdForPatch, not the raw primaryVariantId state.
    expect(PRODUCTS_SRC).toContain("variantIdForPatch");
    expect(PRODUCTS_SRC).toContain("`/catalog/variants/${variantIdForPatch}`");
    // 0 = clear, the backend's documented semantic.
    expect(PRODUCTS_SRC).toContain("usd_price: usdPrice ?? 0");
  });
});
