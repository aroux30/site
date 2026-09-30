"use client";

import React from "react";
import { Shield, RefreshCw, CreditCard, AlertTriangle, Users } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api/client";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { PageLoader } from "@/components/shared/page-state";
import { useAdminQuery } from "@/lib/api/admin-query";

const ANTI_FRAUD_QUERY_KEY = "admin-anti-fraud" as const;

interface UserTrustProfile {
  user_id: string;
  is_trusted: boolean;
  shahkar_verified: boolean;
  risk_score: number;
  delayed_delivery_enabled: boolean;
  daily_spend_limit: number;
}

interface FailedAttempt {
  id: string;
  identifier: string;
  attempt_type: string;
  ip_address: string | null;
  created_at: string;
}

export default function AdminAntiFraudPage() {
  // Both lists come from the same admin fetch, so they share one query and
  // cannot disagree with each other the way two independent loads could.
  const {
    data,
    loading,
    reload: fetchData,
  } = useAdminQuery({
    queryKey: [ANTI_FRAUD_QUERY_KEY],
    queryFn: async () => {
      // P1.4: real admin endpoints — trust profiles list and persisted
      // failed attempts (Karta failed_attempts).
      const [trustRes, attemptsRes] = await Promise.all([
        apiClient.get("/users/admin/kyc/trust-profiles", { params: { page_size: 50 } }),
        apiClient.get("/users/admin/security/failed-attempts", {
          params: { page_size: 50 },
        }),
      ]);
      return {
        trustProfiles: Array.isArray(trustRes.data?.items) ? trustRes.data.items : [],
        failedAttempts: Array.isArray(attemptsRes.data?.items) ? attemptsRes.data.items : [],
      };
    },
    fallbackError: "بارگذاری اطلاعات ضدتقلب با خطا مواجه شد",
    // This page reported load failures as a toast; keep that behaviour.
    toastOnError: true,
  });
  const trustProfiles: UserTrustProfile[] = data?.trustProfiles ?? [];
  const failedAttempts: FailedAttempt[] = data?.failedAttempts ?? [];

  const trustColumns: DataTableColumn<UserTrustProfile>[] = [
    {
      key: "user",
      header: "کاربر",
      className: "font-mono text-xs",
      render: (p) => <span dir="ltr">{p.user_id.slice(0, 8)}...</span>,
    },
    {
      key: "shahkar",
      header: "شاهکار",
      render: (p) => (
        <Badge
          className={p.shahkar_verified ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}
        >
          {p.shahkar_verified ? "تایید‌شده" : "تایید نشده"}
        </Badge>
      ),
    },
    {
      key: "risk",
      header: "امتیاز ریسک",
      render: (p) => (
        <Badge
          className={
            p.risk_score < 30
              ? "bg-emerald-500/10 text-emerald-500"
              : p.risk_score < 60
                ? "bg-amber-500/10 text-amber-500"
                : "bg-rose-500/10 text-rose-500"
          }
        >
          {p.risk_score} / 100
        </Badge>
      ),
    },
    {
      key: "limit",
      header: "سقف روزانه",
      className: "text-xs",
      render: (p) => `${p.daily_spend_limit.toLocaleString("fa-IR")} ریال`,
    },
    {
      key: "delivery",
      header: "تحویل",
      render: (p) => (
        <Badge className={p.is_trusted ? "bg-emerald-500/10 text-emerald-500" : "bg-amber-500/10 text-amber-500"}>
          {p.is_trusted ? "آنی" : "با تاخیر"}
        </Badge>
      ),
    },
  ];

  const attemptColumns: DataTableColumn<FailedAttempt>[] = [
    {
      key: "identifier",
      header: "شناسه",
      className: "font-mono text-xs",
      render: (a) => <span dir="ltr">{a.identifier}</span>,
    },
    {
      key: "type",
      header: "نوع",
      render: (a) => <Badge variant="outline">{a.attempt_type}</Badge>,
    },
    {
      key: "ip",
      header: "IP",
      className: "font-mono text-xs",
      render: (a) => <span dir="ltr">{a.ip_address || "-"}</span>,
    },
    {
      key: "time",
      header: "زمان",
      className: "text-xs text-muted-foreground",
      render: (a) => (
        <span dir="ltr">{new Date(a.created_at).toLocaleString("fa-IR")}</span>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            سامانه ضدتقلب و احراز هویت
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            پروفایل اعتماد کاربران، استعلام شاهکار و لاگ تلاش‌های ناموفق
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <PageLoader message="در حال دریافت داده‌های ضد‌تقلب..." className="min-h-0 p-12" />
      ) : (
        <div className="space-y-6">
          {/* Trust Profiles */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <Users className="h-4 w-4 text-primary" />
              پروفایل اعتماد کاربران
            </h3>
            <DataTable<UserTrustProfile>
              columns={trustColumns}
              rows={trustProfiles}
              rowKey={(p) => p.user_id}
              emptyMessage="هنوز هیچ کاربری احراز هویت نشده است"
              emptyIcon={<Users className="h-8 w-8 text-muted-foreground/40" />}
            />
          </Card>

          {/* Failed Attempts */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold flex items-center gap-2 mb-4">
              <AlertTriangle className="h-4 w-4 text-amber-500" />
              لاگ تلاش‌های ناموفق (Brute-Force)
            </h3>
            <DataTable<FailedAttempt>
              columns={attemptColumns}
              rows={failedAttempts}
              rowKey={(a) => a.id}
              emptyMessage="هیچ تلاش ناموفقی ثبت نشده است"
              emptyIcon={<AlertTriangle className="h-8 w-8 text-muted-foreground/40" />}
            />
          </Card>
        </div>
      )}
    </div>
  );
}
