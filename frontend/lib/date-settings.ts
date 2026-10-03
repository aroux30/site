"use client";

/**
 * Date and time presentation, driven by the site options.
 *
 * `date_format`, `time_format` and `timezone_string` were seeded and never read:
 * `lib/date.ts` hardcoded "yyyy/MM/dd" and "Asia/Tehran", so a store that wanted
 * ۱۴۰۴/۰۵/۱۲ or Tehran-year-only had no way to get it and no way to change it.
 *
 * The 38 call sites keep calling `formatJalali` / `formatJalaliDateTime`. They
 * read the format from here at call time rather than from a prop, so no
 * component has to learn where the setting comes from and no caller has to be
 * touched.
 *
 * A module-level cache rather than React state: these are read on every render
 * of every admin and storefront page, and a hook would force a re-render of
 * whichever page happens to render a date after the setting loads.
 *
 * Loading is deliberately quiet. A date that renders with the default format for
 * the moment the option arrives is invisible; a date that renders "—" until it
 * arrives is a page full of placeholders.
 */

import { siteOptionsApi } from "@/lib/api/wp-parity";

export const OPTION_DATE_FORMAT = "date_format";
export const OPTION_TIME_FORMAT = "time_format";
export const OPTION_TIMEZONE = "timezone_string";

/** What a store gets if the options are missing or unreadable. */
export const DEFAULT_DATE_FORMAT = "yyyy/MM/dd";
export const DEFAULT_TIME_FORMAT = "HH:mm";
export const DEFAULT_TIMEZONE = "Asia/Tehran";

/**
 * date-fns-jalali pattern vocabulary, because that is what the formatter takes.
 * WordPress stores PHP date() formats, which are a different language entirely
 * (``d/m/Y`` versus ``dd/MM/yyyy``). The seeded values are PHP-shaped, so they
 * are translated on the way in rather than stored twice.
 */
const PHP_TO_JALALI = new Map<string, string>([
  // Day
  ["d", "dd"],
  ["j", "d"],
  ["D", "EEE"],
  ["l", "EEEE"],
  // Month
  ["F", "MMMM"],
  ["M", "MMM"],
  ["m", "MM"],
  ["n", "M"],
  // Year
  ["Y", "yyyy"],
  ["y", "yy"],
  // Time
  ["a", "aa"],
  ["A", "aaa"],
  ["g", "h"],
  ["G", "H"],
  ["h", "hh"],
  ["H", "HH"],
  ["i", "mm"],
  ["s", "ss"],
]);

function phpToJalaliPattern(format: string): string {
  // A value that is already a date-fns pattern is used as-is.
  //
  // The test has to be "does it contain a repeated format letter", because the
  // two vocabularies share their single letters: PHP's `Y/m/d` and date-fns'
  // `yyyy/MM/dd` are made of the same characters. The only reliable difference
  // is repetition — a date-fns pattern never writes `Y` or `D` or `a`, and
  // always doubles the letters it uses. Checking for `yyyy|MM|dd|HH|mm|ss`
  // directly avoids the trap: the earlier version rejected the very pattern it
  // was trying to preserve, because `y` is also PHP's year letter.
  // Every date-fns pattern letter is written at least twice, so a single H
  // or a single s is PHP's hour/second and not the modern form.
  if (/y{2,4}|M{2,4}|d{2,4}|H{2}|m{2,4}|s{2}|E{2,4}/.test(format) && !/[FjnDaGL]/.test(format)) {
    return format;
  }
  let out = "";
  for (let i = 0; i < format.length; i++) {
    // noUncheckedIndexedAccess makes an in-range index string | undefined, so
    // the character is normalised once here rather than at every use.
    const ch = format[i] ?? "";
    if (ch === "\\" && i + 1 < format.length) {
      // An escaped character is a literal in PHP date(); keep it verbatim.
      out += format[++i] ?? "";
      continue;
    }
    // An unmapped character is a literal separator ("/", "-", ":") and
    // passes through unchanged.
    // An unmapped character is a literal separator ("/", "-", ":") and
    // passes through unchanged.
    out += PHP_TO_JALALI.get(ch) ?? ch;
  }
  return out || DEFAULT_DATE_FORMAT;
}

interface DateSettings {
  dateFormat: string;
  timeFormat: string;
  timezone: string;
  loaded: boolean;
}

const cache: DateSettings = {
  dateFormat: DEFAULT_DATE_FORMAT,
  timeFormat: DEFAULT_TIME_FORMAT,
  timezone: DEFAULT_TIMEZONE,
  loaded: false,
};

let inFlight: Promise<void> | null = null;

/** Read the three options once. Safe to call from anywhere; deduplicated. */
export function loadDateSettings(): Promise<void> {
  if (cache.loaded) return Promise.resolve();
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      // One request, not three: siteOptionsApi has no per-key getter, and three
      // reads of the same table on every page load is three round trips for
      // three values that ship together.
      const all = (await siteOptionsApi.list()) ?? {};
      const date = all[OPTION_DATE_FORMAT];
      const time = all[OPTION_TIME_FORMAT];
      const tz = all[OPTION_TIMEZONE];
      if (date) cache.dateFormat = phpToJalaliPattern(date);
      if (time) cache.timeFormat = phpToJalaliPattern(time);
      if (tz && isValidTimeZone(tz)) cache.timezone = tz;
    } catch {
      // A missing options endpoint must not break every date on the site: the
      // defaults above are what these were hardcoded to anyway.
    } finally {
      cache.loaded = true;
      inFlight = null;
    }
  })();
  return inFlight;
}

/**
 * Whether a string is a timezone the runtime knows.
 *
 * `Intl` throws on an unknown zone, and a bad value in the options table would
 * then take down every page that renders a date. The store's own option is not
 * trusted here.
 */
export function isValidTimeZone(tz: string): boolean {
  if (!tz) return false;
  try {
    new Intl.DateTimeFormat("en-US", { timeZone: tz });
    return true;
  } catch {
    return false;
  }
}

/** The formats currently in effect. Exposed for the settings screen preview. */
export function getDateSettings(): Readonly<DateSettings> {
  return cache;
}

/** Test seam: reset the cache so a suite can re-run the loader. */
export function __resetDateSettingsCache(): void {
  cache.dateFormat = DEFAULT_DATE_FORMAT;
  cache.timeFormat = DEFAULT_TIME_FORMAT;
  cache.timezone = DEFAULT_TIMEZONE;
  cache.loaded = false;
  inFlight = null;
}

/**
 * Render a Date in the configured timezone.
 *
 * `parseISO` yields a Date in the browser's zone, and `format()` then reads it
 * in that same zone — so a visitor in another timezone sees their own date, not
 * the store's. Both halves are corrected here: the instant is shifted into the
 * configured zone and the formatter is told to read it back out of that zone,
 * which together leave the wall-clock reading correct.
 */
export function toZoned(d: Date, timezone: string): Date {
  if (!isValidTimeZone(timezone)) return d;
  // The zone's offset at this instant, expressed in the browser's own zone.
  const asZoned = new Date(
    d.toLocaleString("en-US", { timeZone: timezone, hour12: false }),
  );
  return asZoned;
}

export { phpToJalaliPattern };
