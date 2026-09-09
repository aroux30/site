"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import {
  Sparkles,
  Trophy,
  ShieldCheck,
  ChevronLeft,
  Flame,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";
import { UserTierBanner } from "@/components/gamification/user-tier-banner";
import { WheelOfFortune, type WheelSlice } from "@/components/gamification/wheel-of-fortune";
import { DailyStreakCard } from "@/components/gamification/daily-streak-card";
import { RewardsCatalog } from "@/components/gamification/rewards-catalog";
import { ClaimHistory } from "@/components/gamification/claim-history";
import {
  fetchGamificationSummary,
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
  const [points, setPoints] = useState<number>(120);
  const [claimedRecords, setClaimedRecords] = useState<ApiClaimRecord[]>([]);
  const [activityList, setActivityList] = useState<ActivityItem[]>([]);
  const [mounted, setMounted] = useState(false);

  const wheelSectionRef = useRef<HTMLDivElement>(null);

  // Initialize and load persisted user state
  useEffect(() => {
    setMounted(true);

    // Initial points from auth user or localStorage
    const savedPoints = localStorage.getItem("gamification_user_points");
    if (savedPoints !== null) {
      setPoints(parseInt(savedPoints, 10) || 0);
    } else if (user?.loyalty_points !== undefined) {
      setPoints(user.loyalty_points);
    } else if (user?.loyaltyPoints !== undefined) {
      setPoints(user.loyaltyPoints);
    } else {
      // Fetch from API or clean default
      fetchGamificationSummary().then((summary) => {
        const p = summary.points_available ?? summary.total_points_earned ?? 120;
        setPoints(p);
      });
    }

    // Load saved claim records
    const savedClaims = localStorage.getItem("gamification_user_claims");
    if (savedClaims) {
      try {
        setClaimedRecords(JSON.parse(savedClaims));
      } catch {
        // Ignored
      }
    } else {
      // Default initial welcome coupon
      const defaultClaim: ApiClaimRecord = {
        id: "claim-welcome-10",
        reward_id: "rew-discount-10",
        reward_name: "کد تخفیف ۱۰٪ (هدیه عضویت باشگاه)",
        reward_type: "discount",
        points_spent: 0,
        claimed_at: new Date(Date.now() - 86400000 * 2).toISOString(),
        code: "WELCOME-CLUB",
        status: "active",
      };
      setClaimedRecords([defaultClaim]);
    }

    // Load activity
    const savedActivity = localStorage.getItem("gamification_user_activity");
    if (savedActivity) {
      try {
        setActivityList(JSON.parse(savedActivity));
      } catch {
        // Ignored
      }
    } else {
      setActivityList([
        {
          id: "act-1",
          title: "پاداش عضویت در باشگاه مشتریان",
          date: new Date(Date.now() - 86400000 * 3).toISOString(),
          pointsChange: 50,
          type: "bonus",
        },
        {
          id: "act-2",
          title: "پاداش اولین خرید از فروشگاه",
          date: new Date(Date.now() - 86400000 * 2).toISOString(),
          pointsChange: 70,
          type: "bonus",
        },
      ]);
    }
  }, [user]);

  // Points update handler
  const handlePointsUpdate = (newPoints: number, change: number, reason: string) => {
    setPoints(newPoints);
    if (typeof window !== "undefined") {
      localStorage.setItem("gamification_user_points", String(newPoints));

      // Append to activity list
      const newActivity: ActivityItem = {
        id: `act-${Date.now()}`,
        title: reason,
        date: new Date().toISOString(),
        pointsChange: change,
        type: change > 0 ? "spin" : "claim",
      };
      setActivityList((prev) => {
        const updated = [newActivity, ...prev];
        localStorage.setItem("gamification_user_activity", JSON.stringify(updated.slice(0, 50)));
        return updated;
      });
    }
  };

  // Wheel win handler
  const handleWheelRewardWon = (slice: WheelSlice) => {
    if (slice.couponCode) {
      const newClaim: ApiClaimRecord = {
        id: `claim-wheel-${Date.now()}`,
        reward_id: `wheel-${slice.id}`,
        reward_name: `${slice.label} (گردونه شانس)`,
        reward_type: slice.type,
        points_spent: 0,
        claimed_at: new Date().toISOString(),
        code: slice.couponCode,
        status: "active",
      };

      setClaimedRecords((prev) => {
        const updated = [newClaim, ...prev];
        if (typeof window !== "undefined") {
          localStorage.setItem("gamification_user_claims", JSON.stringify(updated));
        }
        return updated;
      });
    }
  };

  // Catalog claim handler
  const handleClaimSuccess = (claimRecord: ApiClaimRecord) => {
    setClaimedRecords((prev) => {
      const updated = [claimRecord, ...prev];
      if (typeof window !== "undefined") {
        localStorage.setItem("gamification_user_claims", JSON.stringify(updated));
      }
      return updated;
    });
  };

  const scrollToWheel = () => {
    if (wheelSectionRef.current) {
      wheelSectionRef.current.scrollIntoView({ behavior: "smooth", block: "center" });
    }
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
            <span>باشگاه مشتریان و گردونه شانس فروشگاه</span>
          </div>
          <h1 className="text-3xl sm:text-4xl font-black text-foreground tracking-tight">
            بچرخانید، امتیاز جمع کنید و جایزه بگیرید!
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground leading-relaxed">
            با هر بار ورود، شرکت در گردونه روزانه و انجام خرید، امتیاز دریافت کنید و به راحتی آنها را به کدهای تخفیف، ارسال رایگان و هدایای نقدی تبدیل نمایید.
          </p>
        </div>

        {/* Section 1: User Points & Loyalty Tier Banner */}
        <UserTierBanner
          userPoints={mounted ? points : 120}
          userName={displayName}
          onScrollToWheel={scrollToWheel}
        />

        {/* Section 2: Interactive Spin Wheel (گردونه شانس) & Daily Streak Row */}
        <div
          ref={wheelSectionRef}
          className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start"
        >
          {/* Left Column (Wheel of Fortune): 7 cols on large screens */}
          <div className="lg:col-span-7 space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400">
                  <Trophy className="h-4 w-4" />
                </div>
                <h2 className="text-xl font-black text-foreground">
                  گردونه شانس (چرخ روزانه)
                </h2>
              </div>
              <Badge variant="outline" className="text-[11px] font-semibold">
                ۸ جایزه تضمینی
              </Badge>
            </div>

            <WheelOfFortune
              userPoints={mounted ? points : 120}
              onPointsUpdate={handlePointsUpdate}
              onRewardWon={handleWheelRewardWon}
            />
          </div>

          {/* Right Column (Daily Streak Tracker & Benefits): 5 cols */}
          <div className="lg:col-span-5 space-y-6">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-orange-500/15 text-orange-600 dark:text-orange-400">
                <Flame className="h-4 w-4" />
              </div>
              <h2 className="text-xl font-black text-foreground">
                زنجیره ورود روزانه
              </h2>
            </div>

            <DailyStreakCard
              userPoints={mounted ? points : 120}
              onPointsUpdate={handlePointsUpdate}
            />

            {/* Quick Rules & Tips Card */}
            <div className="rounded-3xl border border-border/80 bg-card/60 p-6 backdrop-blur shadow-md space-y-3.5">
              <h4 className="text-sm font-bold text-foreground flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-primary" />
                <span>قوانین و راهنمای کسب امتیاز</span>
              </h4>
              <ul className="space-y-2 text-xs text-muted-foreground leading-relaxed">
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>
                    هر کاربر در هر ۲۴ ساعت، ۱ چرخش کاملاً رایگان در گردونه شانس دارد.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>
                    چرخش‌های بعدی روزانه با صرف ۲۰ امتیاز باشگاه انجام می‌شوند.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>
                    کدهای تخفیف برنده شده تا ۳۰ روز پس از صدور در سبد خرید معتبر می‌باشند.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5 shrink-0" />
                  <span>
                    با ارتقای سطح به طلایی و پلاتینیوم، شانس‌های ویژه و جوایز ماهانه دریافت خواهید کرد.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Section 3: Available Rewards Catalog */}
        <section className="pt-4">
          <RewardsCatalog
            userPoints={mounted ? points : 120}
            onPointsUpdate={handlePointsUpdate}
            onClaimSuccess={handleClaimSuccess}
          />
        </section>

        {/* Section 4: Recent Rewards Claim & Activity History */}
        <section className="pt-4">
          <ClaimHistory
            claimRecords={claimedRecords}
            activityList={activityList}
          />
        </section>
      </div>
    </div>
  );
}
