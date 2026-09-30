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

/** Gregorian ISO date/datetime → Jalali label (Persian digits). */
export function formatJalali(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = parseISO(iso);
    if (Number.isNaN(d.getTime())) return "—";
    return toPersianDigits(format(d, "yyyy/MM/dd"));
  } catch {
    return "—";
  }
}

/** Gregorian ISO datetime → Jalali date + Tehran time label. */
export function formatJalaliDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  try {
    const d = parseISO(iso);
    if (Number.isNaN(d.getTime())) return "—";
    const datePart = toPersianDigits(format(d, "yyyy/MM/dd"));
    const timePart = d.toLocaleTimeString("fa-IR", {
      hour: "2-digit",
      minute: "2-digit",
      timeZone: "Asia/Tehran",
    });
    return `${datePart} ساعت ${timePart}`;
  } catch {
    return "—";
  }
}
