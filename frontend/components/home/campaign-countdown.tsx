"use client";

import { useEffect, useState } from "react";
import { toPersianDigits } from "@/lib/utils";

interface CampaignCountdownProps {
  targetDateIso?: string;
}

export function CampaignCountdown({
  targetDateIso,
}: CampaignCountdownProps) {
  // Default target: End of current week / 7 days from fixed reference
  const [timeLeft, setTimeLeft] = useState<{
    hours: number;
    minutes: number;
    seconds: number;
    isEnded: boolean;
  }>({
    hours: 18,
    minutes: 45,
    seconds: 30,
    isEnded: false,
  });

  useEffect(() => {
    // If targetDate provided, calculate exact remaining time
    const target = targetDateIso
      ? new Date(targetDateIso).getTime()
      : Date.now() + 18 * 3600 * 1000 + 45 * 60 * 1000;

    const interval = setInterval(() => {
      const now = Date.now();
      const diff = target - now;

      if (diff <= 0) {
        setTimeLeft({ hours: 0, minutes: 0, seconds: 0, isEnded: true });
        clearInterval(interval);
        return;
      }

      const hours = Math.floor(diff / (1000 * 60 * 60));
      const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
      const seconds = Math.floor((diff % (1000 * 60)) / 1000);

      setTimeLeft({ hours, minutes, seconds, isEnded: false });
    }, 1000);

    return () => clearInterval(interval);
  }, [targetDateIso]);

  return (
    <div className="flex items-center gap-3">
      {timeLeft.isEnded ? (
        <span className="text-sm font-bold text-rose-500">مهلت جشنواره به پایان رسید</span>
      ) : (
        <div className="flex items-center gap-2 font-mono text-lg font-bold">
          <div className="bg-background/80 dark:bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-foreground shadow-sm">
            <span>{toPersianDigits(String(timeLeft.hours).padStart(2, "0"))}</span>
            <span className="text-xs font-normal text-muted-foreground mr-1">ساعت</span>
          </div>
          <span className="text-emerald-500 font-bold">:</span>
          <div className="bg-background/80 dark:bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-foreground shadow-sm">
            <span>{toPersianDigits(String(timeLeft.minutes).padStart(2, "0"))}</span>
            <span className="text-xs font-normal text-muted-foreground mr-1">دقیقه</span>
          </div>
          <span className="text-emerald-500 font-bold">:</span>
          <div className="bg-background/80 dark:bg-slate-900/90 backdrop-blur-md px-3 py-1.5 rounded-xl border border-border/80 text-emerald-600 dark:text-emerald-400 shadow-sm">
            <span>{toPersianDigits(String(timeLeft.seconds).padStart(2, "0"))}</span>
            <span className="text-xs font-normal text-muted-foreground mr-1">ثانیه</span>
          </div>
        </div>
      )}
    </div>
  );
}
