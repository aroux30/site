"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Wallet, RefreshCw, CheckCircle2, XCircle, Receipt, CreditCard, Plus, Eye } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";

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
  const [gateways, setGateways] = useState<GatewaySetting[]>([]);
  const [receipts, setReceipts] = useState<CardTransferReceipt[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"gateways" | "receipts">("gateways");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [gwRes, rcptRes] = await Promise.allSettled([
        apiClient.get("/payments/fintech/gateways"),
        apiClient.get("/payments/fintech/admin/card2card/receipts"),
      ]);
      if (gwRes.status === "fulfilled") {
        setGateways(Array.isArray(gwRes.value.data) ? gwRes.value.data : []);
      }
      if (rcptRes.status === "fulfilled") {
        setReceipts(Array.isArray(rcptRes.value.data) ? rcptRes.value.data : []);
      }
    } catch {
      toast({ title: "خطا", description: "بارگذاری اطلاعات فین‌تک با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const reviewReceipt = async (receiptId: string, isApproved: boolean) => {
    try {
      await apiClient.post(`/payments/fintech/admin/card2card/receipts/${receiptId}/review`, {
        is_approved: isApproved,
      });
      toast({
        title: isApproved ? "تایید شد" : "رد شد",
        description: isApproved ? "فیش کارت‌به‌کارت تایید و سفارش فعال شد" : "فیش رد شد",
      });
      fetchData();
    } catch {
      toast({ title: "خطا", description: "بررسی فیش با خطا مواجه شد", variant: "destructive" });
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
          <RefreshCw className="h-4 w-4 mr-2" />
          بروزرسانی
        </Button>
      </div>

      {/* Tab Switch */}
      <div className="flex gap-2">
        <Button variant={tab === "gateways" ? "default" : "outline"} size="sm" onClick={() => setTab("gateways")}>
          <CreditCard className="h-4 w-4 mr-2" />
          درگاه‌های پرداخت ({gateways.length})
        </Button>
        <Button variant={tab === "receipts" ? "default" : "outline"} size="sm" onClick={() => setTab("receipts")}>
          <Receipt className="h-4 w-4 mr-2" />
          فیش‌های کارت‌به‌کارت ({receipts.length})
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : tab === "gateways" ? (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-right p-3 font-medium">درگاه</th>
                  <th className="text-right p-3 font-medium">کلید</th>
                  <th className="text-right p-3 font-medium">اولویت</th>
                  <th className="text-right p-3 font-medium">فعال</th>
                  <th className="text-right p-3 font-medium">پیش‌فرض</th>
                </tr>
              </thead>
              <tbody>
                {gateways.map((g) => (
                  <tr key={g.id} className="border-b hover:bg-muted/30">
                    <td className="p-3 font-medium">{g.title_fa}</td>
                    <td className="p-3 font-mono text-xs" dir="ltr">{g.provider_key}</td>
                    <td className="p-3 text-center">{g.priority}</td>
                    <td className="p-3">
                      <Badge className={g.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}>
                        {g.is_active ? "فعال" : "غیرفعال"}
                      </Badge>
                    </td>
                    <td className="p-3">
                      <Badge className={g.is_default ? "bg-blue-500/10 text-blue-500" : ""}>
                        {g.is_default ? "پیش‌فرض" : "-"}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card>
          {receipts.length === 0 ? (
            <p className="text-center p-12 text-muted-foreground text-sm">هیچ فیشی ثبت نشده است</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-muted/50">
                    <th className="text-right p-3 font-medium">شماره پیگیری</th>
                    <th className="text-right p-3 font-medium">مبلغ</th>
                    <th className="text-right p-3 font-medium">کارت مبدا</th>
                    <th className="text-right p-3 font-medium">وضعیت</th>
                    <th className="text-right p-3 font-medium">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  {receipts.map((r) => (
                    <tr key={r.id} className="border-b hover:bg-muted/30">
                      <td className="p-3 font-mono text-xs" dir="ltr">{r.tracking_code}</td>
                      <td className="p-3 text-xs">{r.amount.toLocaleString("fa-IR")} ریال</td>
                      <td className="p-3 font-mono text-xs" dir="ltr">****{r.source_card_last4}</td>
                      <td className="p-3">
                        <Badge className={statusColors[r.status]}>{statusLabels[r.status]}</Badge>
                      </td>
                      <td className="p-3">
                        {r.status === "pending_review" && (
                          <div className="flex gap-2">
                            <Button size="sm" variant="outline" className="text-emerald-600" onClick={() => reviewReceipt(r.id, true)}>
                              <CheckCircle2 className="h-4 w-4" />
                            </Button>
                            <Button size="sm" variant="outline" className="text-rose-600" onClick={() => reviewReceipt(r.id, false)}>
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
