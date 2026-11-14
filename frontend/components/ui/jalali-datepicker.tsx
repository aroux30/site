"use client";

import * as React from "react";
import { Calendar as CalendarIcon, X } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { toPersianDigits } from "@/lib/utils";
import { useCalendar, type CalendarType } from "@/lib/calendar-context";

interface JalaliDatePickerProps {
  value?: string; // ISO date string (yyyy-MM-dd)
  onChange?: (value: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  calendarType?: CalendarType;
  onCalendarTypeChange?: (type: CalendarType) => void;
}

const JALALI_MONTHS = [
  "فروردین","اردیبهشت","خرداد","تیر","مرداد","شهریور",
  "مهر","آبان","آذر","دی","بهمن","اسفند",
] as const;

const GREGORIAN_MONTHS = [
  "January","February","March","April","May","June",
  "July","August","September","October","November","December",
] as const;

const JALALI_WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"] as const;
const GREGORIAN_WEEKDAYS = ["Su", "Mo", "Tu", "We", "Th", "Fr", "Sa"] as const;

// ---------------------------------------------------------------------------
// Pure Jalali ↔ Gregorian math (no external deps)
// ---------------------------------------------------------------------------

function toJalali(gy: number, gm: number, gd: number): [number, number, number] {
  const g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334] as const;
  let jy = gy <= 1600 ? 0 : 979;
  gy -= gy <= 1600 ? 621 : 1600;
  const gy2 = gm > 2 ? gy + 1 : gy;
  let days =
    365 * gy +
    Math.floor((gy2 + 3) / 4) -
    Math.floor((gy2 + 99) / 100) +
    Math.floor((gy2 + 399) / 400) -
    80 +
    gd +
    (g_d_m[gm - 1] ?? 0);
  jy += 33 * Math.floor(days / 12053);
  days %= 12053;
  jy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    jy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  const jm = days < 186 ? 1 + Math.floor(days / 31) : 7 + Math.floor((days - 186) / 30);
  const jd = 1 + (days < 186 ? days % 31 : (days - 186) % 30);
  return [jy, jm, jd];
}

function toGregorian(jy: number, jm: number, jd: number): [number, number, number] {
  let gy = jy <= 979 ? 621 : 1600;
  jy -= jy <= 979 ? 0 : 979;
  let days =
    365 * jy +
    Math.floor(jy / 33) * 8 +
    Math.floor(((jy % 33) + 3) / 4) +
    78 +
    jd +
    (jm < 7 ? (jm - 1) * 31 : (jm - 7) * 30 + 186);
  gy += 400 * Math.floor(days / 146097);
  days %= 146097;
  if (days > 36524) {
    gy += 100 * Math.floor(--days / 36524);
    days %= 36524;
    if (days >= 365) days++;
  }
  gy += 4 * Math.floor(days / 1461);
  days %= 1461;
  if (days > 365) {
    gy += Math.floor((days - 1) / 365);
    days = (days - 1) % 365;
  }
  // month lookup
  const sal_a = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334, 365] as const;
  let gm = 0;
  for (let i = 0; i < 12; i++) {
    if ((sal_a[i + 1] ?? 366) > days) { gm = i; break; }
  }
  const gd = days - (sal_a[gm] ?? 0) + 1;
  return [gy, gm + 1, gd];
}

function isJalaliLeapYear(jy: number): boolean {
  const leapYears = [1, 5, 9, 13, 17, 22, 26, 30];
  const rem = jy % 33;
  return leapYears.includes(rem);
}

function getJalaliMonthLength(jy: number, jm: number): number {
  if (jm <= 6) return 31;
  if (jm <= 11) return 30;
  return isJalaliLeapYear(jy) ? 30 : 29;
}

function getDaysInMonth(year: number, month: number, isJalaliCal: boolean): number {
  if (isJalaliCal) return getJalaliMonthLength(year, month);
  return new Date(year, month, 0).getDate();
}

function getFirstDayOfMonth(year: number, month: number, isJalaliCal: boolean): number {
  if (isJalaliCal) {
    const [gy, gm, gd] = toGregorian(year, month, 1);
    const day = new Date(gy, gm - 1, gd).getDay();
    // Saturday = 0 in Jalali week; JS Saturday = 6 → offset by 1
    return (day + 1) % 7;
  }
  return new Date(year, month - 1, 1).getDay();
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function JalaliDatePicker({
  value,
  onChange,
  placeholder = "انتخاب تاریخ",
  className,
  disabled = false,
  calendarType: controlledCalendarType,
  onCalendarTypeChange,
}: JalaliDatePickerProps) {
  const [open, setOpen] = React.useState(false);
  const globalCalendar = useCalendar();

  // Local calendar type — isolated to this picker only.
  // Starts from the global preference but switching inside the popup does NOT
  // affect the rest of the site (no global setCalendarType call).
  const [localCalendarType, setLocalCalendarType] = React.useState<CalendarType>(
    () => controlledCalendarType ?? globalCalendar.calendarType,
  );

  // If global preference changes (via the header toggle), reset the local one too.
  React.useEffect(() => {
    if (!controlledCalendarType) {
      setLocalCalendarType(globalCalendar.calendarType);
    }
  }, [globalCalendar.calendarType, controlledCalendarType]);

  const isControlled = controlledCalendarType !== undefined;
  const calendarType = isControlled ? controlledCalendarType! : localCalendarType;

  const setCalendarType = React.useCallback(
    (type: CalendarType) => {
      if (isControlled) {
        onCalendarTypeChange?.(type);
      } else {
        // Only update local state — does NOT touch the global calendar preference.
        setLocalCalendarType(type);
      }
    },
    [isControlled, onCalendarTypeChange],
  );

  // ── today ─────────────────────────────────────────────────────────────────
  const today = React.useMemo(() => {
    const now = new Date();
    const gy = now.getFullYear();
    const gm = now.getMonth() + 1;
    const gd = now.getDate();
    const [jy, jm, jd] = toJalali(gy, gm, gd);
    return {
      gregorian: { year: gy, month: gm, day: gd },
      jalali:    { year: jy, month: jm, day: jd },
    };
  }, []);

  // ── selected date (parsed from ISO value) ─────────────────────────────────
  const selectedDate = React.useMemo(() => {
    if (!value) return null;
    const d = new Date(value + "T00:00:00"); // avoid timezone shift
    if (isNaN(d.getTime())) return null;
    const gy = d.getFullYear();
    const gm = d.getMonth() + 1;
    const gd = d.getDate();
    const [jy, jm, jd] = toJalali(gy, gm, gd);
    return {
      gregorian: { year: gy, month: gm, day: gd },
      jalali:    { year: jy, month: jm, day: jd },
    };
  }, [value]);

  // ── view state ────────────────────────────────────────────────────────────
  const [viewYear, setViewYear] = React.useState(
    () => selectedDate?.[calendarType].year ?? today[calendarType].year,
  );
  const [viewMonth, setViewMonth] = React.useState(
    () => selectedDate?.[calendarType].month ?? today[calendarType].month,
  );

  // When calendar type changes, convert the current view to the new calendar.
  React.useEffect(() => {
    if (selectedDate) {
      setViewYear(selectedDate[calendarType].year);
      setViewMonth(selectedDate[calendarType].month);
    } else {
      // No date selected — show today in the new calendar system
      setViewYear(today[calendarType].year);
      setViewMonth(today[calendarType].month);
    }
  }, [selectedDate, calendarType, today]);

  // ── display text (uses GLOBAL preference for consistency with table dates) ──
  const displayText = React.useMemo(() => {
    if (!selectedDate) return placeholder;
    const displayPref = controlledCalendarType ?? globalCalendar.calendarType;
    if (displayPref === "jalali") {
      const { year, month, day } = selectedDate.jalali;
      return toPersianDigits(
        `${year}/${String(month).padStart(2, "0")}/${String(day).padStart(2, "0")}`,
      );
    }
    const { year, month, day } = selectedDate.gregorian;
    return `${year}/${String(month).padStart(2, "0")}/${String(day).padStart(2, "0")}`;
  }, [selectedDate, globalCalendar.calendarType, controlledCalendarType, placeholder]);

  // ── handlers ──────────────────────────────────────────────────────────────
  const handleDateSelect = (day: number) => {
    let isoDate: string;
    if (calendarType === "jalali") {
      const [gy, gm, gd] = toGregorian(viewYear, viewMonth, day);
      isoDate = `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
    } else {
      isoDate = `${viewYear}-${String(viewMonth).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
    }
    onChange?.(isoDate);
    setOpen(false);
  };

  const handlePrevMonth = () => {
    if (viewMonth === 1) { setViewMonth(12); setViewYear(viewYear - 1); }
    else setViewMonth(viewMonth - 1);
  };

  const handleNextMonth = () => {
    if (viewMonth === 12) { setViewMonth(1); setViewYear(viewYear + 1); }
    else setViewMonth(viewMonth + 1);
  };

  const handleToday = () => {
    // Compute today's ISO date directly — avoids stale closure on viewYear/viewMonth
    const now = new Date();
    const gy = now.getFullYear();
    const gm = now.getMonth() + 1;
    const gd = now.getDate();
    const isoDate = `${gy}-${String(gm).padStart(2, "0")}-${String(gd).padStart(2, "0")}`;
    onChange?.(isoDate);
    setOpen(false);
  };

  const handleClear = (e: React.MouseEvent) => {
    e.stopPropagation();
    onChange?.("");
  };

  // ── calendar grid ─────────────────────────────────────────────────────────
  const renderCalendar = () => {
    const isJalaliCal = calendarType === "jalali";
    const daysInMonth = getDaysInMonth(viewYear, viewMonth, isJalaliCal);
    const firstDay    = getFirstDayOfMonth(viewYear, viewMonth, isJalaliCal);

    const cells: (number | null)[] = Array<null>(firstDay).fill(null);
    for (let i = 1; i <= daysInMonth; i++) cells.push(i);

    const monthNames = isJalaliCal ? JALALI_MONTHS : GREGORIAN_MONTHS;
    const weekdays   = isJalaliCal ? JALALI_WEEKDAYS : GREGORIAN_WEEKDAYS;

    const isToday = (day: number) => {
      const t = today[calendarType];
      return day === t.day && viewMonth === t.month && viewYear === t.year;
    };

    const isSelected = (day: number) => {
      if (!selectedDate) return false;
      const s = selectedDate[calendarType];
      return day === s.day && viewMonth === s.month && viewYear === s.year;
    };

    return (
      <div className="p-3 space-y-3 w-[280px]">
        {/* Header row */}
        <div className="flex items-center justify-between">
          {/* Calendar type switcher */}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setCalendarType(calendarType === "jalali" ? "gregorian" : "jalali")}
            className="text-xs h-7 px-2 shrink-0"
          >
            {calendarType === "jalali" ? "میلادی" : "شمسی"}
          </Button>

          {/* Month/year navigation */}
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={handleNextMonth}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 18 9 12 15 6" />
              </svg>
              <span className="sr-only">ماه بعد</span>
            </Button>

            <span className="text-sm font-semibold min-w-[120px] text-center select-none">
              {isJalaliCal
                ? `${toPersianDigits(String(viewYear))} ${monthNames[viewMonth - 1] ?? ""}`
                : `${monthNames[viewMonth - 1] ?? ""} ${viewYear}`}
            </span>

            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" onClick={handlePrevMonth}>
              <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="9 18 15 12 9 6" />
              </svg>
              <span className="sr-only">ماه قبل</span>
            </Button>
          </div>
        </div>

        {/* Weekday labels */}
        <div className="grid grid-cols-7 text-center text-[11px] font-medium text-muted-foreground">
          {weekdays.map((d) => (
            <div key={d} className="h-7 flex items-center justify-center">{d}</div>
          ))}
        </div>

        {/* Day cells */}
        <div className="grid grid-cols-7 gap-0.5">
          {cells.map((day, idx) => {
            if (day === null) return <div key={`e-${idx}`} />;
            const sel   = isSelected(day);
            const today_ = isToday(day);
            return (
              <Button
                key={day}
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => handleDateSelect(day)}
                className={cn(
                  "h-8 w-full rounded-md text-sm font-normal p-0",
                  today_ && !sel && "border border-primary text-primary",
                  sel && "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground",
                )}
              >
                {isJalaliCal ? toPersianDigits(String(day)) : day}
              </Button>
            );
          })}
        </div>

        {/* Footer */}
        <div className="flex justify-end pt-2 border-t border-border">
          <Button type="button" variant="ghost" size="sm" onClick={handleToday} className="text-xs h-7 px-3">
            امروز
          </Button>
        </div>
      </div>
    );
  };

  // ── render ─────────────────────────────────────────────────────────────────
  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          disabled={disabled}
          className={cn(
            "w-full justify-start text-right font-normal h-10",
            !value && "text-muted-foreground",
            className,
          )}
        >
          <CalendarIcon className="ml-2 h-4 w-4 shrink-0" />
          <span className="flex-1 text-right truncate">{displayText}</span>
          {value && !disabled && (
            <X
              className="h-4 w-4 opacity-40 hover:opacity-100 transition-opacity shrink-0"
              onClick={handleClear}
            />
          )}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start" side="bottom">
        {renderCalendar()}
      </PopoverContent>
    </Popover>
  );
}
