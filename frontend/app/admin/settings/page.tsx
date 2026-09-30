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
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";
import { ContentSettingsCard } from "@/components/admin/content-settings-card";

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

  // SMTP / Email Configuration State
  const [smtpHost, setSmtpHost] = useState("");
  const [smtpPort, setSmtpPort] = useState("587");
  const [smtpUsername, setSmtpUsername] = useState("");
  const [smtpPassword, setSmtpPassword] = useState("");
  const [smtpUseTls, setSmtpUseTls] = useState(true);
  const [smtpFromAddress, setSmtpFromAddress] = useState("");
  const [smtpFromName, setSmtpFromName] = useState("فروشگاه اینترنتی");
  const [smtpConfigured, setSmtpConfigured] = useState(false);
  const [smtpHasPassword, setSmtpHasPassword] = useState(false);
  const [smtpSaving, setSmtpSaving] = useState(false);
  const [smtpStatus, setSmtpStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testEmail, setTestEmail] = useState("");
  const [testEmailSending, setTestEmailSending] = useState(false);
  const [testEmailResult, setTestEmailResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [emailLog, setEmailLog] = useState<
    Array<{ id: string; recipient: string; subject: string; template: string | null; status: string; provider: string; attempts: number; error: string | null; created_at: string | null }>
  >([]);
  const [emailLogTotal, setEmailLogTotal] = useState(0);
  const [emailLogError, setEmailLogError] = useState(false);

  // Telegram Bot Configuration State
  const [telegramBotToken, setTelegramBotToken] = useState("");
  const [telegramBotUsername, setTelegramBotUsername] = useState("");
  const [telegramConfigured, setTelegramConfigured] = useState(false);
  const [telegramHasToken, setTelegramHasToken] = useState(false);
  const [telegramTokenMasked, setTelegramTokenMasked] = useState<string | null>(null);
  const [telegramSaving, setTelegramSaving] = useState(false);
  const [telegramStatus, setTelegramStatus] = useState<{ ok: boolean; text: string } | null>(null);
  const [testChatId, setTestChatId] = useState("");
  const [testTelegramSending, setTestTelegramSending] = useState(false);
  const [testTelegramResult, setTestTelegramResult] = useState<{ ok: boolean; text: string } | null>(null);
  const [telegramLog, setTelegramLog] = useState<
    Array<{ id: string; recipient: string; title: string; status: string; provider: string; attempts: number; error: string | null; created_at: string | null }>
  >([]);
  const [telegramLogTotal, setTelegramLogTotal] = useState(0);
  // True when the delivery-log read failed. Distinguishes "nothing sent yet"
  // from "we could not read the log".
  const [telegramLogError, setTelegramLogError] = useState(false);

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
      if (support?.support_email) setSupportEmail(String(support.support_email));
      if (shippingTax) {
        if (shippingTax.tax_rate_percent !== undefined)
          setTaxRate(String(shippingTax.tax_rate_percent));
        if (shippingTax.free_shipping_threshold_rials !== undefined)
          setFreeShippingThreshold(String(shippingTax.free_shipping_threshold_rials));
        if (shippingTax.default_shipping_fee_rials !== undefined)
          setDefaultShippingFee(String(shippingTax.default_shipping_fee_rials));
      }
      if (paymentFlags) {
        if (typeof paymentFlags.zarinpal_enabled === "boolean")
          setZarinpalEnabled(paymentFlags.zarinpal_enabled);
        if (typeof paymentFlags.card_to_card_enabled === "boolean")
          setC2cEnabled(paymentFlags.card_to_card_enabled);
        if (typeof paymentFlags.wallet_enabled === "boolean")
          setWalletEnabled(paymentFlags.wallet_enabled);
        if (typeof paymentFlags.crypto_enabled === "boolean")
          setCryptoEnabled(paymentFlags.crypto_enabled);
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
      const smtp = group("smtp");
      if (smtp) {
        if (typeof smtp.host === "string") setSmtpHost(smtp.host);
        if (smtp.port !== undefined) setSmtpPort(String(smtp.port));
        if (typeof smtp.username === "string") setSmtpUsername(smtp.username);
        if (typeof smtp.from_address === "string") setSmtpFromAddress(smtp.from_address);
        if (typeof smtp.from_name === "string") setSmtpFromName(smtp.from_name);
        if (typeof smtp.use_tls === "boolean") setSmtpUseTls(smtp.use_tls);
      }
      try {
        const { data: eff } = await apiClient.get<{
          host: string; port: number; username: string; use_tls: boolean;
          from_address: string; from_name: string; has_password: boolean; is_configured: boolean;
        }>("/settings/admin/email-providers");
        setSmtpConfigured(eff.is_configured);
        setSmtpHasPassword(eff.has_password);
        if (!smtp && eff.host) {
          setSmtpHost(eff.host);
          setSmtpPort(String(eff.port));
          setSmtpUsername(eff.username);
          setSmtpFromAddress(eff.from_address);
          setSmtpFromName(eff.from_name);
          setSmtpUseTls(eff.use_tls);
        }
      } catch { /* status banner stays unconfigured */ }

      try {
        const { data: logRes } = await apiClient.get<{ items: typeof emailLog; total: number }>(
          "/settings/admin/email-delivery-log?limit=10"
        );
        setEmailLog(logRes.items);
        setEmailLogTotal(logRes.total);
      } catch {
        // Same reasoning as the Telegram log below: an empty table and a failed
        // read are different facts and must not render the same.
        setEmailLogError(true);
      }

      const telegram = group("telegram");
      if (telegram) {
        if (typeof telegram.bot_username === "string") setTelegramBotUsername(telegram.bot_username);
      }
      try {
        const { data: tg } = await apiClient.get<{
          bot_username: string; has_token: boolean; token_masked: string | null;
          is_configured: boolean;
        }>("/settings/admin/telegram-provider");
        setTelegramConfigured(tg.is_configured);
        setTelegramHasToken(tg.has_token);
        setTelegramTokenMasked(tg.token_masked);
        if (!telegram && tg.bot_username) setTelegramBotUsername(tg.bot_username);
      } catch { /* status banner stays unconfigured */ }

      try {
        const { data: tgLogRes } = await apiClient.get<{ items: typeof telegramLog; total: number }>(
          "/settings/admin/telegram-delivery-log?limit=10"
        );
        setTelegramLog(tgLogRes.items);
        setTelegramLogTotal(tgLogRes.total);
      } catch {
        // Record the failure: an empty log and a failed read both leave
        // `telegramLog` at [], but "no messages have been sent" is a claim
        // about the admin's own delivery history that a failed read cannot
        // support.
        setTelegramLogError(true);
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

  const handleSaveSmtp = async () => {
    setSmtpSaving(true);
    setSmtpStatus(null);
    try {
      const payload: Record<string, unknown> = {
        host: smtpHost.trim(),
        port: Number(smtpPort) || 587,
        username: smtpUsername.trim(),
        use_tls: smtpUseTls,
        from_address: smtpFromAddress.trim(),
        from_name: smtpFromName.trim(),
      };
      // Only send a new password when the admin typed one — an empty field
      // means "keep the existing secret".
      if (smtpPassword.trim()) payload.password = smtpPassword.trim();
      try {
        await apiClient.patch("/settings/smtp", { value: payload });
      } catch (err) {
        const status = (err as { status?: number })?.status;
        if (status === 404) {
          await apiClient.post("/settings", {
            key: "smtp",
            value: payload,
            group: "messaging",
            description: "تنظیمات سرور SMTP ارسال ایمیل",
            is_public: false,
          });
        } else {
          throw err;
        }
      }
      setSmtpPassword("");
      setSmtpConfigured(Boolean(smtpHost.trim() && smtpFromAddress.trim()));
      setSmtpHasPassword(Boolean(smtpPassword.trim()) || smtpHasPassword);
      setSmtpStatus({ ok: true, text: "تنظیمات SMTP با موفقیت ذخیره شد." });
    } catch {
      setSmtpStatus({ ok: false, text: "خطا در ذخیره تنظیمات ایمیل. دسترسی خود را بررسی کنید." });
    } finally {
      setSmtpSaving(false);
    }
  };

  const handleTestEmail = async () => {
    if (!testEmail.trim() || !testEmail.includes("@")) {
      setTestEmailResult({ ok: false, text: "لطفاً نشانی ایمیل معتبر گیرنده را وارد کنید." });
      return;
    }
    setTestEmailSending(true);
    setTestEmailResult(null);
    try {
      const { data } = await apiClient.post<{ success: boolean; provider: string; error?: string | null }>(
        "/settings/admin/email-providers/test",
        { recipient: testEmail.trim() }
      );
      if (data.success && data.provider === "mock_fallback") {
        setTestEmailResult({
          ok: true,
          text: "اتصال برقرار شد، اما SMTP پیکربندی نشده — ایمیل به‌صورت شبیه‌سازی ثبت شد (mock).",
        });
      } else if (data.success) {
        setTestEmailResult({ ok: true, text: "ایمیل آزمایشی با موفقیت ارسال شد." });
      } else {
        setTestEmailResult({ ok: false, text: data.error || "ارسال ایمیل آزمایشی ناموفق بود." });
      }
      // Refresh the delivery log after a test send
      try {
        const { data: logRes } = await apiClient.get<{ items: typeof emailLog; total: number }>(
          "/settings/admin/email-delivery-log?limit=10"
        );
        setEmailLog(logRes.items);
        setEmailLogTotal(logRes.total);
      } catch { /* ignore */ }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setTestEmailResult({ ok: false, text: msg || "ارسال ایمیل آزمایشی با خطا مواجه شد." });
    } finally {
      setTestEmailSending(false);
    }
  };

  const handleSaveTelegram = async () => {
    setTelegramSaving(true);
    setTelegramStatus(null);
    try {
      const payload: Record<string, unknown> = {
        bot_username: telegramBotUsername.trim(),
      };
      // Only send a new token when the admin typed one — an empty field
      // means "keep the existing secret".
      if (telegramBotToken.trim()) payload.bot_token = telegramBotToken.trim();
      try {
        await apiClient.patch("/settings/telegram", { value: payload });
      } catch (err) {
        const status = (err as { status?: number })?.status;
        if (status === 404) {
          await apiClient.post("/settings", {
            key: "telegram",
            value: payload,
            group: "messaging",
            description: "تنظیمات ربات تلگرام اطلاع‌رسانی",
            is_public: false,
          });
        } else {
          throw err;
        }
      }
      const willHaveToken = Boolean(telegramBotToken.trim()) || telegramHasToken;
      setTelegramBotToken("");
      setTelegramHasToken(willHaveToken);
      setTelegramConfigured(willHaveToken);
      setTelegramStatus({ ok: true, text: "تنظیمات ربات تلگرام با موفقیت ذخیره شد." });
    } catch {
      setTelegramStatus({ ok: false, text: "خطا در ذخیره تنظیمات تلگرام. دسترسی خود را بررسی کنید." });
    } finally {
      setTelegramSaving(false);
    }
  };

  const handleTestTelegram = async () => {
    if (!testChatId.trim()) {
      setTestTelegramResult({ ok: false, text: "لطفاً شناسه چت (Chat ID) گیرنده را وارد کنید." });
      return;
    }
    setTestTelegramSending(true);
    setTestTelegramResult(null);
    try {
      const { data } = await apiClient.post<{ success: boolean; provider: string; error?: string | null }>(
        "/settings/admin/telegram-provider/test",
        { chat_id: testChatId.trim() }
      );
      if (data.success && data.provider === "mock_fallback") {
        setTestTelegramResult({
          ok: true,
          text: "اتصال برقرار شد، اما توکن ربات پیکربندی نشده — پیام به‌صورت شبیه‌سازی ثبت شد (mock).",
        });
      } else if (data.success) {
        setTestTelegramResult({ ok: true, text: "پیام آزمایشی تلگرام با موفقیت ارسال شد." });
      } else {
        setTestTelegramResult({ ok: false, text: data.error || "ارسال پیام آزمایشی ناموفق بود." });
      }
      // Refresh the delivery log after a test send
      try {
        const { data: tgLogRes } = await apiClient.get<{ items: typeof telegramLog; total: number }>(
          "/settings/admin/telegram-delivery-log?limit=10"
        );
        setTelegramLog(tgLogRes.items);
        setTelegramLogTotal(tgLogRes.total);
      } catch { /* ignore */ }
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message;
      setTestTelegramResult({ ok: false, text: msg || "ارسال پیام آزمایشی با خطا مواجه شد." });
    } finally {
      setTestTelegramSending(false);
    }
  };

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

        {/* Content & permalink settings (WordPress reading/permalink parity) */}
        <ContentSettingsCard />

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

        {/* SMTP Email Server & Transactional Mail */}
        <Card className="p-6">
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              <h2 className="text-base font-bold text-foreground">
                تنظیمات سرور ایمیل (SMTP) و ارسال تراکنشی
              </h2>
            </div>
            <Badge variant="outline" className="text-xs">
              {smtpConfigured ? "سامانه ایمیل فعال" : "SMTP پیکربندی نشده — حالت شبیه‌سازی"}
            </Badge>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>میزبان SMTP (Host)</Label>
                <Input
                  dir="ltr"
                  value={smtpHost}
                  onChange={(e) => setSmtpHost(e.target.value)}
                  placeholder="smtp.example.com"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-2">
                <Label>پورت</Label>
                <Input
                  dir="ltr"
                  type="number"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(e.target.value)}
                  placeholder="587 / 465 / 25"
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">۴۶۵ = SSL مستقیم، ۵۸۷ = STARTTLS</p>
              </div>
              <div className="space-y-2">
                <Label>فعال‌سازی TLS</Label>
                <div className="flex h-10 items-center gap-2 rounded-md border border-input px-3">
                  <input
                    type="checkbox"
                    checked={smtpUseTls}
                    onChange={(e) => setSmtpUseTls(e.target.checked)}
                    className="h-4 w-4 rounded accent-primary"
                  />
                  <span className="text-xs text-muted-foreground">رمزنگاری اتصال (توصیه‌شده)</span>
                </div>
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>نام کاربری (Username)</Label>
                <Input
                  dir="ltr"
                  value={smtpUsername}
                  onChange={(e) => setSmtpUsername(e.target.value)}
                  placeholder="noreply@site.com"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-2">
                <Label>گذرواژه (Password)</Label>
                <Input
                  dir="ltr"
                  type="password"
                  value={smtpPassword}
                  onChange={(e) => setSmtpPassword(e.target.value)}
                  placeholder={smtpHasPassword ? "•••••••• (ذخیره‌شده — برای تغییر وارد کنید)" : "گذرواژه SMTP"}
                  className="font-mono text-xs"
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>نشانی فرستنده (From Address)</Label>
                <Input
                  dir="ltr"
                  value={smtpFromAddress}
                  onChange={(e) => setSmtpFromAddress(e.target.value)}
                  placeholder="noreply@site.com"
                  className="font-mono text-xs"
                />
              </div>
              <div className="space-y-2">
                <Label>نام نمایشی فرستنده (From Name)</Label>
                <Input
                  value={smtpFromName}
                  onChange={(e) => setSmtpFromName(e.target.value)}
                  placeholder="فروشگاه اینترنتی"
                />
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <Button
                type="button"
                size="sm"
                onClick={handleSaveSmtp}
                disabled={smtpSaving}
                className="gap-1.5"
              >
                {smtpSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                ذخیره تنظیمات ایمیل
              </Button>

              {smtpStatus && (
                <p
                  className={`flex items-center gap-1.5 text-xs ${
                    smtpStatus.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {smtpStatus.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {smtpStatus.text}
                </p>
              )}
            </div>

            {/* Test Email Box */}
            <div className="mt-4 rounded-lg border border-border/80 bg-muted/40 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Send className="h-4 w-4 text-primary" />
                <span className="text-xs font-bold text-foreground">تست اتصال و ارسال ایمیل آزمایشی</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  dir="ltr"
                  value={testEmail}
                  onChange={(e) => setTestEmail(e.target.value)}
                  placeholder="نشانی ایمیل گیرنده تست (admin@example.com)"
                  className="font-mono text-xs sm:w-72"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleTestEmail}
                  disabled={testEmailSending}
                  className="gap-1.5 shrink-0"
                >
                  {testEmailSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Mail className="h-4 w-4" />
                  )}
                  ارسال ایمیل آزمایشی
                </Button>
              </div>
              {testEmailResult && (
                <p
                  className={`mt-2 flex items-center gap-1.5 text-xs ${
                    testEmailResult.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {testEmailResult.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {testEmailResult.text}
                </p>
              )}
            </div>

            {/* Recent Delivery Log */}
            <div className="mt-4 rounded-lg border border-border/80">
              <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
                <span className="text-xs font-bold text-foreground">گزارش ارسال‌های اخیر ایمیل</span>
                <span className="text-[11px] text-muted-foreground">
                  {emailLogTotal > 0 ? `${emailLogTotal} رکورد` : "بدون رکورد"}
                </span>
              </div>
              {emailLogError ? (
                <p
                  role="alert"
                  className="px-4 py-6 text-center text-xs text-destructive"
                >
                  دریافت گزارش تحویل ایمیل ناموفق بود. این پیام به‌معنای نبود ارسال
                  نیست؛ وضعیت تحویل در این لحظه خوانده نشد.
                </p>
              ) : emailLog.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                  هنوز ایمیلی از سامانه ارسال نشده است. پس از اولین ارسال، وضعیت تحویل اینجا نمایش داده می‌شود.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border/60 text-muted-foreground">
                        <th className="px-4 py-2 text-right font-medium">گیرنده</th>
                        <th className="px-4 py-2 text-right font-medium">موضوع</th>
                        <th className="px-4 py-2 text-right font-medium">قالب</th>
                        <th className="px-4 py-2 text-right font-medium">وضعیت</th>
                        <th className="px-4 py-2 text-right font-medium">تلاش</th>
                        <th className="px-4 py-2 text-right font-medium">خطا</th>
                        <th className="px-4 py-2 text-right font-medium">زمان</th>
                      </tr>
                    </thead>
                    <tbody>
                      {emailLog.map((row) => (
                        <tr key={row.id} className="border-b border-border/40 last:border-0">
                          <td className="px-4 py-2 font-mono text-[11px]" dir="ltr">{row.recipient}</td>
                          <td className="max-w-44 truncate px-4 py-2">{row.subject}</td>
                          <td className="px-4 py-2 font-mono text-[11px]">{row.template || "—"}</td>
                          <td className="px-4 py-2">
                            {row.status === "sent" ? (
                              <Badge className="bg-emerald-500/15 text-emerald-600 border border-emerald-500/25 text-[10px]">ارسال‌شده</Badge>
                            ) : row.status === "failed" ? (
                              <Badge variant="destructive" className="text-[10px]">ناموفق</Badge>
                            ) : (
                              <Badge variant="secondary" className="text-[10px]">در صف</Badge>
                            )}
                          </td>
                          <td className="px-4 py-2">{row.attempts}</td>
                          <td className="max-w-40 truncate px-4 py-2 text-destructive/80" title={row.error || ""}>
                            {row.error || "—"}
                          </td>
                          <td className="px-4 py-2 font-mono text-[11px]" dir="ltr">
                            {row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        </Card>

        {/* Telegram Bot & Transactional Messages */}
        <Card className="p-6">
          <div className="mb-4 flex items-center justify-between border-b border-border pb-3">
            <div className="flex items-center gap-2">
              <MessageSquare className="h-5 w-5 text-primary" />
              <h2 className="text-base font-bold text-foreground">
                تنظیمات ربات تلگرام و ارسال اعلان
              </h2>
            </div>
            <Badge variant="outline" className="text-xs">
              {telegramConfigured ? "ربات تلگرام فعال" : "توکن ربات پیکربندی نشده — حالت شبیه‌سازی"}
            </Badge>
          </div>

          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>توکن ربات (Bot Token)</Label>
                <Input
                  dir="ltr"
                  type="password"
                  value={telegramBotToken}
                  onChange={(e) => setTelegramBotToken(e.target.value)}
                  placeholder={
                    telegramHasToken
                      ? `${telegramTokenMasked || "••••••••"} (ذخیره‌شده — برای تغییر وارد کنید)`
                      : "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
                  }
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">
                  توکن را از BotFather دریافت کنید. بدون توکن، پیام‌ها فقط ثبت (شبیه‌سازی) می‌شوند.
                </p>
              </div>
              <div className="space-y-2">
                <Label>نام کاربری ربات (Username)</Label>
                <Input
                  dir="ltr"
                  value={telegramBotUsername}
                  onChange={(e) => setTelegramBotUsername(e.target.value)}
                  placeholder="myshop_bot"
                  className="font-mono text-xs"
                />
                <p className="text-xs text-muted-foreground">
                  برای ساخت پیوند اتصال حساب در پنل کاربری استفاده می‌شود (t.me/username).
                </p>
              </div>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 pt-2">
              <Button
                type="button"
                size="sm"
                onClick={handleSaveTelegram}
                disabled={telegramSaving}
                className="gap-1.5"
              >
                {telegramSaving ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Save className="h-4 w-4" />
                )}
                ذخیره تنظیمات تلگرام
              </Button>

              {telegramStatus && (
                <p
                  className={`flex items-center gap-1.5 text-xs ${
                    telegramStatus.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {telegramStatus.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {telegramStatus.text}
                </p>
              )}
            </div>

            {/* Test Telegram Box */}
            <div className="mt-4 rounded-lg border border-border/80 bg-muted/40 p-4">
              <div className="mb-2 flex items-center gap-2">
                <Send className="h-4 w-4 text-primary" />
                <span className="text-xs font-bold text-foreground">تست اتصال و ارسال پیام آزمایشی</span>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <Input
                  dir="ltr"
                  value={testChatId}
                  onChange={(e) => setTestChatId(e.target.value)}
                  placeholder="شناسه چت گیرنده (Chat ID)"
                  className="font-mono text-xs sm:w-72"
                />
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={handleTestTelegram}
                  disabled={testTelegramSending}
                  className="gap-1.5 shrink-0"
                >
                  {testTelegramSending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <MessageSquare className="h-4 w-4" />
                  )}
                  ارسال پیام آزمایشی
                </Button>
              </div>
              {testTelegramResult && (
                <p
                  className={`mt-2 flex items-center gap-1.5 text-xs ${
                    testTelegramResult.ok ? "text-emerald-600" : "text-destructive"
                  }`}
                >
                  {testTelegramResult.ok ? (
                    <CheckCircle2 className="h-3.5 w-3.5" />
                  ) : (
                    <AlertCircle className="h-3.5 w-3.5" />
                  )}
                  {testTelegramResult.text}
                </p>
              )}
              <p className="mt-2 text-[11px] text-muted-foreground">
                نکته: کاربران از بخش «اعلان‌ها» در پنل کاربری خود کد اتصال دریافت و به ربات ارسال می‌کنند تا Chat ID آن‌ها متصل شود.
              </p>
            </div>

            {/* Recent Telegram Delivery Log */}
            <div className="mt-4 rounded-lg border border-border/80">
              <div className="flex items-center justify-between border-b border-border/60 px-4 py-2.5">
                <span className="text-xs font-bold text-foreground">گزارش ارسال‌های اخیر تلگرام</span>
                <span className="text-[11px] text-muted-foreground">
                  {telegramLogTotal > 0 ? `${telegramLogTotal} رکورد` : "بدون رکورد"}
                </span>
              </div>
              {telegramLogError ? (
                <p
                  role="alert"
                  className="px-4 py-6 text-center text-xs text-destructive"
                >
                  دریافت گزارش تحویل تلگرام ناموفق بود. این پیام به‌معنای نبود
                  ارسال نیست؛ وضعیت تحویل در این لحظه خوانده نشد.
                </p>
              ) : telegramLog.length === 0 ? (
                <p className="px-4 py-6 text-center text-xs text-muted-foreground">
                  هنوز پیامی از سامانه ارسال نشده است. پس از اولین ارسال، وضعیت تحویل اینجا نمایش داده می‌شود.
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-border/60 text-muted-foreground">
                        <th className="px-4 py-2 text-right font-medium">گیرنده (Chat ID)</th>
                        <th className="px-4 py-2 text-right font-medium">عنوان</th>
                        <th className="px-4 py-2 text-right font-medium">وضعیت</th>
                        <th className="px-4 py-2 text-right font-medium">تلاش</th>
                        <th className="px-4 py-2 text-right font-medium">خطا</th>
                        <th className="px-4 py-2 text-right font-medium">زمان</th>
                      </tr>
                    </thead>
                    <tbody>
                      {telegramLog.map((row) => (
                        <tr key={row.id} className="border-b border-border/40 last:border-0">
                          <td className="px-4 py-2 font-mono text-[11px]" dir="ltr">{row.recipient}</td>
                          <td className="max-w-44 truncate px-4 py-2">{row.title}</td>
                          <td className="px-4 py-2">
                            {row.status === "sent" ? (
                              <Badge className="bg-emerald-500/15 text-emerald-600 border border-emerald-500/25 text-[10px]">ارسال‌شده</Badge>
                            ) : row.status === "failed" ? (
                              <Badge variant="destructive" className="text-[10px]">ناموفق</Badge>
                            ) : (
                              <Badge variant="secondary" className="text-[10px]">در صف</Badge>
                            )}
                          </td>
                          <td className="px-4 py-2">{row.attempts}</td>
                          <td className="max-w-40 truncate px-4 py-2 text-destructive/80" title={row.error || ""}>
                            {row.error || "—"}
                          </td>
                          <td className="px-4 py-2 font-mono text-[11px]" dir="ltr">
                            {row.created_at ? new Date(row.created_at).toLocaleString("fa-IR") : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
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
