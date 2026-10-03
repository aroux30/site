import { describe, it, expect, beforeEach, vi } from "vitest";

/**
 * The catalogue was a database table with a public endpoint and no reader:
 * `CATALOGUES` was `{ fa }` with an empty Persian map, and no code path could
 * ever add an entry. Every string an operator wrote through the admin API was
 * stored and never rendered, and the `t` fallback kept the UI looking fine —
 * which is exactly why it went unnoticed.
 *
 * These tests pin the wiring rather than the shape: a catalogue that is loaded
 * into a local variable nobody reads would pass every test about `translate`.
 */

describe("i18n catalogue loading", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("starts with an empty Persian catalogue and a key fallback", async () => {
    const mod = await import("@/lib/i18n");
    // Documented behaviour: a missing translation renders the key, never blank.
    expect(mod.fa).toEqual({});
    expect(mod.t("common.save")).toBe("common.save");
  });

  it("marks the default locale as already loaded", async () => {
    const mod = await import("@/lib/i18n");
    // fa is compiled in, so the loader must not spend a request on it.
    let called = false;
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async () => {
          called = true;
          return { locale: "fa", strings: {} };
        },
      },
    }));
    await mod.loadCatalogue("fa");
    expect(called).toBe(false);
  });

  it("fetches and installs a catalogue for another locale", async () => {
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async (locale: string) => ({
          locale,
          strings: { "common.save": "Save" },
        }),
      },
    }));
    const mod = await import("@/lib/i18n");
    await mod.loadCatalogue("en");
    // The whole point: a string written through the admin API now renders.
    expect(mod.t("common.save", undefined, "en")).toBe("Save");
  });

  it("falls back to the key when the endpoint fails", async () => {
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async () => {
          throw new Error("network down");
        },
      },
    }));
    const mod = await import("@/lib/i18n");
    await expect(mod.loadCatalogue("en")).resolves.toBeUndefined();
    expect(mod.t("common.save", undefined, "en")).toBe("common.save");
  });

  it("does not request a locale twice", async () => {
    let calls = 0;
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async (locale: string) => {
          calls += 1;
          return { locale, strings: {} };
        },
      },
    }));
    const mod = await import("@/lib/i18n");
    await mod.loadCatalogue("en");
    await mod.loadCatalogue("en");
    expect(calls).toBe(1);
  });

  it("invalidation lets an admin edit show without a reload", async () => {
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async (locale: string) => ({
          locale,
          strings: { "common.save": "Save" },
        }),
      },
    }));
    const mod = await import("@/lib/i18n");
    await mod.loadCatalogue("en");
    expect(mod.t("common.save", undefined, "en")).toBe("Save");

    mod.invalidateCatalogue("en");
    // Back to the key: the catalogue must be re-fetched, not stale.
    expect(mod.t("common.save", undefined, "en")).toBe("common.save");
  });

  it("interpolation still applies to a loaded string", async () => {
    vi.doMock("@/lib/api/settings", () => ({
      settingsI18nApi: {
        catalog: async (locale: string) => ({
          locale,
          strings: { "order.number": "Order {number}" },
        }),
      },
    }));
    const mod = await import("@/lib/i18n");
    await mod.loadCatalogue("en");
    expect(mod.t("order.number", { number: "12" }, "en")).toBe("Order 12");
  });

  it("keeps the default locale when everything is invalidated", async () => {
    const mod = await import("@/lib/i18n");
    mod.invalidateCatalogue();
    // Persian is compiled in, so a full reset must not leave it unloadable.
    expect(mod.t("common.save")).toBe("common.save");
  });
});
