"use client";

import React, { useState, useEffect } from "react";
import {
  Gift,
  Tag,
  Coins,
  Check,
  Copy,
  Sparkles,
  Lock,
  Loader2,
  Package,
  AlertCircle,
} from "lucide-react";
import { Card } from "@/components/ui/card";
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
import { triggerCelebrationCannons } from "@/components/ui/confetti";
import {
  fetchGamificationRewards,
  claimGamificationReward,
  type ApiReward,
  type ApiClaimRecord,
} from "@/lib/api/gamification";
import { useAuthStore } from "@/stores/auth-store";

interface RewardsCatalogProps {
  userPoints: number;
  onPointsUpdate: (_newPoints: number, _change: number, _reason: string) => void;
  onClaimSuccess?: (_claimRecord: ApiClaimRecord) => void;
}

export function RewardsCatalog({
  userPoints,
  onPointsUpdate,
  onClaimSuccess,
}: RewardsCatalogProps) {
  const { user, updateProfile } = useAuthStore();
  const [rewards, setRewards] = useState<ApiReward[]>([]);
  const [loading, setLoading] = useState(true);
  const [claimingId, setClaimingId] = useState<string | null>(null);
  const [claimError, setClaimError] = useState<string | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("all");

  // Claim modal state
  const [claimedReward, setClaimedReward] = useState<{
    reward: ApiReward;
    code: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  // Load rewards from API
  useEffect(() => {
    let mounted = true;
    async function load() {
      setLoading(true);
      try {
        const data = await fetchGamificationRewards();
        if (mounted) {
          setRewards(data);
        }
      } catch {
        // Handled in api module
      } finally {
        if (mounted) setLoading(false);
      }
    }
    load();
    return () => {
      mounted = false;
    };
  }, []);

  const handleClaim = async (reward: ApiReward) => {
    if (userPoints < reward.points_required || claimingId) return;

    setClaimingId(reward.id);
    try {
      const response = await claimGamificationReward(reward.id);

      // Deduct points
      const newPoints = Math.max(0, userPoints - reward.points_required);
      onPointsUpdate(
        newPoints,
        -reward.points_required,
        `دریافت جایزه: ${reward.name}`,
      );

      // Update auth store user
      if (user) {
        updateProfile({
          loyalty_points: newPoints,
          loyaltyPoints: newPoints,
        });
      }

      // Generate or retrieve coupon code
      const code =
        response.coupon_code ||
        `GIFT-${Math.random().toString(36).substring(2, 8).toUpperCase()}`;

      const claimRecord: ApiClaimRecord = {
        id: `claim-${Date.now()}`,
        reward_id: reward.id,
        reward_name: reward.name,
        reward_type: reward.type,
        points_spent: reward.points_required,
        claimed_at: new Date().toISOString(),
        code,
        status: "active",
      };

      if (onClaimSuccess) {
        onClaimSuccess(claimRecord);
      }

      setClaimedReward({ reward, code });
      triggerCelebrationCannons();
    } catch {
      // Backend claim failed — do NOT deduct points or fake a coupon.
      setClaimError("دریافت جایزه ممکن نشد. لطفاً دوباره تلاش کنید.");
      setTimeout(() => setClaimError(null), 5000);
    } finally {
      setClaimingId(null);
    }
  };

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  const filteredRewards = rewards.filter((r) => {
    if (activeCategory === "all") return true;
    if (activeCategory === "discount") return r.type === "discount";
    if (activeCategory === "voucher") return r.type === "voucher";
    if (activeCategory === "gift") return r.type === "gift" || r.type === "physical";
    return true;
  });

  return (
    <div className="space-y-6">
      {claimError && (
        <div
          role="alert"
          className="flex items-center gap-2 rounded-xl border border-destructive/25 bg-destructive/10 p-3 text-sm text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          {claimError}
        </div>
      )}
      {/* Section Header & Filter Tabs */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-foreground flex items-center gap-2">
            <Gift className="h-6 w-6 text-primary" />
            <span>کاتالوگ جوایز قابل دریافت</span>
          </h2>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            امتیازات خود را به کدهای تخفیف، ارسال رایگان یا هدایای ویژه تبدیل کنید.
          </p>
        </div>

        {/* Categories */}
        <div className="flex flex-wrap items-center gap-1.5 p-1 rounded-xl bg-muted/60 border border-border">
          {[
            { id: "all", label: "همه جوایز" },
            { id: "discount", label: "تخفیف‌ها" },
            { id: "voucher", label: "بن‌های خرید" },
            { id: "gift", label: "هدایای فیزیکی" },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              onClick={() => setActiveCategory(tab.id)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeCategory === tab.id
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Rewards Grid */}
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin text-primary mb-2" />
          <span className="text-sm">در حال بارگذاری کاتالوگ جوایز...</span>
        </div>
      ) : filteredRewards.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">
          موردی در این دسته یافت نشد.
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filteredRewards.map((reward) => {
            const canAfford = userPoints >= reward.points_required;
            const progress = Math.min(
              100,
              Math.max(3, Math.round((userPoints / reward.points_required) * 100)),
            );
            const remainingPoints = reward.points_required - userPoints;

            return (
              <Card
                key={reward.id}
                className={`group relative flex flex-col justify-between overflow-hidden rounded-2xl border transition-all duration-300 hover:shadow-lg ${
                  canAfford
                    ? "border-primary/40 bg-card hover:border-primary"
                    : "border-border/60 bg-card/60 opacity-90"
                }`}
              >
                <div className="p-5">
                  {/* Top Row: Type Badge & Points Required */}
                  <div className="flex items-center justify-between gap-2 mb-3">
                    <Badge
                      variant="secondary"
                      className="text-[11px] font-semibold flex items-center gap-1.5 px-2.5 py-0.5"
                    >
                      {reward.type === "discount" ? (
                        <>
                          <Tag className="h-3 w-3 text-pink-500" />
                          <span>کد تخفیف</span>
                        </>
                      ) : reward.type === "voucher" ? (
                        <>
                          <Gift className="h-3 w-3 text-amber-500" />
                          <span>بن خرید</span>
                        </>
                      ) : (
                        <>
                          <Package className="h-3 w-3 text-primary" />
                          <span>هدیه فروشگاه</span>
                        </>
                      )}
                    </Badge>

                    <div className="flex items-center gap-1 font-bold text-foreground">
                      <Coins className="h-4 w-4 text-amber-500" />
                      <span className="text-sm font-black">
                        {toPersianDigits(reward.points_required)}
                      </span>
                      <span className="text-[11px] text-muted-foreground font-normal">
                        امتیاز
                      </span>
                    </div>
                  </div>

                  {/* Title & Description */}
                  <h3 className="font-bold text-base text-foreground mb-2 group-hover:text-primary transition-colors line-clamp-2">
                    {reward.name}
                  </h3>
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed mb-4">
                    {reward.description || "قابل استفاده در کلیه سفارش‌های فروشگاه"}
                  </p>

                  {/* Points Progress Bar */}
                  <div className="space-y-1.5 pt-1">
                    <div className="flex justify-between text-[11px]">
                      <span className="text-muted-foreground">
                        {canAfford ? (
                          <span className="text-emerald-600 dark:text-emerald-400 font-semibold flex items-center gap-1">
                            <Check className="h-3 w-3" /> آماده دریافت
                          </span>
                        ) : (
                          <span>نیاز به {toPersianDigits(remainingPoints)} امتیاز دیگر</span>
                        )}
                      </span>
                      <span className="font-bold font-mono text-muted-foreground">
                        {toPersianDigits(progress)}٪
                      </span>
                    </div>

                    <div className="h-2 w-full overflow-hidden rounded-full bg-muted border border-border/60">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          canAfford
                            ? "bg-gradient-to-r from-emerald-500 to-teal-400"
                            : "bg-primary/70"
                        }`}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                </div>

                {/* Card Action Footer */}
                <div className="border-t border-border/60 bg-muted/20 p-4">
                  <Button
                    onClick={() => handleClaim(reward)}
                    disabled={!canAfford || claimingId === reward.id}
                    className={`w-full h-10 rounded-xl font-bold transition-all text-xs sm:text-sm ${
                      canAfford
                        ? "bg-primary text-primary-foreground hover:bg-primary/90 shadow-md shadow-primary/20"
                        : "bg-muted text-muted-foreground cursor-not-allowed"
                    }`}
                  >
                    {claimingId === reward.id ? (
                      <div className="flex items-center gap-2">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        <span>در حال ثبت جایزه...</span>
                      </div>
                    ) : canAfford ? (
                      <div className="flex items-center gap-2">
                        <Sparkles className="h-4 w-4" />
                        <span>دریافت جایزه</span>
                      </div>
                    ) : (
                      <div className="flex items-center gap-1.5">
                        <Lock className="h-3.5 w-3.5" />
                        <span>امتیاز ناکافی</span>
                      </div>
                    )}
                  </Button>
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* Reward Claimed Dialog */}
      <Dialog open={!!claimedReward} onOpenChange={() => setClaimedReward(null)}>
        <DialogContent className="sm:max-w-md text-center p-6">
          <DialogHeader>
            <div className="mx-auto my-2 flex h-16 w-16 items-center justify-center rounded-2xl bg-emerald-500/15 text-emerald-600 dark:text-emerald-400 shadow-md animate-in zoom-in-75 duration-300">
              <Gift className="h-8 w-8" />
            </div>
            <DialogTitle className="text-xl font-black text-foreground">
              جایزه شما با موفقیت صادر شد!
            </DialogTitle>
            <DialogDescription className="text-xs text-muted-foreground">
              کد هدیه اختصاصی برای شما صادر و در سابقه جوایز ذخیره گردید.
            </DialogDescription>
          </DialogHeader>

          {claimedReward && (
            <div className="my-4 space-y-3">
              <div className="rounded-xl border border-border bg-muted/40 p-3 text-right">
                <div className="text-xs text-muted-foreground">نام جایزه:</div>
                <div className="text-sm font-bold text-foreground mt-0.5">
                  {claimedReward.reward.name}
                </div>
              </div>

              {/* Coupon Code Box */}
              <div className="rounded-xl border border-dashed border-primary/50 bg-primary/5 p-4 text-right">
                <div className="text-xs text-muted-foreground mb-1.5 font-medium">
                  کد کوپن شما:
                </div>
                <div className="flex items-center justify-between gap-2 rounded-lg bg-background p-2.5 border border-border">
                  <span className="font-mono text-base font-bold tracking-wider text-primary">
                    {claimedReward.code}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copyCode(claimedReward.code)}
                    className="gap-1.5 text-xs h-8"
                  >
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-emerald-600" />
                        <span>کپی شد!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5" />
                        <span>کپی کد</span>
                      </>
                    )}
                  </Button>
                </div>
              </div>
            </div>
          )}

          <Button
            className="w-full rounded-xl bg-primary text-primary-foreground font-bold"
            onClick={() => setClaimedReward(null)}
          >
            بستن و ادامه خرید
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
