/**
 * Shared Jalali date helpers (admin UI).
 *
 * The project renders dates in Jalali for Persian users but exchanges plain
 * Gregorian ISO dates with the API. date-fns-jalali is already a dependency
 * (previously unused); these helpers are the single place admin pages do
 * the conversion, so date handling stops being ad-hoc Intl calls per page.
 */

import { format, parseISO } from "date-fns-jalali";
import { toPersianDigits } from "@/lib/utils";
import { getDateSettings, loadDateSettings, toZoned } from "@/lib/date-settings";

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
 * Gregorian ISO date/datetime → Jalali label (Persian digits).
 *
 * The pattern and the timezone come from the site options; before this, both
 * were the literals "yyyy/MM/dd" and "Asia/Tehran", which is why the
 * date_format and timezone_string settings changed nothing. The loader is fired
 * and not awaited: a date must render now, and the setting arriving a moment
 * later is only visible on the next render of that date.
 */
export function formatJalali(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    void loadDateSettings();
    const { dateFormat, timezone } = getDateSettings();
    const d = toZoned(parseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    return toPersianDigits(format(d, dateFormat));
  } catch {
    return "—";
  }
}

/** Gregorian ISO datetime → Jalali date + time, both from the site options. */
export function formatJalaliDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    void loadDateSettings();
    const { dateFormat, timeFormat, timezone } = getDateSettings();
    const d = toZoned(parseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    const datePart = toPersianDigits(format(d, dateFormat));
    const timePart = toPersianDigits(format(d, timeFormat));
    return `${datePart} ساعت ${timePart}`;
  } catch {
    return "—";
  }
}
