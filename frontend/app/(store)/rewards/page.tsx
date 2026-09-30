"use client";

import React, { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import {
  Sparkles,
  ShieldCheck,
  ChevronLeft,
  Gift,
  Loader2,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { UserTierBanner } from "@/components/gamification/user-tier-banner";
import { RewardsCatalog } from "@/components/gamification/rewards-catalog";
import { ClaimHistory } from "@/components/gamification/claim-history";
import {
  fetchGamificationSummary,
  fetchGamificationHistory,
  type ApiClaimRecord,
} from "@/lib/api/gamification";
import { Badge } from "@/components/ui/badge";

interface ActivityItem {
  id: string;
  title: string;
  date: string;
  pointsChange: number;
  type: "spin" | "claim" | "streak" | "bonus";
  code?: string;
  status?: string;
}

export default function RewardsPage() {
  const { user } = useAuthStore();
  const [points, setPoints] = useState<number>(0);
  const [pointsLoading, setPointsLoading] = useState(true);
  const [activityList, setActivityList] = useState<ActivityItem[]>([]);
  const [mounted, setMounted] = useState(false);

  const loadServerState = useCallback(async () => {
    setPointsLoading(true);
    try {
      // The server is the single source of truth for points; the client
      // never invents or persists a balance of its own.
      const summary = await fetchGamificationSummary();
      setPoints(summary.points_available ?? summary.total_points_earned ?? 0);
    } finally {
      setPointsLoading(false);
    }

    try {
      const history = await fetchGamificationHistory(0, 20);
      setActivityList(
        (history.items || []).map((event) => ({
          id: event.id,
          title: event.rule_name || "دریافت امتیاز باشگاه مشتریان",
          date: event.created_at,
          pointsChange: event.points_earned,
          type: "bonus" as const,
        })),
      );
    } catch {
      setActivityList([]);
    }
  }, []);

  useEffect(() => {
    setMounted(true);
    void loadServerState();
  }, [loadServerState, user?.id]);

  // After a successful server-side claim, refresh from the server instead of
  // doing local arithmetic — the catalog reports the outcome, the summary is
  // authoritative.
  const handlePointsUpdate = () => {
    void loadServerState();
  };

  const handleClaimSuccess = (_claimRecord: ApiClaimRecord) => {
    void loadServerState();
  };

  const displayName =
    user?.fullName ||
    (user?.first_name ? `${user.first_name} ${user.last_name || ""}`.trim() : null) ||
    "کاربر گرامی";

  return (
    <div className="min-h-screen bg-gradient-to-b from-background via-muted/20 to-background pb-20">
      {/* Top Banner & Breadcrumb */}
      <div className="border-b border-border bg-card/60 backdrop-blur">
        <div className="container mx-auto px-4 py-3 sm:py-4">
          <nav className="flex items-center gap-2 text-xs text-muted-foreground">
            <Link href="/" className="hover:text-primary transition-colors">
              صفحه اصلی
            </Link>
            <ChevronLeft className="h-3.5 w-3.5" />
            <span className="font-semibold text-foreground">
              باشگاه جوایز و گردونه شانس
            </span>
          </nav>
        </div>
      </div>

      <div className="container mx-auto px-4 pt-6 sm:pt-8 space-y-8 sm:space-y-10">
        {/* Hero Title */}
        <div className="text-center max-w-2xl mx-auto space-y-2.5">
          <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-bold shadow-xs">
            <Sparkles className="h-3.5 w-3.5" />
            <span>باشگاه مشتریان فروشگاه</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            امتیاز جمع کنید و جایزه بگیرید!
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
            با ثبت سفارش موفق، ثبت دیدگاه و عضویت در فروشگاه امتیاز دریافت کنید و آنها را به
            کدهای تخفیف، ارسال رایگان و هدایای نقدی تبدیل نمایید.
          </p>
        </div>

        {/* Section 1: User Points & Loyalty Tier Banner */}
        <UserTierBanner
          userPoints={mounted ? points : 0}
          userName={displayName}
        />

        {/* Section 2: How points & the lucky wheel work */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400">
                  <Gift className="h-4 w-4" />
                </div>
                <h2 className="text-xl font-black text-foreground">گردونه شانس پس از خرید</h2>
              </div>
              <Badge variant="outline" className="text-[11px] font-semibold">
                ویژه سفارش‌های موفق
              </Badge>
            </div>

            <div className="rounded-3xl border border-amber-500/30 bg-gradient-to-tr from-amber-500/10 via-card to-card p-8 text-center space-y-3">
              <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-full bg-amber-500/15 text-3xl">
                🎁
              </div>
              <h3 className="text-base font-black text-foreground">
                بعد از هر خرید موفق، یک شانس رایگان بگیرید
              </h3>
              <p className="text-xs text-muted-foreground leading-relaxed max-w-md mx-auto">
                بلافاصله پس از تأیید پرداخت، صفحه تأیید سفارش دکمه‌ی «گردونه شانس» را به شما
                نشان می‌دهد. نتیجه‌ی چرخش روی سرور محاسبه می‌شود و جایزه مستقیماً به کیف پول
                شما واریز می‌گردد.
              </p>
            </div>
          </div>

          {/* Right Column: Quick Rules & Tips Card */}
          <div className="lg:col-span-5 space-y-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400">
                <ShieldCheck className="h-4 w-4" />
              </div>
              <h2 className="text-xl font-black text-foreground">راهنمای کسب امتیاز</h2>
            </div>

            <div className="rounded-3xl border border-border/80 bg-card/60 p-6 backdrop-blur shadow-md space-y-3.5">
              <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <span>قوانین باشگاه مشتریان</span>
              </h4>
              <ul className="space-y-2 text-xs text-muted-foreground leading-relaxed">
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>ثبت هر سفارش موفق امتیاز باشگاه مشتریان به شما می‌دهد.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>ثبت دیدگاه برای محصولات خریداری‌شده امتیاز جداگانه دارد.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>امتیازها به‌صورت خودکار و بر اساس قوانین فروشگاه روی سرور ثبت می‌شوند.</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>جوایز قابل انتخاب در کاتالوگ پایین، مستقیماً با امتیاز شما فعال می‌شوند.</span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Section 3: Available Rewards Catalog */}
        <section className="pt-4">
          {pointsLoading ? (
            <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              در حال بارگذاری امتیازهای شما...
            </div>
          ) : (
            <RewardsCatalog
              userPoints={mounted ? points : 0}
              onPointsUpdate={handlePointsUpdate}
              onClaimSuccess={handleClaimSuccess}
            />
          )}
        </section>

        {/* Section 4: Points Activity History (server-backed) */}
        <section className="pt-4">
          <ClaimHistory claimRecords={[]} activityList={activityList} />
        </section>
      </div>
    </div>
  );
}
