/**
 * i18n infrastructure — locale registry + string catalogue.
 *
 * The storefront chrome is Persian (RTL, Jalali, Iranian payment stack); the
 * locale registry below is what makes a SECOND content locale possible
 * without a rewrite: content rows (blog posts, CMS pages) carry a ``locale``
 * and a ``translation_group``, the admin "ترجمه‌ها" page manages the links,
 * and the storefront LanguageSwitcher offers the sibling translations.
 *
 * Content-level i18n is enabled by the ``enabled_locales`` site option
 * (comma-separated, first entry is the default) — see
 * /api/v1/settings/public/routing.
 */

export type Locale = string;

export interface LocaleMeta {
  name: string; // native name shown in the switcher
  dir: "rtl" | "ltr";
}

/** Locales the UI knows how to label. Content locales come from settings. */
export const LOCALE_REGISTRY: Record<string, LocaleMeta> = {
  fa: { name: "فارسی", dir: "rtl" },
  en: { name: "English", dir: "ltr" },
  ar: { name: "العربية", dir: "rtl" },
};

export const DEFAULT_LOCALE: Locale = "fa";

/** Locales the build knows how to render (label + direction known). */
export const SUPPORTED_LOCALES: readonly Locale[] = Object.keys(LOCALE_REGISTRY);

export function isKnownLocale(locale: string): boolean {
  return locale in LOCALE_REGISTRY;
}

/** Right-to-left locales among the known set. */
export function isRtl(locale: Locale): boolean {
  return LOCALE_REGISTRY[locale]?.dir === "rtl";
}

/** Text direction for a locale, for ``<html dir>`` and layout decisions. */
export function direction(locale: Locale): "rtl" | "ltr" {
  return isRtl(locale) ? "rtl" : "ltr";
}

/** Native label for a locale (falls back to the code itself). */
export function localeName(locale: Locale): string {
  return LOCALE_REGISTRY[locale]?.name ?? locale;
}

/**
 * Placeholder interpolation, e.g. ``"سفارش {number}"`` with
 * ``{ number: "۱۲۳" }``. Kept deliberately minimal: no pluralisation engine,
 * because Persian has no plural agreement to encode and a half-built ICU
 * subset is worse than none.
 */
export function interpolate(
  template: string,
  params?: Record<string, string | number>,
): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (match, key: string) => {
    const value = params[key];
    return value === undefined ? match : String(value);
  });
}

/**
 * Persisted catalogue shape. Keys are dotted paths; values are the Persian
 * text. Flat on purpose — a nested tree invites key churn during migration
 * without adding lookup value.
 */
export type MessageCatalogue = Record<string, string>;

/**
 * The Persian catalogue. Starts nearly empty and grows as strings migrate out
 * of components; the ``t`` fallback makes a partial migration safe at every
 * step.
 */
export const fa: MessageCatalogue = {};

/**
 * Filled from the backend catalogue at runtime, once per locale.
 *
 * The catalogue was a database table with an endpoint and nothing read it:
 * ``CATALOGUES`` was ``{ fa }`` with an empty Persian map and no code path
 * that could ever add an entry, so every string an operator wrote through the
 * admin API was stored and never rendered. The `t` fallback kept the UI
 * working, which is exactly why it was not noticed.
 *
 * Populated lazily and never awaited at a call site: `translate` is called
 * during render, and a lookup must never block one. A component that renders
 * before the catalogue arrives gets the key, and the next render has the text.
 */
const CATALOGUES: Record<Locale, MessageCatalogue> = { fa };

let loaded: Promise<void> | null = null;

/** Which locales already have a catalogue loaded, for the switcher. */
const loadedLocales = new Set<string>(["fa"]);

/**
 * Fetch a locale's catalogue. Deduplicated: repeated calls before the first
 * resolves share one request, and a locale already loaded costs nothing.
 */
export function loadCatalogue(locale: Locale = DEFAULT_LOCALE): Promise<void> {
  if (loadedLocales.has(locale)) return Promise.resolve();
  if (loaded === null || !isKnownLocale(locale)) {
    loaded = (async () => {
      try {
        const { settingsI18nApi } = await import("@/lib/api/settings");
        const catalogue = await settingsI18nApi.catalog(locale);
        if (catalogue?.strings && Object.keys(catalogue.strings).length > 0) {
          CATALOGUES[locale] = { ...(CATALOGUES[locale] ?? {}), ...catalogue.strings };
        }
        loadedLocales.add(locale);
      } catch {
        // A missing catalogue is a missing translation, not a broken page:
        // `translate` falls back to the key, which is visible and harmless.
        // Marked loaded so a failing endpoint is not retried on every render.
        loadedLocales.add(locale);
      } finally {
        loaded = null;
      }
    })();
  }
  return loaded;
}

/** Forget the cached catalogue, so an admin edit shows without a reload. */
export function invalidateCatalogue(locale?: Locale): void {
  if (locale) {
    delete CATALOGUES[locale];
    loadedLocales.delete(locale);
    loaded = null;
    return;
  }
  for (const l of Array.from(loadedLocales)) {
    if (l !== DEFAULT_LOCALE) delete CATALOGUES[l];
  }
  loadedLocales.clear();
  loadedLocales.add(DEFAULT_LOCALE);
  loaded = null;
}

/**
 * Look a key up, with interpolation.
 *
 * An unknown key returns the key itself rather than throwing or rendering
 * empty — a missing translation must be *visible* (the dotted key in the UI
 * is obviously wrong) but must never blank a page.
 */
export function translate(
  key: string,
  params?: Record<string, string | number>,
  locale: Locale = DEFAULT_LOCALE,
): string {
  const template = CATALOGUES[locale]?.[key] ?? key;
  return interpolate(template, params);
}

/** Alias matching the convention most call sites use. */
export const t = translate;
