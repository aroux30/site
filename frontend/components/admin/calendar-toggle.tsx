"use client";

import { Calendar, Globe } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useCalendar } from "@/lib/calendar-context";

/**
 * Toggle between Jalali (شمسی) and Gregorian (میلادی) calendar display.
 *
 * Placed in the admin header alongside ThemeToggle. When the user switches,
 * every date on the page (table columns, date pickers, timestamps) updates
 * immediately through CalendarProvider.
 */
export function CalendarToggle() {
  const { calendarType, setCalendarType } = useCalendar();

  const isJalali = calendarType === "jalali";

  return (
    <Button
      variant="ghost"
      size="sm"
      className="gap-1.5 rounded-full px-3 h-9 text-xs font-medium"
      onClick={() => setCalendarType(isJalali ? "gregorian" : "jalali")}
      title={isJalali ? "تغییر به میلادی" : "تغییر به شمسی"}
    >
      {isJalali ? (
        <>
          <Calendar className="h-4 w-4" />
          <span className="hidden sm:inline">شمسی</span>
        </>
      ) : (
        <>
          <Globe className="h-4 w-4" />
          <span className="hidden sm:inline">میلادی</span>
        </>
      )}
    </Button>
  );
}
