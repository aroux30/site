/**
 * Shared date helpers — calendar-aware (Jalali/Gregorian).
 *
 * The project renders dates in Jalali for Persian users but exchanges plain
 * Gregorian ISO dates with the API. These helpers read the user's calendar
 * preference from localStorage ("calendarPref") — same key used by the
 * CalendarProvider context and JalaliDatePicker. When the preference is
 * "gregorian", dates display in the Gregorian calendar; otherwise they
 * default to Jalali.
 *
 * date-fns-jalali is already a dependency; date-fns handles Gregorian.
 */

import { format as fnsJalaliFormat, parseISO as jalaliParseISO } from "date-fns-jalali";
import { format as fnsGregorianFormat, parseISO as gregorianParseISO } from "date-fns";
import { toPersianDigits } from "@/lib/utils";
import { getDateSettings, loadDateSettings, toZoned } from "@/lib/date-settings";

/** Read the calendar preference from localStorage (safe for SSR). */
function getCalendarPref(): "jalali" | "gregorian" {
  if (typeof window === "undefined") return "jalali";
  try {
    const pref = localStorage.getItem("calendarPref");
    return pref === "gregorian" ? "gregorian" : "jalali";
  } catch {
    return "jalali";
  }
}

/** Gregorian Date → ISO date string (yyyy-MM-dd) for API query params. */
export function toApiDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Today as an ISO date string. */
export function todayApiDate(): string {
  return toApiDate(new Date());
}

/** ISO date N days before today. */
export function daysAgoApiDate(days: number): string {
  return toApiDate(new Date(Date.now() - days * 24 * 60 * 60 * 1000));
}

/**
 * ISO date/datetime → formatted label based on calendar preference.
 *
 * Jalali mode: Persian digits, date-fns-jalali format from site settings.
 * Gregorian mode: standard yyyy/MM/dd format.
 */
export function formatJalali(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    void loadDateSettings();
    const { dateFormat, timezone } = getDateSettings();
    const pref = getCalendarPref();

    if (pref === "gregorian") {
      const d = toZoned(gregorianParseISO(iso), timezone);
      if (Number.isNaN(d.getTime())) return "—";
      return fnsGregorianFormat(d, "yyyy/MM/dd");
    }

    const d = toZoned(jalaliParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    return toPersianDigits(fnsJalaliFormat(d, dateFormat));
  } catch {
    return "—";
  }
}

/**
 * ISO datetime → formatted date + time based on calendar preference.
 */
export function formatJalaliDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    void loadDateSettings();
    const { dateFormat, timeFormat, timezone } = getDateSettings();
    const pref = getCalendarPref();

    if (pref === "gregorian") {
      const d = toZoned(gregorianParseISO(iso), timezone);
      if (Number.isNaN(d.getTime())) return "—";
      return `${fnsGregorianFormat(d, "yyyy/MM/dd")} ${fnsGregorianFormat(d, "HH:mm")}`;
    }

    const d = toZoned(jalaliParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    const datePart = toPersianDigits(fnsJalaliFormat(d, dateFormat));
    const timePart = toPersianDigits(fnsJalaliFormat(d, timeFormat));
    return `${datePart} ساعت ${timePart}`;
  } catch {
    return "—";
  }
}
