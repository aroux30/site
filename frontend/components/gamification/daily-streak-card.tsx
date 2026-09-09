"use client";

import React, { useState, useEffect } from "react";
import {
  CheckCircle2,
  Flame,
  Sparkles,
  Gift,
  Clock,
  Award,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { toPersianDigits } from "@/lib/utils";
import { triggerConfetti } from "@/components/ui/confetti";
import { earnLoyaltyPoints } from "@/lib/api/gamification";
import { useAuthStore } from "@/stores/auth-store";

interface DayReward {
  day: number;
  points: number;
  label: string;
  isSpecial?: boolean;
}

const STREAK_DAYS: DayReward[] = [
  { day: 1, points: 10, label: "روز اول" },
  { day: 2, points: 15, label: "روز دوم" },
  { day: 3, points: 20, label: "روز سوم" },
  { day: 4, points: 25, label: "روز چهارم" },
  { day: 5, points: 30, label: "روز پنجم" },
  { day: 6, points: 40, label: "روز ششم" },
  { day: 7, points: 60, label: "روز هفتم", isSpecial: true },
];

interface DailyStreakCardProps {
  userPoints: number;
  onPointsUpdate: (_newPoints: number, _change: number, _reason: string) => void;
}

export function DailyStreakCard({
  userPoints,
  onPointsUpdate,
}: DailyStreakCardProps) {
  const { user, updateProfile } = useAuthStore();
  const [streakCount, setStreakCount] = useState(1);
  const [claimedToday, setClaimedToday] = useState(false);
  const [timeLeft, setTimeLeft] = useState<string>("");

  // Load streak from localStorage
  useEffect(() => {
    if (typeof window === "undefined") return;

    const todayStr = new Date().toISOString().split("T")[0];
    const saved = localStorage.getItem("daily_streak_tracker");

    if (saved) {
      try {
        const data = JSON.parse(saved);
        const lastDate = data.lastClaimDate;

        if (lastDate === todayStr) {
          setClaimedToday(true);
          setStreakCount(data.streak || 1);
        } else {
          // Check if yesterday
          const yesterday = new Date();
          yesterday.setDate(yesterday.getDate() - 1);
          const yesterdayStr = yesterday.toISOString().split("T")[0];

          if (lastDate === yesterdayStr) {
            // Consecutive streak continues
            setClaimedToday(false);
            const nextStreak = data.streak >= 7 ? 1 : data.streak + 1;
            setStreakCount(nextStreak);
          } else {
            // Streak broken, reset to day 1
            setClaimedToday(false);
            setStreakCount(1);
          }
        }
      } catch {
        setStreakCount(1);
        setClaimedToday(false);
      }
    } else {
      setStreakCount(1);
      setClaimedToday(false);
    }
  }, []);

  // Countdown timer to midnight
  useEffect(() => {
    const updateCountdown = () => {
      const now = new Date();
      const tomorrow = new Date(now);
      tomorrow.setHours(24, 0, 0, 0);
      const diff = tomorrow.getTime() - now.getTime();

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      setTimeLeft(
        `${toPersianDigits(hours.toString().padStart(2, "0"))}:${toPersianDigits(
          minutes.toString().padStart(2, "0"),
        )}:${toPersianDigits(seconds.toString().padStart(2, "0"))}`,
      );
    };

    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, []);

  const currentDayReward: DayReward = STREAK_DAYS[(streakCount - 1) % 7] ?? STREAK_DAYS[0] ?? { day: 1, points: 10, label: "روز اول" };

  const handleClaimDaily = () => {
    if (claimedToday) return;

    const pointsToAward = currentDayReward.points;
    const todayStr = new Date().toISOString().split("T")[0];

    // Save to localStorage
    const streakData = {
      streak: streakCount,
      lastClaimDate: todayStr,
    };
    localStorage.setItem("daily_streak_tracker", JSON.stringify(streakData));
    setClaimedToday(true);

    // Update parent state
    const newTotal = userPoints + pointsToAward;
    onPointsUpdate(
      newTotal,
      pointsToAward,
      `جایزه ورود روزانه (${currentDayReward.label})`,
    );

    // Update auth store user if available
    if (user) {
      updateProfile({
        loyalty_points: (user.loyalty_points || 0) + pointsToAward,
        loyaltyPoints: (user.loyaltyPoints || 0) + pointsToAward,
      });
    }

    // Call backend loyalty earn API
    earnLoyaltyPoints(
      pointsToAward,
      `جایزه ورود روزانه (${currentDayReward.label})`,
      "daily_login_streak",
    );

    // Confetti celebration
    triggerConfetti({
      particleCount: 80,
      spread: 70,
    });
  };

  return (
    <Card className="overflow-hidden border-border/80 bg-card/60 backdrop-blur shadow-lg">
      <div className="p-5 sm:p-7">
        {/* Header */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/60 pb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-tr from-amber-500 to-orange-400 text-white shadow-md">
              <Flame className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-lg font-bold text-foreground">
                  پاداش ورود روزانه (Streak)
                </h3>
                <Badge className="bg-amber-500/15 text-amber-700 dark:text-amber-400 hover:bg-amber-500/20 border-amber-500/30 text-xs">
                  {toPersianDigits(streakCount)} روز متوالی
                </Badge>
              </div>
              <p className="text-xs text-muted-foreground mt-0.5">
                هر روز به فروشگاه سر بزنید و تا ۶۰ امتیاز هدیه در روز هفتم دریافت کنید!
              </p>
            </div>
          </div>

          {claimedToday && (
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground font-mono bg-muted/60 px-3 py-1.5 rounded-xl border border-border">
              <Clock className="h-3.5 w-3.5 text-primary" />
              <span>شانس بعدی در: {timeLeft}</span>
            </div>
          )}
        </div>

        {/* 7-Day Visual Tracker */}
        <div className="mt-6 grid grid-cols-4 sm:grid-cols-7 gap-2.5 sm:gap-3">
          {STREAK_DAYS.map((dayItem) => {
            const isCompleted = claimedToday
              ? dayItem.day <= streakCount
              : dayItem.day < streakCount;
            const isToday = dayItem.day === streakCount && !claimedToday;

            return (
              <div
                key={dayItem.day}
                className={`relative flex flex-col items-center justify-between rounded-2xl p-3 sm:p-3.5 border text-center transition-all ${
                  isCompleted
                    ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-900 dark:text-emerald-300"
                    : isToday
                    ? "bg-gradient-to-b from-primary/15 to-primary/5 border-primary shadow-md ring-2 ring-primary/20 scale-[1.03]"
                    : "bg-muted/30 border-border/50 text-muted-foreground opacity-75"
                }`}
              >
                {/* Special Tag for Day 7 */}
                {dayItem.isSpecial && (
                  <span className="absolute -top-2.5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full bg-gradient-to-r from-amber-500 to-yellow-400 px-2 py-0.5 text-[9px] font-black text-amber-950 shadow-sm">
                    ویژه!
                  </span>
                )}

                <span className="text-[11px] font-medium">{dayItem.label}</span>

                <div className="my-2.5 flex h-10 w-10 items-center justify-center rounded-xl bg-background shadow-xs">
                  {isCompleted ? (
                    <CheckCircle2 className="h-6 w-6 text-emerald-600 dark:text-emerald-400" />
                  ) : dayItem.isSpecial ? (
                    <Award className={`h-6 w-6 ${isToday ? "text-amber-500 animate-bounce" : "text-muted-foreground"}`} />
                  ) : (
                    <Sparkles className={`h-5 w-5 ${isToday ? "text-primary animate-pulse" : "text-muted-foreground"}`} />
                  )}
                </div>

                <div className="flex flex-col items-center">
                  <span
                    className={`text-xs font-bold ${
                      isCompleted
                        ? "text-emerald-700 dark:text-emerald-400"
                        : isToday
                        ? "text-primary"
                        : "text-muted-foreground"
                    }`}
                  >
                    +{toPersianDigits(dayItem.points)}
                  </span>
                  <span className="text-[9px] text-muted-foreground">امتیاز</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Claim Action Row */}
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 rounded-2xl bg-muted/40 p-4 border border-border">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
              <Gift className="h-5 w-5" />
            </div>
            <div>
              <div className="text-sm font-bold text-foreground">
                {claimedToday
                  ? `جایزه ${currentDayReward.label} دریافت شده است`
                  : `جایزه امروز: +${toPersianDigits(currentDayReward.points)} امتیاز`}
              </div>
              <p className="text-xs text-muted-foreground">
                {claimedToday
                  ? "فردا برای ادامه زنجیره و دریافت امتیاز بیشتر بازگردید"
                  : "روی دکمه کلیک کنید تا امتیاز به موجودی شما افزوده شود"}
              </p>
            </div>
          </div>

          <Button
            onClick={handleClaimDaily}
            disabled={claimedToday}
            className={`w-full sm:w-auto min-w-[170px] h-11 rounded-xl font-bold transition-all ${
              claimedToday
                ? "bg-muted text-muted-foreground cursor-not-allowed"
                : "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md shadow-primary/20"
            }`}
          >
            {claimedToday ? (
              <div className="flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                <span>امروز دریافت شد</span>
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <Sparkles className="h-4 w-4" />
                <span>دریافت {toPersianDigits(currentDayReward.points)} امتیاز</span>
              </div>
            )}
          </Button>
        </div>
      </div>
    </Card>
  );
}
