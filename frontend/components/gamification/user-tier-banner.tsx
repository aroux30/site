"use client";

import React, { useState } from "react";
import {
  Coins,
  Crown,
  Shield,
  Award,
  Sparkles,
  Info,
  Check,
  TrendingUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { toPersianDigits } from "@/lib/utils";

export interface TierDef {
  key: "bronze" | "silver" | "gold" | "platinum";
  title: string;
  minPoints: number;
  maxPoints: number;
  color: string;
  badgeBg: string;
  borderColor: string;
  benefits: string[];
}

export const TIERS: TierDef[] = [
  {
    key: "bronze",
    title: "برنزی",
    minPoints: 0,
    maxPoints: 99,
    color: "#b45309",
    badgeBg: "bg-amber-700/15 text-amber-800 dark:text-amber-400",
    borderColor: "border-amber-700/30",
    benefits: [
      "دسترسی به گردونه شانس روزانه",
      "امکان تبدیل امتیاز به کوپن تخفیف",
      "پاداش ورود روزانه (Streak)",
    ],
  },
  {
    key: "silver",
    title: "نقره‌ای",
    minPoints: 100,
    maxPoints: 299,
    color: "#64748b",
    badgeBg: "bg-slate-500/15 text-slate-800 dark:text-slate-300",
    borderColor: "border-slate-400/40",
    benefits: [
      "تمامی مزایای سطح برنزی",
      "۵٪ تخفیف مازاد در حراج‌های ویژه",
      "اولویت در ارسال و بسته‌بندی سفارشات",
      "یک چرخش هدیه اضافی در ماه",
    ],
  },
  {
    key: "gold",
    title: "طلایی",
    minPoints: 300,
    maxPoints: 699,
    color: "#d97706",
    badgeBg: "bg-amber-500/20 text-amber-900 dark:text-amber-300",
    borderColor: "border-amber-500/50",
    benefits: [
      "تمامی مزایای سطح نقره‌ای",
      "ارسال رایگان دائمی برای تمام سفارشات",
      "۱۰٪ تخفیف مازاد در روز تولد",
      "دسترسی پیش از موعد به جشنواره‌های تخفیف",
    ],
  },
  {
    key: "platinum",
    title: "پلاتینیوم",
    minPoints: 700,
    maxPoints: Infinity,
    color: "#6366f1",
    badgeBg: "bg-indigo-500/20 text-indigo-900 dark:text-indigo-300",
    borderColor: "border-indigo-500/50",
    benefits: [
      "تمامی مزایای سطح طلایی",
      "پشتیبانی تلفنی و اختصاصی VIP (پاسخگویی فوری)",
      "هدایای نفیس مناسبتی همراه بسته‌ها",
      "امکان رزرو محصولات محدود پیش از عرضه عمومی",
    ],
  },
];

export function getTierForPoints(points: number): TierDef {
  if (points >= 700) return TIERS[3]!;
  if (points >= 300) return TIERS[2]!;
  if (points >= 100) return TIERS[1]!;
  return TIERS[0]!;
}

interface UserTierBannerProps {
  userPoints: number;
  userName?: string | null;
  onScrollToWheel?: () => void;
}

export function UserTierBanner({
  userPoints,
  userName = "کاربر گرامی",
  onScrollToWheel,
}: UserTierBannerProps) {
  const [tierInfoOpen, setTierInfoOpen] = useState(false);

  const currentTier = getTierForPoints(userPoints);
  const currentTierIndex = TIERS.findIndex((t) => t.key === currentTier.key);
  const nextTier = TIERS[currentTierIndex + 1] || null;

  // Calculate progress percentage to next tier
  let progressPercent = 100;
  let pointsNeeded = 0;

  if (nextTier) {
    const range = nextTier.minPoints - currentTier.minPoints;
    const progress = userPoints - currentTier.minPoints;
    progressPercent = Math.min(100, Math.max(5, Math.round((progress / range) * 100)));
    pointsNeeded = nextTier.minPoints - userPoints;
  }

  return (
    <>
      <div className="relative overflow-hidden rounded-3xl border border-primary/20 bg-gradient-to-r from-primary/10 via-primary/5 to-card p-6 sm:p-8 shadow-xl">
        {/* Subtle Background Glow */}
        <div className="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-primary/15 blur-3xl" />
        <div className="pointer-events-none absolute -left-16 -bottom-16 h-64 w-64 rounded-full bg-amber-500/10 blur-3xl" />

        <div className="relative z-10 flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          {/* User & Points Info */}
          <div className="flex flex-col sm:flex-row items-start sm:items-center gap-5">
            {/* Big Points Badge */}
            <div className="relative flex h-20 w-20 shrink-0 items-center justify-center rounded-3xl bg-gradient-to-tr from-primary to-primary/80 text-primary-foreground shadow-xl ring-4 ring-primary/20">
              <Coins className="h-10 w-10 animate-pulse" />
            </div>

            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-muted-foreground">
                  سلام، {userName || "کاربر گرامی"}
                </span>
                <button
                  type="button"
                  onClick={() => setTierInfoOpen(true)}
                  className="flex items-center gap-1 text-xs text-primary hover:underline"
                >
                  <Info className="h-3.5 w-3.5" />
                  <span>راهنمای سطوح</span>
                </button>
              </div>

              <div className="flex items-baseline gap-2">
                <span className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
                  {toPersianDigits(userPoints)}
                </span>
                <span className="text-base sm:text-lg font-bold text-muted-foreground">
                  امتیاز باشگاه
                </span>
              </div>

              {/* Current Tier Badge */}
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Badge
                  className={`flex items-center gap-1.5 px-3 py-1 text-xs font-bold ${currentTier.badgeBg} border ${currentTier.borderColor}`}
                >
                  {currentTier.key === "platinum" ? (
                    <Crown className="h-3.5 w-3.5 text-indigo-500" />
                  ) : currentTier.key === "gold" ? (
                    <Award className="h-3.5 w-3.5 text-amber-500" />
                  ) : currentTier.key === "silver" ? (
                    <Shield className="h-3.5 w-3.5 text-slate-400" />
                  ) : (
                    <Shield className="h-3.5 w-3.5 text-amber-700" />
                  )}
                  <span>سطح وفاداری شما: {currentTier.title}</span>
                </Badge>

                {nextTier && (
                  <span className="text-xs text-muted-foreground">
                    ({toPersianDigits(pointsNeeded)} امتیاز تا سطح {nextTier.title})
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* Tier Progress & Quick Action */}
          <div className="flex flex-col gap-3 min-w-[280px] lg:max-w-xs">
            {nextTier ? (
              <div className="space-y-1.5">
                <div className="flex justify-between text-xs font-medium text-muted-foreground">
                  <span>سطح {currentTier.title}</span>
                  <span className="text-foreground font-bold">
                    {toPersianDigits(progressPercent)}٪
                  </span>
                  <span>سطح {nextTier.title}</span>
                </div>

                {/* Progress bar */}
                <div className="h-3 w-full overflow-hidden rounded-full bg-muted border border-border/80">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-primary to-amber-500 transition-all duration-700 ease-out"
                    style={{ width: `${progressPercent}%` }}
                  />
                </div>
              </div>
            ) : (
              <div className="rounded-2xl bg-indigo-500/10 border border-indigo-500/20 p-3 text-center text-xs font-semibold text-indigo-700 dark:text-indigo-300">
                تبریک! شما در بالاترین سطح باشگاه مشتریان (پلاتینیوم) قرار دارید.
              </div>
            )}

            {/* Quick Actions */}
            <div className="flex items-center gap-2">
              <Button
                onClick={onScrollToWheel}
                className="flex-1 rounded-xl bg-gradient-to-r from-primary to-primary/90 font-bold shadow-md shadow-primary/20 gap-1.5 h-10 text-xs sm:text-sm"
              >
                <Sparkles className="h-4 w-4" />
                <span>گردونه شانس امروز</span>
              </Button>
            </div>
          </div>
        </div>
      </div>

      {/* Tier Explanation Modal */}
      <Dialog open={tierInfoOpen} onOpenChange={setTierInfoOpen}>
        <DialogContent className="sm:max-w-2xl text-right">
          <DialogHeader>
            <DialogTitle className="text-xl font-bold flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <span>سطوح وفاداری باشگاه مشتریان</span>
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              با هر خرید، چرخش در گردونه شانس و ورود روزانه امتیاز کسب کنید و از مزایای اختصاصی هر سطح بهره‌مند شوید.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 gap-3.5 max-h-[60vh] overflow-y-auto p-1">
            {TIERS.map((tier) => {
              const isUserCurrent = tier.key === currentTier.key;

              return (
                <div
                  key={tier.key}
                  className={`rounded-2xl border p-4 transition-all ${
                    isUserCurrent
                      ? "border-primary bg-primary/5 ring-2 ring-primary/20 shadow-md"
                      : "border-border bg-card"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2.5">
                    <div className="flex items-center gap-2">
                      <Badge className={`${tier.badgeBg} border ${tier.borderColor} font-bold`}>
                        {tier.title}
                      </Badge>
                      {isUserCurrent && (
                        <span className="text-[11px] font-bold text-primary">
                          (سطح فعلی شما)
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground font-medium">
                      {tier.maxPoints === Infinity
                        ? `${toPersianDigits(tier.minPoints)}+ امتیاز`
                        : `${toPersianDigits(tier.minPoints)} تا ${toPersianDigits(tier.maxPoints)} امتیاز`}
                    </span>
                  </div>

                  <ul className="space-y-2 text-xs text-muted-foreground mt-3">
                    {tier.benefits.map((benefit, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <Check className="h-3.5 w-3.5 text-primary shrink-0 mt-0.5" />
                        <span>{benefit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              );
            })}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
