"use client";

import React, { useEffect, useState } from "react";
import {
  Settings,
  Store,
  CreditCard,
  Truck,
  FileText,
  Save,
  CheckCircle2,
  Bell,
  Lock,
  ShieldCheck,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api/client";

const ZARINPAL_MERCHANT_KEY = "payment.zarinpal.merchant_id";

export default function AdminSettingsPage() {
  const [saved, setSaved] = useState(false);

  // Form State
  const [storeName, setStoreName] = useState("فروشگاه اینترنتی آنلاین");
  const [supportPhone, setSupportPhone] = useState("021-88889999");
  const [supportEmail, setSupportEmail] = useState("support@site.com");
  const [taxRate, setTaxRate] = useState("10");
  const [freeShippingThreshold, setFreeShippingThreshold] = useState("10000000"); // 1M Toman (10M Rial)
  const [defaultShippingFee, setDefaultShippingFee] = useState("500000"); // 50K Toman
  const [zarinpalEnabled, setZarinpalEnabled] = useState(true);
  const [c2cEnabled, setC2cEnabled] = useState(true);
  const [walletEnabled, setWalletEnabled] = useState(true);
  const [cryptoEnabled, setCryptoEnabled] = useState(true);

  // Zarinpal merchant code (persisted via admin settings API)
  const [merchantCode, setMerchantCode] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [merchantLoading, setMerchantLoading] = useState(true);
  const [merchantSaving, setMerchantSaving] = useState(false);
  const [merchantStatus, setMerchantStatus] = useState<
    { ok: boolean; text: string } | null
  >(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiClient.get(`/settings/${ZARINPAL_MERCHANT_KEY}`);
        if (cancelled) return;
        const raw = res.data?.value;
        const code =
          typeof raw === "object" && raw !== null
            ? (raw.merchant_id as string) ?? ""
            : (raw as string) ?? "";
        setMerchantCode(code);
      } catch {
        // Setting not created yet — empty state
      } finally {
        if (!cancelled) setMerchantLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleSaveMerchant = async () => {
    const code = merchantCode.trim();
    setMerchantSaving(true);
    setMerchantStatus(null);
    try {
      const value = { merchant_id: code };
      try {
        await apiClient.patch(`/settings/${ZARINPAL_MERCHANT_KEY}`, { value });
      } catch (err) {
        const status = (err as { response?: { status?: number } })?.response?.status;
        if (status === 404) {
          await apiClient.post("/settings", {
            key: ZARINPAL_MERCHANT_KEY,
            value,
            group: "payment",
            description: "Zarinpal merchant id (GUID) — activates the Zarinpal gateway when set",
            is_public: false,
          });
        } else {
          throw err;
        }
      }
      setMerchantStatus({
        ok: true,
        text: code
          ? "ذخیره شد — درگاه زرین‌پال برای پرداخت‌های جدید فعال است."
          : "ذخیره شد — بدون مرچنت‌کد، پرداخت‌ها با کارت به کارت انجام می‌شود.",
      });
    } catch {
      setMerchantStatus({
        ok: false,
        text: "ذخیره نشد. دسترسی ادمین (settings:write) را بررسی کنید.",
      });
    } finally {
      setMerchantSaving(false);
    }
  };

  const SETTINGS_KEYS = {
    store: "store.identity",
    support: "store.support",
    shippingTax: "store.shipping_tax",
    paymentFlags: "store.payment_flags",
  } as const;

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setSaveError(null);
    try {
      const groups: Array<[string, Record<string, unknown>]> = [
        [SETTINGS_KEYS.store, { store_name: storeName }],
        [SETTINGS_KEYS.support, { support_phone: supportPhone, support_email: supportEmail }],
        [
          SETTINGS_KEYS.shippingTax,
          {
            tax_rate_percent: taxRate,
            free_shipping_threshold_rials: freeShippingThreshold,
            default_shipping_fee_rials: defaultShippingFee,
          },
        ],
        [
          SETTINGS_KEYS.paymentFlags,
          {
            zarinpal_enabled: zarinpalEnabled,
            card_to_card_enabled: c2cEnabled,
            wallet_enabled: walletEnabled,
            crypto_enabled: cryptoEnabled,
          },
        ],
      ];
      for (const [key, value] of groups) {
        try {
          await apiClient.patch(`/settings/${key}`, { value });
        } catch (err: unknown) {
          const status = (err as { status?: number })?.status;
          if (status === 404) {
            // key does not exist yet — create it
            await apiClient.post("/settings", { key, value, is_public: false });
          } else {
            throw err;
          }
        }
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err: unknown) {
      setSaveError(
        (err as { message?: string })?.message ||
          "ذخیره تنظیمات با خطا مواجه شد. لطفاً دوباره تلاش کنید."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">تنظیمات کلی فروشگاه</h1>
          <p className="text-sm text-muted-foreground">
            پیکربندی هویت تجاری، درگاه‌های پرداخت، مالیات و هزینه‌های ارسال
          </p>
        </div>
      </div>

      {saveError && (
        <div className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/10 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4" /> {saveError}
        </div>
      )}

      {saved && (
        <div className="flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-3 text-sm text-emerald-600">
          <CheckCircle2 className="h-4 w-4" /> تنظیمات با موفقیت ذخیره شدند.
        </div>
      )}

      <form onSubmit={handleSave} className="space-y-6">
        {/* General Store Identity */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <Store className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">مشخصات عمومی فروشگاه</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>نام فروشگاه</Label>
              <Input
                value={storeName}
                onChange={(e) => setStoreName(e.target.value)}
                placeholder="عنوان برند فروشگاه"
              />
            </div>
            <div className="space-y-2">
              <Label>شماره تماس پشتیبانی مشتریان</Label>
              <Input
                value={supportPhone}
                onChange={(e) => setSupportPhone(e.target.value)}
                placeholder="۰۲۱-۸۸۸۸۹۹۹۹"
              />
            </div>
            <div className="space-y-2">
              <Label>ایمیل ارتباط با ما</Label>
              <Input
                value={supportEmail}
                onChange={(e) => setSupportEmail(e.target.value)}
                placeholder="info@site.com"
              />
            </div>
            <div className="space-y-2">
              <Label>واحد پول رسمی سیستم</Label>
              <Input value="ریال ایران (نمایش در فرانت: تومان)" disabled className="bg-muted" />
            </div>
          </div>
        </Card>

        {/* Financial & Tax Settings */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <FileText className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">مالیات و حمل و نقل</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>نرخ مالیات بر ارزش افزوده (درصد)</Label>
              <Input
                type="number"
                value={taxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                placeholder="10"
              />
              <p className="text-xs text-muted-foreground">طبق قانون مالیات بر ارزش افزوده ایران (۱۰٪)</p>
            </div>
            <div className="space-y-2">
              <Label>حداقل سفارش برای ارسال رایگان (ریال)</Label>
              <Input
                value={freeShippingThreshold}
                onChange={(e) => setFreeShippingThreshold(e.target.value)}
                placeholder="10000000"
              />
              <p className="text-xs text-muted-foreground">معادل ۱٬۰۰۰٬۰۰۰ تومان</p>
            </div>
            <div className="space-y-2">
              <Label>هزینه پیش‌فرض ارسال عادی (ریال)</Label>
              <Input
                value={defaultShippingFee}
                onChange={(e) => setDefaultShippingFee(e.target.value)}
                placeholder="500000"
              />
              <p className="text-xs text-muted-foreground">معادل ۵۰٬۰۰۰ تومان</p>
            </div>
          </div>
        </Card>

        {/* Payment Methods Toggle */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <CreditCard className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">روش‌های پرداخت فعال برای مشتریان</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="rounded-lg border border-border p-3.5 sm:col-span-2">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium text-foreground">
                    درگاه بانکی زرین‌پال (شاپرک)
                    {merchantCode ? (
                      <Badge className="ms-2 bg-success/15 text-success border border-success/25">
                        فعال
                      </Badge>
                    ) : (
                      <Badge variant="secondary" className="ms-2">
                        بدون مرچنت‌کد — کارت به کارت جایگزین است
                      </Badge>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground">
                    مرچنت‌کد (GUID ۳۶ کاراکتری) را از پنل زرین‌پال بگیرید؛ به‌محض
                    ذخیره، پرداخت‌های جدید از طریق زرین‌پال انجام می‌شود.
                  </div>
                </div>
              </div>

              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <Input
                  dir="ltr"
                  value={merchantCode}
                  onChange={(e) => setMerchantCode(e.target.value)}
                  placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
                  className="font-mono text-xs"
                  aria-label="مرچنت کد زرین‌پال"
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={handleSaveMerchant}
                  disabled={merchantSaving || merchantLoading}
                  className="gap-1.5 rounded-xl font-bold"
                >
                  {merchantSaving ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Save className="h-4 w-4" />
                  )}
                  ذخیره مرچنت‌کد
                </Button>
              </div>

              {merchantStatus && (
                <p
                  className={`mt-2 flex items-center gap-1.5 text-xs ${
                    merchantStatus.ok ? "text-success" : "text-destructive"
                  }`}
                >
                  {merchantStatus.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {merchantStatus.text}
                </p>
              )}
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">کارت به کارت با بارگذاری فیش</div>
                <div className="text-xs text-muted-foreground">نیاز به تایید دستی مدیریت در پنل</div>
              </div>
              <input
                type="checkbox"
                checked={c2cEnabled}
                onChange={(e) => setC2cEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">پرداخت با کیف پول داخلی</div>
                <div className="text-xs text-muted-foreground">کسر آنی از موجودی حساب کاربر</div>
              </div>
              <input
                type="checkbox"
                checked={walletEnabled}
                onChange={(e) => setWalletEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">درگاه ارزی و رمزارز (NowPayments)</div>
                <div className="text-xs text-muted-foreground">پذیرش تتر (USDT)، بیت‌کوین و اتریوم</div>
              </div>
              <input
                type="checkbox"
                checked={cryptoEnabled}
                onChange={(e) => setCryptoEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>
          </div>
        </Card>

        {/* Platform Security & Defense Posture */}
        <Card className="p-6 border-emerald-500/20 bg-emerald-500/5">
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-emerald-500" />
              <h2 className="text-base font-bold text-foreground">وضعیت سپرهای دفاعی و امنیت پلتفرم (Active Defenses)</h2>
            </div>
            <Badge variant="outline" className="border-emerald-500/30 text-emerald-600 bg-emerald-500/10">
              محیط امن - ۸ لایه دفاعی فعال
            </Badge>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">محدودسازی نرخ (Rate Limiting)</div>
              <div className="mt-1 font-bold text-sm text-foreground">SlowAPI + Redis</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">۱۰ req/min فعال</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">مقابله با Brute Force</div>
              <div className="mt-1 font-bold text-sm text-foreground">Multi-Key Lockout</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">۵ تلاش / ۱۵ دقیقه قفل</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">تاخیر تصاعدی هوشمند</div>
              <div className="mt-1 font-bold text-sm text-foreground">OWASP Progressive Delay</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">کندسازی ربات‌های کرکر</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">کنترل دسترسی سازمانی</div>
              <div className="mt-1 font-bold text-sm text-foreground">Casbin RBAC/ABAC</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">پالیسی‌های دقیق نقش‌ها</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">ورود بیومتریک و دومرحله‌ای</div>
              <div className="mt-1 font-bold text-sm text-foreground">FIDO2 Passkeys + TOTP</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">Google Auth + بیومتریک</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">دیواره آتش ضدبات (WAF)</div>
              <div className="mt-1 font-bold text-sm text-foreground">Nginx + Honeypot</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">مسدودسازی SQLMap/Nikto</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">فیلتر و مسدودسازی آنی IP</div>
              <div className="mt-1 font-bold text-sm text-foreground">Redis Dynamic Blacklist</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">بلاک زیر ۱ میلی‌ثانیه</div>
            </div>

            <div className="rounded-lg border border-border/60 bg-background/80 p-3 shadow-sm">
              <div className="text-xs text-muted-foreground">رمزنگاری و مقابله با XSS</div>
              <div className="mt-1 font-bold text-sm text-foreground">Argon2id + DOMPurify</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">استاندارد عالی رمزنگاری</div>
            </div>
          </div>
        </Card>

        {/* Submit */}
        <div className="flex justify-end">
          <Button type="submit" disabled={saving} className="gap-2 px-8">
            <Save className="h-4 w-4" /> ذخیره تنظیمات
          </Button>
        </div>
      </form>
    </div>
  );
}
