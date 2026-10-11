"use client";

import React, { useState } from "react";
import {
  Wallet as WalletIcon,
  RefreshCw,
  CheckCircle2,
  XCircle,
  Banknote,
  ArrowLeftRight,
  Settings2,
  SlidersHorizontal,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { PageLoader } from "@/components/shared/page-state";

const WITHDRAWALS_KEY = "admin-wallet-withdrawals" as const;
const WALLETS_KEY = "admin-wallet-wallets" as const;
const TRANSFERS_KEY = "admin-wallet-transfers" as const;
const SETTINGS_KEY = "admin-wallet-settings" as const;

interface Withdrawal {
  id: string;
  user_id: string;
  amount: number;
  status: "pending_review" | "approved" | "rejected" | "paid";
  iban: string | null;
  card_number: string | null;
  account_holder_name: string | null;
  admin_notes: string | null;
  payout_reference: string | null;
  reviewed_at: string | null;
  paid_at: string | null;
  created_at: string;
}

interface WalletRow {
  id: string;
  user_id: string;
  balance: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface Transfer {
  id: string;
  from_user_id: string;
  to_user_id: string;
  amount: number;
  fee: number;
  note: string | null;
  created_at: string;
}

interface LedgerTx {
  id: string;
  type: string;
  amount: number;
  balance_after: number;
  description: string | null;
  created_at: string;
}

const SWITCH_LABELS: Record<string, string> = {
  wallet_enabled: "فعال بودن ماژول کیف پول",
  wallet_deposit_enabled: "شارژ کیف پول از درگاه",
  wallet_withdraw_enabled: "درخواست برداشت",
  wallet_transfer_enabled: "انتقال بین کاربران",
  wallet_admin_adjust_enabled: "اصلاح موجودی توسط مدیر",
};

const STATUS_LABELS: Record<string, string> = {
  pending_review: "در انتظار بررسی",
  approved: "تأییدشده (در انتظار واریز)",
  rejected: "ردشده",
  paid: "پرداخت‌شده",
};

const STATUS_COLORS: Record<string, string> = {
  pending_review: "bg-amber-500/10 text-amber-600",
  approved: "bg-blue-500/10 text-blue-600",
  rejected: "bg-rose-500/10 text-rose-600",
  paid: "bg-emerald-500/10 text-emerald-600",
};

const fmtToman = (rial: number) => `${Math.trunc(rial / 10).toLocaleString("fa-IR")} تومان`;

export default function AdminWalletPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"withdrawals" | "wallets" | "transfers" | "settings">(
    "withdrawals",
  );

  // Independent queries so one outage does not blank the whole screen.
  const withdrawalsQuery = useAdminQuery({
    queryKey: [WITHDRAWALS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/admin/wallet/withdrawals");
      return (res.data?.items ?? []) as Withdrawal[];
    },
    fallbackError: "خطا در دریافت درخواست‌های برداشت",
  });
  const walletsQuery = useAdminQuery({
    queryKey: [WALLETS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/admin/wallet/wallets");
      return (res.data?.items ?? []) as WalletRow[];
    },
    fallbackError: "خطا در دریافت کیف پول‌ها",
  });
  const transfersQuery = useAdminQuery({
    queryKey: [TRANSFERS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/admin/wallet/transfers");
      return (res.data?.items ?? []) as Transfer[];
    },
    fallbackError: "خطا در دریافت انتقال‌ها",
  });
  const settingsQuery = useAdminQuery({
    queryKey: [SETTINGS_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/admin/wallet/settings");
      return (res.data ?? {}) as Record<string, boolean>;
    },
    fallbackError: "خطا در دریافت تنظیمات کیف پول",
  });

  const withdrawals = withdrawalsQuery.data ?? [];
  const wallets = walletsQuery.data ?? [];
  const transfers = transfersQuery.data ?? [];
  const switches = settingsQuery.data ?? {};
  const runMutation = useAdminMutation();

  // Withdrawal review dialog
  const [reviewTarget, setReviewTarget] = useState<Withdrawal | null>(null);
  const [reviewApprove, setReviewApprove] = useState(true);
  const [reviewNotes, setReviewNotes] = useState("");

  // Mark-paid dialog
  const [payTarget, setPayTarget] = useState<Withdrawal | null>(null);
  const [payoutRef, setPayoutRef] = useState("");

  // Ledger + adjust dialog
  const [ledgerTarget, setLedgerTarget] = useState<WalletRow | null>(null);
  const [ledger, setLedger] = useState<LedgerTx[]>([]);
  const [ledgerLoading, setLedgerLoading] = useState(false);
  const [adjustAmount, setAdjustAmount] = useState("");
  const [adjustReason, setAdjustReason] = useState("");

  const refreshAll = async () => {
    await Promise.all([
      withdrawalsQuery.reload(),
      walletsQuery.reload(),
      transfersQuery.reload(),
      settingsQuery.reload(),
    ]);
  };

  const openReview = (w: Withdrawal, approve: boolean) => {
    setReviewTarget(w);
    setReviewApprove(approve);
    setReviewNotes("");
  };

  const submitReview = async () => {
    if (!reviewTarget) return;
    const result = await runMutation(
      () =>
        apiClient.post(`/admin/wallet/withdrawals/${reviewTarget.id}/review`, {
          is_approved: reviewApprove,
          admin_notes: reviewNotes || null,
        }),
      { fallbackError: "بررسی درخواست برداشت ناموفق بود", invalidateKeys: [[WITHDRAWALS_KEY]] },
    );
    if (result.ok) {
      toast({
        title: reviewApprove ? "تأیید شد" : "رد شد",
        description: reviewApprove
          ? "درخواست تأیید شد. پس از واریز دستی، آن را «پرداخت‌شده» ثبت کنید."
          : "درخواست رد شد و مبلغ به کیف پول کاربر بازگشت.",
      });
      setReviewTarget(null);
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const submitMarkPaid = async () => {
    if (!payTarget || !payoutRef.trim()) return;
    const result = await runMutation(
      () =>
        apiClient.post(`/admin/wallet/withdrawals/${payTarget.id}/mark-paid`, {
          payout_reference: payoutRef.trim(),
        }),
      { fallbackError: "ثبت پرداخت ناموفق بود", invalidateKeys: [[WITHDRAWALS_KEY]] },
    );
    if (result.ok) {
      toast({ title: "ثبت شد", description: "واریز دستی با موفقیت ثبت شد." });
      setPayTarget(null);
      setPayoutRef("");
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const openLedger = async (w: WalletRow) => {
    setLedgerTarget(w);
    setLedger([]);
    setAdjustAmount("");
    setAdjustReason("");
    setLedgerLoading(true);
    try {
      const res = await apiClient.get(`/admin/wallet/wallets/${w.user_id}/ledger`);
      setLedger((res.data?.items ?? []) as LedgerTx[]);
    } catch {
      setLedger([]);
    } finally {
      setLedgerLoading(false);
    }
  };

  const submitAdjust = async () => {
    if (!ledgerTarget) return;
    const toman = parseInt(adjustAmount.replace(/[^\d-]/g, ""), 10);
    if (!toman || !adjustReason.trim()) {
      toast({ title: "اطلاعات ناقص", description: "مبلغ و دلیل اصلاح را وارد کنید.", variant: "destructive" });
      return;
    }
    const result = await runMutation(
      () =>
        apiClient.post(`/admin/wallet/wallets/${ledgerTarget.user_id}/adjust`, {
          amount: toman * 10, // Toman → Rial
          reason: adjustReason.trim(),
        }),
      { fallbackError: "اصلاح موجودی ناموفق بود", invalidateKeys: [[WALLETS_KEY]] },
    );
    if (result.ok) {
      toast({ title: "انجام شد", description: "موجودی کیف پول اصلاح شد." });
      await openLedger(ledgerTarget);
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const toggleSwitch = async (key: string, value: boolean) => {
    const result = await runMutation(
      () => apiClient.put(`/admin/wallet/settings/${key}`, null, { params: { enabled: value } }),
      { fallbackError: "تغییر تنظیمات ناموفق بود", invalidateKeys: [[SETTINGS_KEY]] },
    );
    if (result.ok) {
      toast({ title: "ذخیره شد", description: "تنظیمات کیف پول به‌روزرسانی شد." });
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const withdrawalColumns: DataTableColumn<Withdrawal>[] = [
    {
      key: "amount",
      header: "مبلغ",
      render: (w) => <span className="font-semibold">{fmtToman(w.amount)}</span>,
    },
    {
      key: "destination",
      header: "مقصد",
      className: "font-mono text-xs",
      render: (w) => (
        <span dir="ltr">{w.iban || w.card_number || "-"}</span>
      ),
    },
    { key: "holder", header: "صاحب حساب", render: (w) => w.account_holder_name || "-" },
    {
      key: "status",
      header: "وضعیت",
      render: (w) => (
        <Badge className={STATUS_COLORS[w.status]}>{STATUS_LABELS[w.status] ?? w.status}</Badge>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      render: (w) => {
        if (w.status === "pending_review") {
          return (
            <div className="flex gap-2">
              <Button size="sm" variant="outline" className="text-emerald-600" aria-label="تأیید" onClick={() => openReview(w, true)}>
                <CheckCircle2 className="h-4 w-4" />
              </Button>
              <Button size="sm" variant="outline" className="text-rose-600" aria-label="رد" onClick={() => openReview(w, false)}>
                <XCircle className="h-4 w-4" />
              </Button>
            </div>
          );
        }
        if (w.status === "approved") {
          return (
            <Button size="sm" variant="outline" className="text-blue-600 gap-1" onClick={() => { setPayTarget(w); setPayoutRef(""); }}>
              <Banknote className="h-4 w-4" />
              ثبت واریز
            </Button>
          );
        }
        return null;
      },
    },
  ];

  const walletColumns: DataTableColumn<WalletRow>[] = [
    {
      key: "user",
      header: "شناسه کاربر",
      className: "font-mono text-xs",
      render: (w) => <span dir="ltr">{w.user_id.slice(0, 8)}…</span>,
    },
    {
      key: "balance",
      header: "موجودی",
      render: (w) => <span className="font-semibold">{fmtToman(w.balance)}</span>,
    },
    {
      key: "active",
      header: "وضعیت",
      render: (w) => (
        <Badge className={w.is_active ? "bg-emerald-500/10 text-emerald-600" : "bg-neutral-500/10 text-neutral-500"}>
          {w.is_active ? "فعال" : "غیرفعال"}
        </Badge>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      render: (w) => (
        <Button size="sm" variant="outline" className="gap-1" onClick={() => openLedger(w)}>
          <SlidersHorizontal className="h-4 w-4" />
          دفتر کل / اصلاح
        </Button>
      ),
    },
  ];

  const transferColumns: DataTableColumn<Transfer>[] = [
    { key: "from", header: "از", className: "font-mono text-xs", render: (t) => <span dir="ltr">{t.from_user_id.slice(0, 8)}…</span> },
    { key: "to", header: "به", className: "font-mono text-xs", render: (t) => <span dir="ltr">{t.to_user_id.slice(0, 8)}…</span> },
    { key: "amount", header: "مبلغ", render: (t) => <span className="font-semibold">{fmtToman(t.amount)}</span> },
    { key: "note", header: "توضیح", render: (t) => t.note || "-" },
    {
      key: "date",
      header: "تاریخ",
      render: (t) => new Date(t.created_at).toLocaleDateString("fa-IR"),
    },
  ];

  const loading =
    withdrawalsQuery.loading || walletsQuery.loading || transfersQuery.loading || settingsQuery.loading;

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <WalletIcon className="h-5 w-5 text-primary" />
            کیف پول‌ها
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            بررسی درخواست‌های برداشت، مشاهده و اصلاح موجودی، انتقال‌ها و تنظیمات ماژول کیف پول
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={refreshAll}>
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant={tab === "withdrawals" ? "default" : "outline"} size="sm" onClick={() => setTab("withdrawals")}>
          <Banknote className="h-4 w-4 ms-2" />
          برداشت‌ها ({withdrawals.length})
        </Button>
        <Button variant={tab === "wallets" ? "default" : "outline"} size="sm" onClick={() => setTab("wallets")}>
          <WalletIcon className="h-4 w-4 ms-2" />
          کیف پول‌ها ({wallets.length})
        </Button>
        <Button variant={tab === "transfers" ? "default" : "outline"} size="sm" onClick={() => setTab("transfers")}>
          <ArrowLeftRight className="h-4 w-4 ms-2" />
          انتقال‌ها ({transfers.length})
        </Button>
        <Button variant={tab === "settings" ? "default" : "outline"} size="sm" onClick={() => setTab("settings")}>
          <Settings2 className="h-4 w-4 ms-2" />
          تنظیمات
        </Button>
      </div>

      {loading ? (
        <PageLoader message="در حال دریافت اطلاعات کیف پول..." className="min-h-0 p-12" />
      ) : tab === "withdrawals" ? (
        <DataTable<Withdrawal>
          columns={withdrawalColumns}
          rows={withdrawals}
          rowKey={(w) => w.id}
          error={withdrawalsQuery.error ? "خطا در دریافت درخواست‌های برداشت" : null}
          emptyMessage="هیچ درخواست برداشتی ثبت نشده است."
        />
      ) : tab === "wallets" ? (
        <DataTable<WalletRow>
          columns={walletColumns}
          rows={wallets}
          rowKey={(w) => w.id}
          error={walletsQuery.error ? "خطا در دریافت کیف پول‌ها" : null}
          emptyMessage="هیچ کیف پولی یافت نشد."
        />
      ) : tab === "transfers" ? (
        <DataTable<Transfer>
          columns={transferColumns}
          rows={transfers}
          rowKey={(t) => t.id}
          error={transfersQuery.error ? "خطا در دریافت انتقال‌ها" : null}
          emptyMessage="هیچ انتقالی ثبت نشده است."
        />
      ) : (
        <Card className="p-6 space-y-4">
          <div>
            <h3 className="font-semibold">فعال/غیرفعال کردن بخش‌های کیف پول</h3>
            <p className="text-xs text-muted-foreground mt-1">
              هر بخش به‌صورت مستقل قابل خاموش کردن است؛ تغییر بلافاصله اعمال می‌شود.
            </p>
          </div>
          {Object.entries(SWITCH_LABELS).map(([key, label]) => (
            <div key={key} className="flex items-center justify-between rounded-lg border p-3.5">
              <div className="font-medium text-sm">{label}</div>
              <Switch
                checked={Boolean(switches[key])}
                onCheckedChange={(v) => toggleSwitch(key, v)}
                aria-label={label}
              />
            </div>
          ))}
        </Card>
      )}

      {/* Review dialog */}
      <Dialog open={reviewTarget !== null} onOpenChange={(o) => !o && setReviewTarget(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{reviewApprove ? "تأیید درخواست برداشت" : "رد درخواست برداشت"}</DialogTitle>
            <DialogDescription>
              {reviewApprove
                ? "با تأیید، درخواست آماده واریز دستی می‌شود (مبلغ از قبل بلوکه شده است)."
                : "با رد، مبلغ بلوکه‌شده به کیف پول کاربر بازمی‌گردد."}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="reviewNotes">یادداشت (اختیاری)</Label>
            <Input id="reviewNotes" value={reviewNotes} onChange={(e) => setReviewNotes(e.target.value)} />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setReviewTarget(null)}>انصراف</Button>
            <Button onClick={submitReview}>{reviewApprove ? "تأیید" : "رد"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Mark-paid dialog */}
      <Dialog open={payTarget !== null} onOpenChange={(o) => !o && setPayTarget(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>ثبت واریز دستی</DialogTitle>
            <DialogDescription>
              شماره پیگیری/مرجع واریز بانکی را وارد کنید. (این مرحله فقط ثبت است؛ مبلغ قبلاً از کیف پول کسر شده.)
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 py-2">
            <Label htmlFor="payoutRef">شماره پیگیری واریز</Label>
            <Input id="payoutRef" value={payoutRef} onChange={(e) => setPayoutRef(e.target.value)} dir="ltr" className="font-mono" />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setPayTarget(null)}>انصراف</Button>
            <Button onClick={submitMarkPaid}>ثبت</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Ledger + adjust dialog */}
      <Dialog open={ledgerTarget !== null} onOpenChange={(o) => !o && setLedgerTarget(null)}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>دفتر کل و اصلاح موجودی</DialogTitle>
            <DialogDescription>
              {ledgerTarget ? `کاربر: ${ledgerTarget.user_id}` : ""}
            </DialogDescription>
          </DialogHeader>
          <div className="max-h-64 overflow-auto rounded-lg border">
            {ledgerLoading ? (
              <div className="p-6 text-center text-sm text-muted-foreground">در حال دریافت…</div>
            ) : ledger.length === 0 ? (
              <div className="p-6 text-center text-sm text-muted-foreground">تراکنشی وجود ندارد.</div>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="p-2 text-right">تاریخ</th>
                    <th className="p-2 text-right">شرح</th>
                    <th className="p-2 text-right">مبلغ</th>
                    <th className="p-2 text-right">مانده</th>
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {ledger.map((t) => (
                    <tr key={t.id}>
                      <td className="p-2 text-xs">{new Date(t.created_at).toLocaleDateString("fa-IR")}</td>
                      <td className="p-2 text-xs">{t.description || t.type}</td>
                      <td className={`p-2 font-mono text-xs ${t.amount >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                        {t.amount >= 0 ? "+" : ""}
                        {fmtToman(t.amount)}
                      </td>
                      <td className="p-2 font-mono text-xs">{fmtToman(t.balance_after)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
          <div className="space-y-3 border-t pt-4">
            <h4 className="font-semibold text-sm">اصلاح موجودی</h4>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="adjustAmount">مبلغ (تومان، منفی = کسر)</Label>
                <Input id="adjustAmount" value={adjustAmount} onChange={(e) => setAdjustAmount(e.target.value)} dir="ltr" className="font-mono" placeholder="مثلاً: 50000 یا -50000" />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="adjustReason">دلیل</Label>
                <Input id="adjustReason" value={adjustReason} onChange={(e) => setAdjustReason(e.target.value)} />
              </div>
            </div>
            <Button onClick={submitAdjust} className="w-full">ثبت اصلاح</Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
