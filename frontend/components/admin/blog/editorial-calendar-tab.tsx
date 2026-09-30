"use client";

import React, { useState } from "react";
import {
  Calendar as CalendarIcon,
  ChevronLeft,
  ChevronRight,
  Clock,
  CheckCircle2,
  FileText,
  CalendarClock,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { toPersianDigits } from "@/lib/utils";
import type { BlogPost } from "@/lib/api/blog";

interface EditorialCalendarTabProps {
  posts: BlogPost[];
  onSelectPost: (post: BlogPost) => void;
}

const PERSIAN_MONTHS = [
  "فروردین",
  "اردیبهشت",
  "خرداد",
  "تیر",
  "مرداد",
  "شهریور",
  "مهر",
  "آبان",
  "آذر",
  "دی",
  "بهمن",
  "اسفند",
];

const WEEKDAYS = ["ش", "ی", "د", "س", "چ", "پ", "ج"];

export function EditorialCalendarTab({ posts, onSelectPost }: EditorialCalendarTabProps) {
  // Current view date
  const [currentDate, setCurrentDate] = useState(() => new Date());

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // Navigation
  const prevMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };
  const nextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };
  const today = () => {
    setCurrentDate(new Date());
  };

  // Group posts by day (YYYY-MM-DD)
  const postsByDay = React.useMemo(() => {
    const map: Record<string, BlogPost[]> = {};
    for (const post of posts) {
      const dateStr = post.scheduled_for || post.published_at || post.created_at;
      if (!dateStr) continue;
      const d = new Date(dateStr);
      const key = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(
        d.getDate(),
      ).padStart(2, "0")}`;
      if (!map[key]) map[key] = [];
      map[key].push(post);
    }
    return map;
  }, [posts]);

  // Compute calendar days
  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);
  const daysInMonth = lastDayOfMonth.getDate();
  // Saturday is index 0 in Persian calendar: JS getDay() is 0 for Sunday
  // Sunday (0) -> 1, Monday (1) -> 2, ..., Friday (5) -> 6, Saturday (6) -> 0
  const startingDayIndex = (firstDayOfMonth.getDay() + 1) % 7;

  const monthName = currentDate.toLocaleDateString("fa-IR", {
    month: "long",
    year: "numeric",
  });

  return (
    <div className="space-y-4">
      {/* Calendar Header */}
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <CalendarIcon className="h-5 w-5 text-emerald-600" />
            <h3 className="font-bold text-base text-foreground">تقویم تحریریه — {monthName}</h3>
          </div>
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-3 pe-4 text-xs">
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> منتشر شده
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-sky-500" /> زمان‌بندی‌شده
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> پیش‌نویس
              </span>
            </div>
            <Button variant="outline" size="sm" onClick={prevMonth}>
              <ChevronRight className="h-4 w-4" />
            </Button>
            <Button variant="outline" size="sm" onClick={today} className="text-xs">
              امروز
            </Button>
            <Button variant="outline" size="sm" onClick={nextMonth}>
              <ChevronLeft className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </Card>

      {/* Calendar Grid */}
      <Card className="overflow-hidden border-border">
        <div className="grid grid-cols-7 border-b border-border bg-muted/50 text-center text-xs font-bold text-muted-foreground">
          {WEEKDAYS.map((day, idx) => (
            <div key={idx} className="py-2.5">
              {day}
            </div>
          ))}
        </div>

        <div className="grid grid-cols-7 auto-rows-fr bg-border gap-px">
          {/* Empty cells before month start */}
          {Array.from({ length: startingDayIndex }).map((_, idx) => (
            <div key={`empty-${idx}`} className="min-h-[110px] bg-background/50 p-2 opacity-30" />
          ))}

          {/* Month days */}
          {Array.from({ length: daysInMonth }).map((_, idx) => {
            const dayNum = idx + 1;
            const dateKey = `${year}-${String(month + 1).padStart(2, "0")}-${String(
              dayNum,
            ).padStart(2, "0")}`;
            const dayPosts = postsByDay[dateKey] || [];
            const isToday =
              new Date().getFullYear() === year &&
              new Date().getMonth() === month &&
              new Date().getDate() === dayNum;

            return (
              <div
                key={`day-${dayNum}`}
                className={`min-h-[110px] bg-background p-2 transition-colors hover:bg-muted/30 ${
                  isToday ? "bg-emerald-500/5 ring-1 ring-emerald-500/30" : ""
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold ${
                      isToday
                        ? "bg-emerald-600 text-white"
                        : "text-foreground/80"
                    }`}
                  >
                    {toPersianDigits(String(dayNum))}
                  </span>
                  {dayPosts.length > 0 && (
                    <span className="text-[10px] text-muted-foreground">
                      {toPersianDigits(String(dayPosts.length))} نوشته
                    </span>
                  )}
                </div>

                <div className="space-y-1">
                  {dayPosts.slice(0, 3).map((post) => {
                    const isSched =
                      post.scheduled_for &&
                      new Date(post.scheduled_for).getTime() > Date.now() &&
                      post.status === "draft";
                    const isPub = post.status === "published";

                    return (
                      <div
                        key={post.id}
                        onClick={() => onSelectPost(post)}
                        className={`group flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[11px] font-medium transition-all hover:scale-[1.02] ${
                          isSched
                            ? "bg-sky-500/10 text-sky-700 dark:text-sky-300 border border-sky-500/20"
                            : isPub
                            ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300 border border-emerald-500/20"
                            : "bg-amber-500/10 text-amber-700 dark:text-amber-300 border border-amber-500/20"
                        }`}
                        title={post.title}
                      >
                        {isSched ? (
                          <CalendarClock className="h-3 w-3 shrink-0" />
                        ) : isPub ? (
                          <CheckCircle2 className="h-3 w-3 shrink-0" />
                        ) : (
                          <FileText className="h-3 w-3 shrink-0" />
                        )}
                        <span className="truncate">{post.title}</span>
                      </div>
                    );
                  })}
                  {dayPosts.length > 3 && (
                    <div className="text-[10px] text-muted-foreground text-center">
                      +{toPersianDigits(String(dayPosts.length - 3))} مورد دیگر
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Card>
    </div>
  );
}
