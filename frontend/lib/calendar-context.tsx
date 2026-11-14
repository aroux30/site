"use client";

/**
 * Global calendar preference — Jalali (شمسی) or Gregorian (میلادی).
 *
 * Stored in localStorage so it survives page reloads and is shared across
 * all admin and storefront pages. The preference controls:
 *   - Date display in every table column (formatDate / formatDateTime)
 *   - The default calendar shown in every JalaliDatePicker
 *
 * Usage:
 *   const { calendarType, setCalendarType, formatDate, formatDateTime } = useCalendar();
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import { format as fnsJalaliFormat, parseISO as jalaliParseISO } from "date-fns-jalali";
import { format as fnsGregorianFormat, parseISO as gregorianParseISO } from "date-fns";
import { toPersianDigits } from "@/lib/utils";
import { getDateSettings, loadDateSettings, toZoned } from "@/lib/date-settings";

export type CalendarType = "jalali" | "gregorian";

const STORAGE_KEY = "calendarPref";

interface CalendarContextValue {
  calendarType: CalendarType;
  setCalendarType: (type: CalendarType) => void;
  /** ISO date/datetime → formatted string according to current preference */
  formatDate: (iso: string | null | undefined) => string;
  /** ISO datetime → formatted date + time according to current preference */
  formatDateTime: (iso: string | null | undefined) => string;
}

const CalendarContext = createContext<CalendarContextValue | null>(null);

// ---------------------------------------------------------------------------
// Gregorian helpers (date-fns)
// ---------------------------------------------------------------------------

function formatGregorianDate(iso: string): string {
  try {
    void loadDateSettings();
    const { timezone } = getDateSettings();
    const d = toZoned(gregorianParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    return fnsGregorianFormat(d, "yyyy/MM/dd");
  } catch {
    return "—";
  }
}

function formatGregorianDateTime(iso: string): string {
  try {
    void loadDateSettings();
    const { timezone } = getDateSettings();
    const d = toZoned(gregorianParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    return `${fnsGregorianFormat(d, "yyyy/MM/dd")} ${fnsGregorianFormat(d, "HH:mm")}`;
  } catch {
    return "—";
  }
}

// ---------------------------------------------------------------------------
// Jalali helpers (date-fns-jalali)
// ---------------------------------------------------------------------------

function formatJalaliDate(iso: string): string {
  try {
    void loadDateSettings();
    const { dateFormat, timezone } = getDateSettings();
    const d = toZoned(jalaliParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    return toPersianDigits(fnsJalaliFormat(d, dateFormat));
  } catch {
    return "—";
  }
}

function formatJalaliDateTime(iso: string): string {
  try {
    void loadDateSettings();
    const { dateFormat, timeFormat, timezone } = getDateSettings();
    const d = toZoned(jalaliParseISO(iso), timezone);
    if (Number.isNaN(d.getTime())) return "—";
    const datePart = toPersianDigits(fnsJalaliFormat(d, dateFormat));
    const timePart = toPersianDigits(fnsJalaliFormat(d, timeFormat));
    return `${datePart} ساعت ${timePart}`;
  } catch {
    return "—";
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

export function CalendarProvider({ children }: { children: React.ReactNode }) {
  const [calendarType, setCalendarTypeState] = useState<CalendarType>("jalali");

  // Hydrate from localStorage on mount (client only)
  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored === "gregorian" || stored === "jalali") {
        setCalendarTypeState(stored);
      }
    } catch {
      // localStorage unavailable (SSR, private mode)
    }
  }, []);

  const setCalendarType = useCallback((type: CalendarType) => {
    setCalendarTypeState(type);
    try {
      localStorage.setItem(STORAGE_KEY, type);
    } catch {
      // ignore
    }
    // Notify non-React consumers (e.g. formatJalali in lib/date.ts read from
    // localStorage) that the preference changed. Any component that shows
    // dates from the static helpers should listen for this event to re-render.
    if (typeof window !== "undefined") {
      window.dispatchEvent(new CustomEvent("calendarPrefChange", { detail: type }));
    }
  }, []);

  const formatDate = useCallback(
    (iso: string | null | undefined): string => {
      if (!iso) return "—";
      return calendarType === "jalali"
        ? formatJalaliDate(iso)
        : formatGregorianDate(iso);
    },
    [calendarType],
  );

  const formatDateTime = useCallback(
    (iso: string | null | undefined): string => {
      if (!iso) return "—";
      return calendarType === "jalali"
        ? formatJalaliDateTime(iso)
        : formatGregorianDateTime(iso);
    },
    [calendarType],
  );

  return (
    <CalendarContext.Provider
      value={{ calendarType, setCalendarType, formatDate, formatDateTime }}
    >
      {children}
    </CalendarContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useCalendar(): CalendarContextValue {
  const ctx = useContext(CalendarContext);
  if (!ctx) {
    // Outside the provider — return safe defaults (SSR / tests)
    return {
      calendarType: "jalali",
      setCalendarType: () => {},
      formatDate: (iso) => (iso ? formatJalaliDate(iso) : "—"),
      formatDateTime: (iso) => (iso ? formatJalaliDateTime(iso) : "—"),
    };
  }
  return ctx;
}

/**
 * Force-re-renders the calling component whenever the calendar preference
 * changes. Use this in any component that calls formatJalali / formatJalaliDateTime
 * from lib/date.ts directly (outside CalendarContext), so the displayed dates
 * update when the user switches calendar.
 */
export function useCalendarRefresh(): void {
  const [, forceUpdate] = React.useReducer((n: number) => n + 1, 0);
  React.useEffect(() => {
    const handler = () => forceUpdate();
    window.addEventListener("calendarPrefChange", handler);
    return () => window.removeEventListener("calendarPrefChange", handler);
  }, []);
}
