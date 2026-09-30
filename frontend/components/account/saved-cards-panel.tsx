"use client";

import { useCallback, useEffect, useState } from "react";
import { CreditCard, Plus, ShieldCheck, Star, Trash2, AlertCircle, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits } from "@/lib/utils";
import { paymentsV1Api, type InstallmentPlan, type SavedPaymentMethod } from "@/lib/api/payments";

/** Providers whose gateway can actually store a card (see the backend
 *  capability contract: the public Zarinpal v4 / IDPay v1.1 APIs cannot). */
const TOKENIZABLE_PROVIDERS = [{ value: "mock", label: "درگاه آزمایشی (توسعه)" }];

const PLAN_STATUS_LABELS: Record<InstallmentPlan["status"], string> = {
  pending: "در انتظار پیش‌پرداخت",
  active: "در حال پرداخت",
  completed: "تکمیل شده",
  canceled: "لغو شده",
  defaulted: "معوق",
};

/** Persian label for a saved-card provider slug. */
function providerLabel(provider: string): string {
  const labels: Record<string, string> = {
    mock: "درگاه آزمایشی",
    zarinpal: "زرین‌پال",
    idpay: "آی‌دی‌پی",
    wallet: "کیف پول",
    card_transfer: "کارت به کارت",
    crypto: "ارز دیجیتال",
  };
  return labels[provider] ?? provider;
}

/**
 * Saved cards (tokenized) + installment plans for the account page.
 *
 * Only masked display metadata is ever shown: the gateway token stays on the
 * server, and no PAN or CVV exists anywhere in this flow — the customer enters
 * card details on the gateway's own page.
 */
export function SavedCardsPanel() {
  const { toast } = useToast();
  const [methods, setMethods] = useState<SavedPaymentMethod[]>([]);
  const [plans, setPlans] = useState<InstallmentPlan[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setIsLoading(true);
    setLoadError(null);
    try {
      const [savedMethods, installmentPlans] = await Promise.all([
        paymentsV1Api.listSavedMethods(true),
        paymentsV1Api.listInstallmentPlans().catch(() => [] as InstallmentPlan[]),
      ]);
      setMethods(savedMethods);
      setPlans(installmentPlans);
    } catch {
      // An empty list must never be shown as "you have no cards" when the
      // request actually failed — that reads as data loss to a customer.
      setLoadError("دریافت اطلاعات کارت‌ها با خطا مواجه شد.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleAddCard = async () => {
    const provider = TOKENIZABLE_PROVIDERS[0]?.value;
    if (!provider) return;
    setIsAdding(true);
    try {
      const result = await paymentsV1Api.tokenizeCard(provider);
      if (!result.success) {
        toast({
          variant: "destructive",
          title: "ثبت کارت ناموفق بود",
          description: result.error_message || "خطای درگاه پرداخت",
        });
        return;
      }
      if (result.requires_redirect && result.redirect_url) {
        // The gateway hosts the card-entry page; the PAN never reaches us.
        window.location.href = result.redirect_url;
        return;
      }
      toast({ title: "کارت با موفقیت ذخیره شد", description: "از این پس می‌توانید سریع‌تر پرداخت کنید." });
      await load();
    } catch {
      toast({
        variant: "destructive",
        title: "ثبت کارت ناموفق بود",
        description: "در حال حاضر امکان افزودن کارت وجود ندارد.",
      });
    } finally {
      setIsAdding(false);
    }
  };

  const handleSetDefault = async (methodId: string) => {
    setBusyId(methodId);
    try {
      await paymentsV1Api.setDefaultSavedMethod(methodId);
      toast({ title: "کارت پیش‌فرض تغییر کرد" });
      await load();
    } catch {
      toast({ variant: "destructive", title: "تغییر کارت پیش‌فرض ناموفق بود" });
    } finally {
      setBusyId(null);
    }
  };

  const handleDelete = async (methodId: string) => {
    setBusyId(methodId);
    try {
      await paymentsV1Api.deleteSavedMethod(methodId);
      toast({ title: "کارت حذف شد", description: "این کارت دیگر برای پرداخت قابل استفاده نیست." });
      await load();
    } catch {
      toast({ variant: "destructive", title: "حذف کارت ناموفق بود" });
    } finally {
      setBusyId(null);
    }
  };

  const activeMethods = methods.filter((m) => m.is_active);

  return (
    <div className="space-y-6">
      {/* Saved cards */}
      <Card className="p-6">
        <div className="mb-6 flex flex-col gap-3 border-b pb-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-semibold text-foreground">کارت‌های ذخیره‌شده</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              پرداخت سریع بدون وارد کردن مجدد اطلاعات کارت؛ اطلاعات کامل کارت هرگز در سایت ذخیره
              نمی‌شود.
            </p>
          </div>
          <Button onClick={handleAddCard} disabled={isAdding} size="sm" className="gap-1.5">
            {isAdding ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            <span>افزودن کارت</span>
          </Button>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>در حال بارگذاری...</span>
          </div>
        ) : loadError ? (
          <div className="flex flex-col items-center gap-2 py-10 text-sm text-destructive">
            <AlertCircle className="h-5 w-5" />
            <span>{loadError}</span>
            <Button variant="outline" size="sm" onClick={() => void load()}>
              تلاش مجدد
            </Button>
          </div>
        ) : activeMethods.length === 0 ? (
          <div className="flex flex-col items-center gap-3 py-12 text-center">
            <CreditCard className="h-10 w-10 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              هنوز کارتی ذخیره نکرده‌اید. با افزودن کارت، پرداخت‌های بعدی سریع‌تر انجام می‌شود.
            </p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {activeMethods.map((method) => (
              <div
                key={method.id}
                className={`relative rounded-xl border p-4 transition-colors ${
                  method.is_default ? "border-primary/50 bg-primary/5" : "border-border"
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg border bg-muted">
                      <CreditCard className="h-4 w-4 text-primary" />
                    </div>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-foreground" dir="ltr">
                        {method.masked_pan || `•••• •••• •••• ${method.last4 ?? "----"}`}
                      </p>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {providerLabel(method.provider)}
                        {method.bank_name ? ` — ${method.bank_name}` : ""}
                        {method.expiry_jalali
                          ? ` — انقضا ${toPersianDigits(method.expiry_jalali)}`
                          : ""}
                      </p>
                    </div>
                  </div>
                  {method.is_default && (
                    <Badge variant="outline" className="shrink-0 border-primary/30 bg-primary/10 text-primary">
                      پیش‌فرض
                    </Badge>
                  )}
                </div>

                <div className="mt-4 flex items-center gap-2">
                  {!method.is_default && (
                    <Button
                      variant="outline"
                      size="sm"
                      className="gap-1.5"
                      disabled={busyId === method.id}
                      onClick={() => void handleSetDefault(method.id)}
                    >
                      <Star className="h-3.5 w-3.5" />
                      <span>پیش‌فرض کن</span>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    className="gap-1.5 text-destructive hover:bg-destructive/10"
                    disabled={busyId === method.id}
                    onClick={() => void handleDelete(method.id)}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                    <span>حذف</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex items-start gap-2 rounded-lg border border-border/80 bg-muted/30 p-3 text-[11px] text-muted-foreground">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600" />
          <span>
            فقط شماره کارت ماسک‌شده و اطلاعات نمایشی ذخیره می‌شود. رمز دوم، CVV2 و شماره کامل کارت
            هرگز در سرورهای ما نگهداری نمی‌شود.
          </span>
        </div>
      </Card>

      {/* Installment plans */}
      <Card className="p-6">
        <div className="mb-6 border-b pb-4">
          <h2 className="text-lg font-semibold text-foreground">طرح‌های اقساطی</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            اقساط سفارش‌های خریداری‌شده به‌صورت اعتباری
          </p>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>در حال بارگذاری...</span>
          </div>
        ) : plans.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            در حال حاضر طرح اقساطی فعالی ندارید.
          </p>
        ) : (
          <div className="space-y-4">
            {plans.map((plan) => (
              <div key={plan.id} className="rounded-xl border border-border p-4">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div>
                    <p className="text-sm font-semibold text-foreground">
                      {toPersianDigits(plan.num_installments)} قسط —{" "}
                      {providerLabel(plan.provider)}
                    </p>
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      مبلغ کل: {toPersianDigits(plan.total_rial.toLocaleString("en-US"))} ریال —
                      پیش‌پرداخت:{" "}
                      {toPersianDigits(plan.first_installment_rial.toLocaleString("en-US"))} ریال
                    </p>
                  </div>
                  <Badge variant="outline" className="shrink-0">
                    {PLAN_STATUS_LABELS[plan.status]}
                  </Badge>
                </div>

                <div className="mt-3 divide-y divide-border/60 text-xs">
                  {plan.schedule.map((entry, index) => (
                    <div
                      key={`${plan.id}-${index}`}
                      className="flex items-center justify-between py-2"
                    >
                      <span className="flex items-center gap-2">
                        <span
                          className={
                            entry.status === "paid"
                              ? "h-2 w-2 rounded-full bg-emerald-500"
                              : "h-2 w-2 rounded-full bg-muted-foreground/40"
                          }
                        />
                        <span className="text-muted-foreground">
                          {entry.is_prepayment ? "پیش‌پرداخت" : "قسط"}{" "}
                          {toPersianDigits(index + 1)} — سررسید{" "}
                          {toPersianDigits(entry.due_date_jalali)}
                        </span>
                      </span>
                      <span
                        className={
                          entry.status === "paid"
                            ? "font-medium text-emerald-600"
                            : "font-medium text-foreground"
                        }
                      >
                        {toPersianDigits(entry.amount_rial.toLocaleString("en-US"))} ریال
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
