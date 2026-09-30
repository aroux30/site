"use client";

import React, { useState } from "react";
import {
  History,
  Gift,
  Check,
  Copy,
  Tag,
  ArrowDownLeft,
  ArrowUpRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { toPersianDigits } from "@/lib/utils";
import type { ApiClaimRecord } from "@/lib/api/gamification";

interface ActivityItem {
  id: string;
  title: string;
  date: string;
  pointsChange: number; // positive = earned, negative = spent
  type: "spin" | "claim" | "streak" | "bonus";
  code?: string;
  status?: string;
}

interface ClaimHistoryProps {
  claimRecords: ApiClaimRecord[];
  activityList: ActivityItem[];
}

// Convert Gregorian ISO date to Persian formatted date
function formatJalaliDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    return new Intl.DateTimeFormat("fa-IR", {
      year: "numeric",
      month: "long",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch {
    return isoString;
  }
}

export function ClaimHistory({ claimRecords, activityList }: ClaimHistoryProps) {
  const [activeTab, setActiveTab] = useState<"claims" | "activity">("claims");
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  const copyToClipboard = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    setTimeout(() => setCopiedCode(null), 2500);
  };

  return (
    <Card className="overflow-hidden border-border/80 bg-card/60 backdrop-blur shadow-lg">
      <div className="p-5 sm:p-7">
        {/* Header & Tabs */}
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-border/60 pb-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-primary/10 text-primary">
              <History className="h-5 w-5" />
            </div>
            <div>
              <h3 className="text-lg font-bold text-foreground">
                تاریخچه جوایز و امتیازات
              </h3>
              <p className="text-xs text-muted-foreground mt-0.5">
                مشاهده کدهای دریافتی و سابقه تراکنش‌های باشگاه مشتریان
              </p>
            </div>
          </div>

          <div className="flex items-center gap-1 p-1 rounded-xl bg-muted/60 border border-border">
            <button
              type="button"
              onClick={() => setActiveTab("claims")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === "claims"
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              جوایز دریافت شده ({toPersianDigits(claimRecords.length)})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("activity")}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all ${
                activeTab === "activity"
                  ? "bg-background text-foreground shadow-xs"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              گردش امتیازات ({toPersianDigits(activityList.length)})
            </button>
          </div>
        </div>

        {/* Tab 1: Claimed Rewards */}
        {activeTab === "claims" && (
          <div className="mt-5">
            {claimRecords.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Gift className="h-10 w-10 text-muted-foreground/50 mb-2" />
                <p className="text-sm font-medium text-foreground">
                  هنوز جایزه‌ای دریافت نکرده‌اید!
                </p>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm">
                  با چرخاندن گردونه شانس و جمع‌آوری امتیاز در کاتالوگ بالا، جوایز و کدهای تخفیف اختصاصی دریافت کنید.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {claimRecords.map((record) => (
                  <div
                    key={record.id}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-2xl border border-border/80 bg-background/50 p-4 transition-all hover:bg-muted/40"
                  >
                    <div className="flex items-start sm:items-center gap-3">
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary/10 text-primary">
                        <Tag className="h-5 w-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-bold text-foreground">
                            {record.reward_name}
                          </span>
                          <Badge
                            variant="secondary"
                            className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[10px] py-0"
                          >
                            فعال
                          </Badge>
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
                          <span>{formatJalaliDate(record.claimed_at)}</span>
                          <span>•</span>
                          <span>{toPersianDigits(record.points_spent)} امتیاز صرف شده</span>
                        </div>
                      </div>
                    </div>

                    {/* Copy code button */}
                    <div className="flex items-center gap-2 self-end sm:self-center">
                      <div className="rounded-lg bg-muted/60 px-3 py-1.5 font-mono text-xs font-bold text-primary border border-border">
                        {record.code}
                      </div>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyToClipboard(record.code)}
                        className="h-8 gap-1 text-xs"
                      >
                        {copiedCode === record.code ? (
                          <>
                            <Check className="h-3.5 w-3.5 text-emerald-600" />
                            <span>کپی شد</span>
                          </>
                        ) : (
                          <>
                            <Copy className="h-3.5 w-3.5" />
                            <span>کپی</span>
                          </>
                        )}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Tab 2: Activity List */}
        {activeTab === "activity" && (
          <div className="mt-5">
            {activityList.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center text-muted-foreground">
                <History className="h-10 w-10 opacity-40 mb-2" />
                <span className="text-xs">هیچ تراکنشی یافت نشد.</span>
              </div>
            ) : (
              <div className="space-y-2.5">
                {activityList.map((item) => {
                  const isPositive = item.pointsChange > 0;

                  return (
                    <div
                      key={item.id}
                      className="flex items-center justify-between rounded-xl border border-border/60 bg-background/40 p-3.5 transition-colors hover:bg-muted/30"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                            isPositive
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                          }`}
                        >
                          {isPositive ? (
                            <ArrowDownLeft className="h-4 w-4" />
                          ) : (
                            <ArrowUpRight className="h-4 w-4" />
                          )}
                        </div>
                        <div>
                          <div className="text-xs sm:text-sm font-semibold text-foreground">
                            {item.title}
                          </div>
                          <div className="text-[11px] text-muted-foreground">
                            {formatJalaliDate(item.date)}
                          </div>
                        </div>
                      </div>

                      <div
                        className={`font-mono text-xs sm:text-sm font-black ${
                          isPositive
                            ? "text-emerald-600 dark:text-emerald-400"
                            : "text-amber-600 dark:text-amber-400"
                        }`}
                      >
                        {isPositive ? "+" : ""}
                        {toPersianDigits(item.pointsChange)} امتیاز
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
