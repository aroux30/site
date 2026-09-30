"use client";

import React, { useState } from "react";
import { Wallet, RefreshCw, CheckCircle2, XCircle, Receipt, CreditCard, Plus, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { PageLoader } from "@/components/shared/page-state";

const FINTECH_GATEWAYS_KEY = "admin-fintech-gateways" as const;
const FINTECH_RECEIPTS_KEY = "admin-fintech-receipts" as const;

interface GatewaySetting {
  id: string;
  provider_key: string;
  title_fa: string;
  is_active: boolean;
  is_default: boolean;
  priority: number;
  min_amount: number;
  max_amount: number;
}

interface CardTransferReceipt {
  id: string;
  order_id: string;
  user_id: string;
  amount: number;
  tracking_code: string;
  source_card_last4: string;
  status: "pending_review" | "approved" | "rejected";
  admin_notes: string | null;
  reviewed_at: string | null;
  created_at: string;
}

export default function AdminFintechPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"gateways" | "receipts">("gateways");

  // Two independent queries, not one. The page loaded both endpoints with
  // Promise.allSettled and kept whichever succeeded, so a gateways outage
  // still showed the receipts table. Collapsing them into a single query key
  // would make one failure blank both tables — a regression in exactly the
  // situation this screen exists to handle.
  const gatewaysQuery = useAdminQuery({
    queryKey: [FINTECH_GATEWAYS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/payments/fintech/gateways");
      return Array.isArray(res.data) ? (res.data as GatewaySetting[]) : [];
    },
    fallbackError: "خطا در دریافت درگاه‌های پرداخت",
  });
  const receiptsQuery = useAdminQuery({
    queryKey: [FINTECH_RECEIPTS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/payments/fintech/admin/card2card/receipts");
      return Array.isArray(res.data) ? (res.data as CardTransferReceipt[]) : [];
    },
    fallbackError: "خطا در دریافت فیش‌های کارت به کارت",
  });
  const gateways: GatewaySetting[] = gatewaysQuery.data ?? [];
  const receipts: CardTransferReceipt[] = receiptsQuery.data ?? [];
  const loading = gatewaysQuery.loading || receiptsQuery.loading;
  const gatewaysError = gatewaysQuery.error !== null;
  const receiptsError = receiptsQuery.error !== null;
  const runMutation = useAdminMutation();

  const fetchData = async () => {
    await Promise.all([gatewaysQuery.reload(), receiptsQuery.reload()]);
  };

  const reviewReceipt = async (receiptId: string, isApproved: boolean) => {
    const result = await runMutation(
      () =>
        apiClient.post(`/payments/fintech/admin/card2card/receipts/${receiptId}/review`, {
          is_approved: isApproved,
        }),
      {
        fallbackError: "بررسی فیش با خطا مواجه شد",
        invalidateKeys: [[FINTECH_RECEIPTS_KEY]],
      },
    );
    if (result.ok) {
      toast({
        title: isApproved ? "تایید شد" : "رد شد",
        description: isApproved
          ? "فیش تایید شد؛ پرداخت کارت‌به‌کارت مرتبط کامل و سفارش تایید می‌شود"
          : "فیش رد شد و پرداخت مرتبط (در صورت وجود) لغو می‌شود",
      });
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const statusLabels: Record<string, string> = {
    pending_review: "در انتظار بررسی",
    approved: "تایید‌شده",
    rejected: "رد‌شده",
  };

  const statusColors: Record<string, string> = {
    pending_review: "bg-amber-500/10 text-amber-500",
    approved: "bg-emerald-500/10 text-emerald-500",
    rejected: "bg-rose-500/10 text-rose-500",
  };

  const gatewayColumns: DataTableColumn<GatewaySetting>[] = [
    {
      key: "name",
      header: "درگاه",
      className: "font-medium",
      render: (g) => g.title_fa,
    },
    {
      key: "key",
      header: "کلید",
      className: "font-mono text-xs",
      render: (g) => <span dir="ltr">{g.provider_key}</span>,
    },
    {
      key: "priority",
      header: "اولویت",
      className: "text-center",
      render: (g) => g.priority,
    },
    {
      key: "active",
      header: "فعال",
      render: (g) => (
        <Badge className={g.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}>
          {g.is_active ? "فعال" : "غیرفعال"}
        </Badge>
      ),
    },
    {
      key: "default",
      header: "پیش‌فرض",
      render: (g) => (
        <Badge className={g.is_default ? "bg-blue-500/10 text-blue-500" : ""}>
          {g.is_default ? "پیش‌فرض" : "-"}
        </Badge>
      ),
    },
  ];

  const receiptColumns: DataTableColumn<CardTransferReceipt>[] = [
    {
      key: "tracking",
      header: "شماره پیگیری",
      className: "font-mono text-xs",
      render: (r) => <span dir="ltr">{r.tracking_code}</span>,
    },
    {
      key: "amount",
      header: "مبلغ",
      className: "text-xs",
      render: (r) => `${r.amount.toLocaleString("fa-IR")} ریال`,
    },
    {
      key: "card",
      header: "کارت مبدا",
      className: "font-mono text-xs",
      render: (r) => <span dir="ltr">****{r.source_card_last4}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) => <Badge className={statusColors[r.status]}>{statusLabels[r.status]}</Badge>,
    },
    {
      key: "actions",
      header: "عملیات",
      render: (r) =>
        r.status === "pending_review" ? (
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              className="text-emerald-600"
              aria-label="تایید فیش"
              onClick={() => reviewReceipt(r.id, true)}
            >
              <CheckCircle2 className="h-4 w-4" />
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="text-rose-600"
              aria-label="رد فیش"
              onClick={() => reviewReceipt(r.id, false)}
            >
              <XCircle className="h-4 w-4" />
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Wallet className="h-5 w-5 text-primary" />
            پرداخت، کارت‌به‌کارت و درگاه‌ها
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            مدیریت درگاه‌های پرداخت و بررسی فیش‌های کارت‌به‌کارت
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      {/* Tab Switch */}
      <div className="flex gap-2">
        <Button variant={tab === "gateways" ? "default" : "outline"} size="sm" onClick={() => setTab("gateways")}>
          <CreditCard className="h-4 w-4 ms-2" />
          درگاه‌های پرداخت ({gateways.length})
        </Button>
        <Button variant={tab === "receipts" ? "default" : "outline"} size="sm" onClick={() => setTab("receipts")}>
          <Receipt className="h-4 w-4 ms-2" />
          فیش‌های کارت‌به‌کارت ({receipts.length})
        </Button>
      </div>

      {loading ? (
        <PageLoader message="در حال دریافت اطلاعات فین‌تک..." className="min-h-0 p-12" />
      ) : tab === "gateways" ? (
        <DataTable<GatewaySetting>
          columns={gatewayColumns}
          rows={gateways}
          rowKey={(g) => g.id}
          error={gatewaysError ? "خطا در دریافت درگاه‌های پرداخت" : null}
          emptyMessage="هیچ درگاهی ثبت نشده است."
        />
      ) : (
        <DataTable<CardTransferReceipt>
          columns={receiptColumns}
          rows={receipts}
          rowKey={(r) => r.id}
          error={receiptsError ? "خطا در دریافت فیش‌های کارت به کارت" : null}
          emptyMessage="هیچ فیشی ثبت نشده است."
        />
      )}
    </div>
  );
}
