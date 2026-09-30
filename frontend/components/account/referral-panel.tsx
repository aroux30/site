"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Copy, Check, Users, Gift, Loader2, AlertCircle, Share2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { formatPrice, toPersianDigits } from "@/lib/utils";
import {
  buildInviteUrl,
  fetchReferralCode,
  fetchReferralStats,
  type ApiReferralStats,
} from "@/lib/api/referrals";

const EMPTY_STATS: ApiReferralStats = {
  total_referrals: 0,
  completed_referrals: 0,
  pending_referrals: 0,
  level1_count: 0,
  level2_count: 0,
  total_commission_earned: 0,
  total_commission_pending: 0,
};

/**
 * "Invite friends" panel.
 *
 * The referral code is fetched from the server (it is persisted per user, so
 * it is stable) and never generated client-side — a locally invented code
 * could never be resolved back to this referrer at signup.
 */
export function ReferralPanel() {
  const { toast } = useToast();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [code, setCode] = useState<string | null>(null);
  const [inviteUrl, setInviteUrl] = useState<string>("");
  const [stats, setStats] = useState<ApiReferralStats>(EMPTY_STATS);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [codeData, statsData] = await Promise.all([
        fetchReferralCode(),
        // Stats are non-critical: a failure here must not hide the invite
        // link, which is the whole point of the panel.
        fetchReferralStats().catch(() => EMPTY_STATS),
      ]);
      setCode(codeData.referral_code);
      setInviteUrl(buildInviteUrl(codeData.referral_link));
      setStats(statsData);
    } catch (err: unknown) {
      setError(
        (err as { message?: string })?.message ||
          "دریافت کد معرف با خطا مواجه شد. لطفاً دوباره تلاش کنید."
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCopy = async () => {
    if (!inviteUrl) return;
    try {
      await navigator.clipboard.writeText(inviteUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
      toast({ title: "لینک دعوت کپی شد", variant: "success" });
    } catch {
      toast({
        title: "کپی خودکار ممکن نشد",
        description: "لطفاً لینک را دستی انتخاب و کپی کنید.",
        variant: "destructive",
      });
    }
  };

  if (loading) {
    return (
      <Card className="flex items-center justify-center gap-2 p-10 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال دریافت اطلاعات دعوت...
      </Card>
    );
  }

  if (error) {
    return (
      <Card className="space-y-4 p-8 text-center">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-destructive/10 text-destructive">
          <AlertCircle className="h-7 w-7" />
        </div>
        <p className="text-sm text-muted-foreground">{error}</p>
        <Button onClick={() => void load()} variant="outline">
          تلاش دوباره
        </Button>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <div className="text-center space-y-2">
        <div className="inline-flex items-center gap-2 rounded-full border border-primary/20 bg-primary/10 px-3.5 py-1.5 text-xs font-bold text-primary">
          <Users className="h-3.5 w-3.5" />
          <span>دعوت دوستان</span>
        </div>
        <h2 className="text-2xl font-black text-foreground">دوستات رو دعوت کن، پاداش بگیر</h2>
        <p className="mx-auto max-w-lg text-xs leading-relaxed text-muted-foreground">
          لینک اختصاصی خود را برای دوستانت بفرست. با ثبت‌نام آن‌ها از طریق این لینک، معرفی شما
          ثبت می‌شود و پاداش آن به حساب شما اضافه می‌گردد.
        </p>
      </div>

      <Card className="space-y-4 p-6">
        <div className="space-y-2">
          <span className="text-xs font-semibold text-muted-foreground">کد اختصاصی شما</span>
          <div className="flex items-center justify-center rounded-2xl border border-dashed border-primary/40 bg-primary/5 py-4">
            <span className="font-mono text-2xl font-black tracking-[0.2em] text-primary" dir="ltr">
              {code}
            </span>
          </div>
        </div>

        <div className="space-y-2">
          <span className="text-xs font-semibold text-muted-foreground">لینک دعوت</span>
          <div className="flex items-center gap-2">
            <div
              className="flex-1 truncate rounded-xl border border-border bg-muted/40 px-3 py-2.5 font-mono text-xs text-foreground"
              dir="ltr"
              title={inviteUrl}
            >
              {inviteUrl}
            </div>
            <Button onClick={handleCopy} size="sm" className="shrink-0">
              {copied ? (
                <>
                  <Check className="ms-1.5 h-3.5 w-3.5" />
                  کپی شد
                </>
              ) : (
                <>
                  <Copy className="ms-1.5 h-3.5 w-3.5" />
                  کپی
                </>
              )}
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: "کل دعوت‌ها", value: stats.total_referrals },
          { label: "تکمیل‌شده", value: stats.completed_referrals },
          { label: "در انتظار", value: stats.pending_referrals },
          { label: "سطح ۱", value: stats.level1_count },
        ].map((item) => (
          <Card key={item.label} className="p-4 text-center">
            <div className="text-2xl font-black text-foreground">
              {toPersianDigits(item.value)}
            </div>
            <div className="mt-1 text-[11px] text-muted-foreground">{item.label}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <div className="mb-3 flex items-center gap-2">
          <Gift className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
          <h3 className="text-sm font-bold text-foreground">پاداش‌های شما</h3>
        </div>
        <div className="space-y-2.5">
          <div className="flex items-center justify-between border-b border-border/60 pb-2.5">
            <span className="text-xs text-muted-foreground">پاداش پرداخت‌شده</span>
            <span className="font-bold text-foreground">
              {formatPrice(Math.round(stats.total_commission_earned / 10))}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted-foreground">پاداش در انتظار</span>
            <div className="flex items-center gap-2">
              <span className="font-bold text-foreground">
                {formatPrice(Math.round(stats.total_commission_pending / 10))}
              </span>
              {stats.total_commission_pending > 0 && (
                <Badge variant="outline" className="text-[10px]">
                  در انتظار تسویه
                </Badge>
              )}
            </div>
          </div>
        </div>
      </Card>

      <Card className="flex items-start gap-3 border-primary/20 bg-primary/5 p-4">
        <Share2 className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
        <p className="text-xs leading-relaxed text-muted-foreground">
          دوست شما هم هنگام ثبت‌نام می‌تواند از کد اختصاصی شما استفاده کند. این کد ثابت است و
          همیشه قابل استفاده خواهد بود.
        </p>
      </Card>
    </div>
  );
}
