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

const CATALOGUES: Record<Locale, MessageCatalogue> = { fa };

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
