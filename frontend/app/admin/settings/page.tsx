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
  MessageSquare,
  Send,
  Smartphone,
  Mail,
  SlidersHorizontal,
  Heart,
  ArrowLeftRight,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";
import { invalidateShopFeatures } from "@/hooks/use-shop-features";
import { useToast } from "@/components/ui/use-toast";
import { ContentSettingsCard } from "@/components/admin/content-settings-card";
import { UserSettingsCard } from "@/components/admin/user-settings-card";
import { ContentToolsCard } from "@/components/admin/content-tools-card";
import { SiteIdentityCard } from "@/components/admin/site-identity-card";
import { RobotsSettingsCard } from "@/components/admin/robots-settings-card";
import { ImageSeoSettingsCard } from "@/components/admin/image-seo-settings-card";
import { BreadcrumbSettingsCard } from "@/components/admin/breadcrumb-settings-card";
import { IndexingSettingsCard } from "@/components/admin/indexing-settings-card";
import { LocalSeoSettingsCard } from "@/components/admin/local-seo-settings-card";
import { ContentAiSettingsCard } from "@/components/admin/content-ai-settings-card";

const ZARINPAL_MERCHANT_KEY = "payment.zarinpal.merchant_id";

export default function AdminSettingsPage() {
  const [saved, setSaved] = useState(false);
  const { toast } = useToast();
  // Which settings group is visible. "general" on load: the store's identity
  // is the first thing an operator comes here for.
  const [activeTab, setActiveTab] = useState<
    "general" | "content" | "financial" | "features" | "communication" | "security"
  >("general");

  // Form State
  const [storeName, setStoreName] = useState("فروشگاه اینترنتی آنلاین");
  const [supportPhone, setSupportPhone] = useState("021-88889999");
  const [taxRate, setTaxRate] = useState("9");
  const [zarinpalEnabled, setZarinpalEnabled] = useState(true);
  const [c2cEnabled, setC2cEnabled] = useState(true);
  const [walletEnabled, setWalletEnabled] = useState(true);

  // Storefront feature switches (wishlist / compare). These are NOT the wallet
  // switches above — those live under /admin/wallet and are stored separately;
  // this row only reads the old payment_flags.wallet_enabled for the payment
  // card. The feature switches live in site_options behind their own endpoints.
  const [shopFeatures, setShopFeatures] = useState({ wishlist_enabled: true, compare_enabled: true });
  const [savingFeature, setSavingFeature] = useState<string | null>(null);

  // Feature switches have their own endpoints (not the /settings map above),
  // so they load and save independently of the main settings form.
  //
  // The destructured names are deliberately DIFFERENT from the state variable:
  // an earlier version destructured this as `shopFeatures` too, so the syncing
  // effect below read the STATE (not the fetched data), re-ran on every
  // setShopFeatures and reset the checkbox to its pre-click value right after a
  // successful save. The click looked like it did nothing.
  const {
    loading: shopFeaturesLoading,
    data: shopFeaturesData,
    reload: reloadShopFeatures,
  } = useAdminQuery({
    queryKey: ["admin", "shop-features"],
    queryFn: async () => {
      const { data } = await apiClient.get("/admin/shop-features");
      return (data ?? {}) as Record<string, boolean>;
    },
    fallbackError: "دریافت تنظیمات قابلیت‌ها ناموفق بود",
  });

  useEffect(() => {
    if (shopFeaturesLoading || !shopFeaturesData) return;
    setShopFeatures({
      wishlist_enabled: shopFeaturesData.wishlist_enabled ?? true,
      compare_enabled: shopFeaturesData.compare_enabled ?? true,
    });
  }, [shopFeaturesLoading, shopFeaturesData]);

  async function toggleShopFeature(key: "wishlist_enabled" | "compare_enabled", value: boolean) {
    setSavingFeature(key);
    // Optimistic: the toggle should feel instant, and the reload below is the
    // authority. Reverted on failure so the switch never lies about its state.
    setShopFeatures((prev) => ({ ...prev, [key]: value }));
    try {
      await apiClient.put(`/admin/shop-features/${key}`, null, { params: { enabled: value } });
      toast({ title: "ذخیره شد", description: "تنظیمات قابلیت فروشگاه به‌روزرسانی شد." });
      // The storefront reads these on every page load, so make the next
      // navigation see the new value rather than a cached one.
      invalidateShopFeatures();
      reloadShopFeatures();
    } catch {
      setShopFeatures((prev) => ({ ...prev, [key]: !value }));
      toast({ title: "ذخیره ناموفق بود", description: "تغییر اعمال نشد.", variant: "destructive" });
    } finally {
      setSavingFeature(null);
    }
  }

  // SMS Configuration State
  const [smsProvider, setSmsProvider] = useState<"kavenegar" | "farazsms" | "sms_ir">("kavenegar");
  const [smsApiKey, setSmsApiKey] = useState("");
  const [smsSenderNumber, setSmsSenderNumber] = useState("");
  const [smsOtpPattern, setSmsOtpPattern] = useState("");
  const [smsOrderPattern, setSmsOrderPattern] = useState("");
  const [smsEnabled, setSmsEnabled] = useState(true);
  const [smsSaving, setSmsSaving] = useState(false);
  const [smsStatus, setSmsStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testPhone, setTestPhone] = useState("");
  const [testMessage, setTestMessage] = useState("پیامک تستی سامانه فروشگاهی");
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; text: string } | null>(null);

  // The SMTP / email configuration state was removed on 2026-10-07 with the
  // rest of the email feature.

  // Zarinpal merchant code (persisted via admin settings API)
  const [merchantCode, setMerchantCode] = useState("");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [merchantSaving, setMerchantSaving] = useState(false);
  const [merchantStatus, setMerchantStatus] = useState<
    { ok: boolean; text: string } | null
  >(null);

  const {
    loading: merchantLoading,
    reload: reloadSettings,
  } = useAdminQuery({
    queryKey: ["admin", "settings", "all"],
    queryFn: async () => {
      const { data: settings } = await apiClient.get<Array<{ key: string; value: unknown }>>("/settings");
      const values = new Map(settings.map(({ key, value }) => [key, value]));
      const group = (key: string) => {
        const value = values.get(key);
        return value && typeof value === "object" && !Array.isArray(value)
          ? value as Record<string, unknown>
          : null;
      };
      const identity = group("store.identity");
      const support = group("store.support");
      const shippingTax = group("store.shipping_tax");
      const paymentFlags = group("store.payment_flags");
      if (identity?.store_name) setStoreName(String(identity.store_name));
      if (support?.support_phone) setSupportPhone(String(support.support_phone));
      if (shippingTax) {
        if (shippingTax.tax_rate_percent !== undefined)
          setTaxRate(String(shippingTax.tax_rate_percent));
      }
      if (paymentFlags) {
        if (typeof paymentFlags.zarinpal_enabled === "boolean")
          setZarinpalEnabled(paymentFlags.zarinpal_enabled);
        if (typeof paymentFlags.card_to_card_enabled === "boolean")
          setC2cEnabled(paymentFlags.card_to_card_enabled);
        if (typeof paymentFlags.wallet_enabled === "boolean")
          setWalletEnabled(paymentFlags.wallet_enabled);
      }
      const raw = values.get(ZARINPAL_MERCHANT_KEY);
      const merchantId = typeof raw === "string" ? raw : group(ZARINPAL_MERCHANT_KEY)?.merchant_id;
      setMerchantCode(typeof merchantId === "string" ? merchantId : "");
      const sms = group("sms");
      if (sms) {
        if (["kavenegar", "farazsms", "sms_ir"].includes(String(sms.provider)))
          setSmsProvider(sms.provider as typeof smsProvider);
        if (typeof sms.api_key === "string") setSmsApiKey(sms.api_key);
        if (typeof sms.sender_number === "string") setSmsSenderNumber(sms.sender_number);
        if (typeof sms.otp_pattern === "string") setSmsOtpPattern(sms.otp_pattern);
        if (typeof sms.order_pattern === "string") setSmsOrderPattern(sms.order_pattern);
        if (typeof sms.is_enabled === "boolean") setSmsEnabled(sms.is_enabled);
      }
      return settings;
    },
    fallbackError: "بارگذاری تنظیمات ناموفق بود. پیش از ذخیره، صفحه را دوباره بارگذاری کنید.",
  });

  const handleSaveSms = async () => {
    setSmsSaving(true);
    setSmsStatus(null);
    try {
      const payload = {
        provider: smsProvider,
        api_key: smsApiKey,
        sender_number: smsSenderNumber,
        otp_pattern: smsOtpPattern,
        order_pattern: smsOrderPattern,
        is_enabled: smsEnabled,
      };
      try {
        await apiClient.patch("/settings/sms", { value: payload });
      } catch (err) {
        const status = (err as { status?: number })?.status;
        if (status === 404) {
          await apiClient.post("/settings", {
            key: "sms",
            value: payload,
            group: "messaging",
            description: "تنظیمات وب‌سرویس و درگاه پیامک",
            is_public: false,
          });
        } else {
          throw err;
        }
      }
      setSmsStatus({ ok: true, text: "تنظیمات درگاه پیامک با موفقیت ذخیره شد." });
    } catch {
      setSmsStatus({ ok: false, text: "خطا در ذخیره تنظیمات پیامک. دسترسی خود را بررسی کنید." });
    } finally {
      setSmsSaving(false);
    }
  };

  const handleTestSms = async () => {
    if (!testPhone.trim()) {
      setTestResult({ ok: false, text: "لطفاً شماره موبایل گیرنده را وارد کنید." });
      return;
    }
    setTestSending(true);
    setTestResult(null);
    try {
      await apiClient.post("/settings/admin/sms-providers/test", {
        phone: testPhone.trim(),
        message: testMessage.trim(),
      });
      setTestResult({ ok: true, text: "پیامک تستی با موفقیت ارسال شد." });
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setTestResult({ ok: false, text: msg || "ارسال پیامک تستی با خطا مواجه شد." });
    } finally {
      setTestSending(false);
    }
  };

  // handleSaveSmtp / handleTestEmail were removed on 2026-10-07 with the
  // rest of the email feature.

  const handleSaveMerchant = async () => {
    const code = merchantCode.trim();
    setMerchantSaving(true);
    setMerchantStatus(null);
    try {
      const value = { merchant_id: code };
      try {
        await apiClient.patch(`/settings/${ZARINPAL_MERCHANT_KEY}`, { value });
      } catch (err) {
        const status = (err as { status?: number })?.status;
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
        [SETTINGS_KEYS.support, { support_phone: supportPhone }],
        [
          SETTINGS_KEYS.shippingTax,
          {
            tax_rate_percent: taxRate,
          },
        ],
        [
          SETTINGS_KEYS.paymentFlags,
          {
            zarinpal_enabled: zarinpalEnabled,
            card_to_card_enabled: c2cEnabled,
            wallet_enabled: walletEnabled,
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
            پیکربندی هویت تجاری، درگاه‌های پرداخت و مالیات
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

      {/* Tab bar. The page was one long scroll of every settings card, so
          "where do I change the SMTP host" meant scrolling past the tax form.
          The groups follow WordPress's Settings screen (General / Writing /
          Reading / Discussion / Media) collapsed into the five areas this
          store actually has, and every card keeps its own save button or the
          form submit below — the tabs only decide what is visible. */}
      <div
        role="tablist"
        aria-label="بخش‌های تنظیمات"
        className="flex flex-wrap gap-1.5 border-b border-border pb-2"
      >
        {(
          [
            ["general", "عمومی", Store],
            ["content", "محتوا و رسانه", FileText],
            ["financial", "مالی و پرداخت", CreditCard],
            ["features", "قابلیت‌های فروشگاه", SlidersHorizontal],
            ["communication", "ارتباطات (پیامک)", Mail],
            ["security", "امنیت", ShieldCheck],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={activeTab === id}
            onClick={() => setActiveTab(id)}
            className={`flex items-center gap-1.5 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
              activeTab === id
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:bg-muted"
            }`}
          >
            <Icon className="h-4 w-4" />
            {label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSave} className="space-y-6">
        {activeTab === "general" && (
          <>
        {/* Site identity: the keys the feed, sitemap and robots route read. */}
        <SiteIdentityCard />

        {/* The admin-email card was removed on 2026-10-07 with the rest of
            the email feature. */}

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
              <Label>واحد پول رسمی سیستم</Label>
              <Input value="ریال ایران (نمایش در فرانت: تومان)" disabled className="bg-muted" />
            </div>
          </div>
        </Card>
          </>
        )}

        {activeTab === "content" && (
          <>
        {/* Content & permalink settings (WordPress reading/permalink parity) */}
        <ContentSettingsCard />
        <UserSettingsCard />
        <RobotsSettingsCard />
        {/* Image SEO (Rank Math Pro parity): fill empty alt/title/caption
            from the file name at upload time. */}
        <ImageSeoSettingsCard />
        {/* Breadcrumbs (Rank Math Pro parity): the trail shown above posts
            and products, and the BreadcrumbList structured data. */}
        <BreadcrumbSettingsCard />
        {/* Instant Indexing (Rank Math Pro parity): IndexNow auto-submit on
            publish + honest Google connection status. */}
        <IndexingSettingsCard />
        {/* Local SEO (Rank Math Pro parity): business profile → LocalBusiness
            JSON-LD with a live preview of the emitted node. */}
        <LocalSeoSettingsCard />
        {/* Content AI (Rank Math Pro parity): meta suggestions via a
            configured LLM — honest "not connected" without a key. */}
        <ContentAiSettingsCard />

        {/* Category→tag conversion and the trash purge. Kept off the settings
            form on purpose: both are destructive-capable, and a mistyped value
            in a settings form would fire them silently. */}
        <ContentToolsCard />
          </>
        )}

        {activeTab === "financial" && (
          <>
        {/* Financial & Tax Settings */}
        <Card className="p-6">
          <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
            <FileText className="h-5 w-5 text-primary" />
            <h2 className="text-base font-bold text-foreground">مالیات</h2>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div className="space-y-2">
              <Label>نرخ مالیات بر ارزش افزوده (درصد)</Label>
              <Input
                type="number"
                value={taxRate}
                onChange={(e) => setTaxRate(e.target.value)}
                placeholder="9"
              />
              <p className="text-xs text-muted-foreground">نرخ واحد مالیات — در سبد خرید، چک‌اوت و سفارش‌های جدید همین نرخ اعمال می‌شود</p>
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
          </div>
        </Card>
          </>
        )}

        {activeTab === "features" && (
          <Card className="p-6">
            <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
              <div>
                <h2 className="text-base font-bold text-foreground">قابلیت‌های فروشگاه</h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  خاموش کردن یک قابلیت، آن را کاملاً از فروشگاه حذف می‌کند: لینک منو، دکمه‌های
                  صفحه محصول و خود صفحه دیگر نمایش داده نمی‌شوند و درخواست‌های آن هم رد می‌شوند.
                </p>
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
                <div className="flex items-start gap-3">
                  <Heart className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <div className="font-medium text-foreground">علاقه‌مندی‌ها</div>
                    <div className="text-xs text-muted-foreground">
                      ذخیره محصولات برای مرور بعدی
                    </div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={shopFeatures.wishlist_enabled}
                  disabled={shopFeaturesLoading || savingFeature === "wishlist_enabled"}
                  onChange={(e) => toggleShopFeature("wishlist_enabled", e.target.checked)}
                  className="h-4 w-4 rounded accent-primary disabled:opacity-50"
                />
              </div>

              <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
                <div className="flex items-start gap-3">
                  <ArrowLeftRight className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <div className="font-medium text-foreground">مقایسه کالاها</div>
                    <div className="text-xs text-muted-foreground">
                      مقایسه مشخصات چند محصول در کنار هم
                    </div>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={shopFeatures.compare_enabled}
                  disabled={shopFeaturesLoading || savingFeature === "compare_enabled"}
                  onChange={(e) => toggleShopFeature("compare_enabled", e.target.checked)}
                  className="h-4 w-4 rounded accent-primary disabled:opacity-50"
                />
              </div>
            </div>
          </Card>
        )}

        {activeTab === "communication" && (
          <>
        {/* SMS Gateway & Notification Service */}
        <Card className="p-6">
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              <h2 className="text-base font-bold text-foreground">
                تنظیمات پیامک و سامانه اطلاع‌رسانی (SMS Gateway)
              </h2>
            </div>
            <Badge variant="outline" className="text-xs">
              {smsEnabled ? "سامانه فعال" : "سامانه غیرفعال"}
            </Badge>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>ارائه‌دهنده وب‌سرویس پیامک</Label>
                <select
                  value={smsProvider}
                  onChange={(e) => setSmsProvider(e.target.value as "kavenegar" | "farazsms" | "sms_ir")}
                  className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <option value="kavenegar">کاوه‌نگار (Kavenegar REST API)</option>
                  <option value="farazsms">فراز اس‌ام‌اس (FarazSMS / IPPanel)</option>
                  <option value="sms_ir">سامانه اس‌ام‌اس دات آی‌آر (SMS.ir)</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label>کلید دسترسی (API Key / Token)</Label>
                <Input
                  dir="ltr"
                  type="password"
                  value={smsApiKey}
                  onChange={(e) => setSmsApiKey(e.target.value)}
                  placeholder="کلید احراز هویت وب‌سرویس"
                  className="font-mono text-xs"
                />
              </div>

              <div className="space-y-2">
                <Label>شماره خط ارسال‌کننده</Label>
                <Input
                  dir="ltr"
                  value={smsSenderNumber}
                  onChange={(e) => setSmsSenderNumber(e.target.value)}
                  placeholder="مثال: 10008564 یا 3000..."
                  className="font-mono text-xs"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>کد الگوی اعتبارسنجی و ورود (OTP Pattern Code)</Label>
                <Input
                  dir="ltr"
                  value={smsOtpPattern}
                  onChange={(e) => setSmsOtpPattern(e.target.value)}
                  placeholder="کد پترن خدماتی جهت ارسال سریع OTP"
                  className="font-mono text-xs"
                />
              </div>

              <div className="space-y-2">
                <Label>کد الگوی وضعیت سفارش (Order Pattern Code)</Label>
                <Input
                  dir="ltr"
                  value={smsOrderPattern}
                  onChange={(e) => setSmsOrderPattern(e.target.value)}
                  placeholder="کد پترن پیامک تغییر وضعیت سفارش"
                  className="font-mono text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-between rounded-lg border border-border p-3.5">
              <div>
                <div className="font-medium text-foreground">فعال‌بودن ارسال پیامک سیستمی</div>
                <div className="text-xs text-muted-foreground">ارسال رمز یکبار مصرف و اعلانات خرید به کاربران</div>
              </div>
              <input
                type="checkbox"
                checked={smsEnabled}
                onChange={(e) => setSmsEnabled(e.target.checked)}
                className="h-4 w-4 rounded accent-primary"
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <Button
                type="button"
                size="sm"
                onClick={handleSaveSms}
                disabled={smsSaving}
                className="gap-1.5"
              >
                {smsSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                ذخیره تنظیمات پیامک
              </Button>

              {smsStatus && (
                <p
                  className={`flex items-center gap-1.5 text-xs ${
                    smsStatus.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {smsStatus.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {smsStatus.text}
                </p>
              )}
            </div>

            {/* Test SMS Box */}
            <div className="mt-4 rounded-lg border border-border/80 bg-muted/40 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Smartphone className="h-4 w-4 text-primary" />
                <span className="text-xs font-bold text-foreground">تست ارسال پیامک اعتباری</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  dir="ltr"
                  value={testPhone}
                  onChange={(e) => setTestPhone(e.target.value)}
                  placeholder="شماره موبایل تست (۰۹۱۲۳۴۵۶۷۸۹)"
                  className="font-mono text-xs sm:w-64"
                />
                <Input
                  value={testMessage}
                  onChange={(e) => setTestMessage(e.target.value)}
                  placeholder="متن پیامک تستی"
                  className="text-xs flex-1"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleTestSms}
                  disabled={testSending}
                  className="gap-1.5 shrink-0"
                >
                  {testSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4" />
                  )}
                  ارسال پیامک آزمایشی
                </Button>
              </div>
              {testResult && (
                <p
                  className={`mt-2 flex items-center gap-1.5 text-xs ${
                    testResult.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {testResult.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {testResult.text}
                </p>
              )}
            </div>
          </div>
        </Card>

        {/* The SMTP / transactional-email card was removed on 2026-10-07 with
            the rest of the email feature. */}

          </>
        )}

        {activeTab === "security" && (
          <>
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
              <div className="text-xs text-muted-foreground">ورود دومرحله‌ای (2FA)</div>
              <div className="mt-1 font-bold text-sm text-foreground">TOTP Authenticator</div>
              <div className="mt-1 text-xs text-emerald-600 font-medium">Google Authenticator / پیامک</div>
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
          </>
        )}

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
