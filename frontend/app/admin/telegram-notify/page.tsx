"use client";

/**
 * Admin — اطلاع‌رسانی تلگرام سفارشات (Telegram Order Notifier).
 *
 * Ported from the owner's WordPress plugin "woocommerce-telegram-notifier".
 * Config stored as SiteSetting `tgnotif.config`. Three sections:
 * - «تنظیمات اتصال» — bot token, enable/disable, webhook secret + register
 * - «مسیردهی به چت/تاپیک» — per-status chat_id + topic_id
 * - «فیلدهای پیام» — checkboxes for each data field (synced with backend)
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Banknote,
  Bookmark,
  CheckCircle2,
  CircleDollarSign,
  ClipboardList,
  Clock,
  CreditCard,
  ExternalLink,
  Fingerprint,
  Globe,
  Hash,
  Loader2,
  Link as LinkIcon,
  MapPin,
  MessageSquareText,
  Package,
  Percent,
  Phone,
  Receipt,
  Save,
  Search,
  Send,
  Settings,
  ShieldCheck,
  ShoppingCart,
  Sparkles,
  StickyNote,
  Tag,
  Timer,
  Truck,
  User,
  type LucideIcon,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import {
  fetchTgNotifConfig,
  updateTgNotifConfig,
  sendTgNotifTest,
  registerTgNotifWebhook,
  type TgNotifConfig,
} from "@/lib/api/tgnotif-admin";
import { STATUS_VISUALS } from "@/lib/admin/order-domain";

// ── Status entries — labels from STATUS_VISUALS (single source of truth) ─

const STATUS_ENTRIES: { key: string; Icon: LucideIcon }[] = [
  { key: "pending",         Icon: Search },
  { key: "processing",      Icon: Loader2 },
  { key: "doing_verified",  Icon: ShieldCheck },
  { key: "completed",       Icon: CheckCircle2 },
  { key: "canceled",        Icon: AlertTriangle },
];

// ── Field toggle groups (synced with backend DEFAULT_CONFIG) ─────────────

type FieldToggle = { key: keyof TgNotifConfig; label: string; Icon: LucideIcon };

const FIELD_GROUPS: { title: string; fields: FieldToggle[] }[] = [
  {
    title: "اطلاعات سفارش",
    fields: [
      { key: "show_order_id",    label: "شماره سفارش",          Icon: Hash },
      { key: "show_status",      label: "وضعیت سفارش",           Icon: ClipboardList },
      { key: "show_order_link",  label: "لینک سفارش در پنل",     Icon: LinkIcon },
      { key: "show_date",        label: "تاریخ ثبت",             Icon: Clock },
      { key: "show_notes",       label: "یادداشت مشتری",         Icon: StickyNote },
    ],
  },
  {
    title: "محصولات",
    fields: [
      { key: "show_items",        label: "نام و تعداد محصول",    Icon: Package },
      { key: "show_variant_info", label: "مشخصات تنوع (رنگ/سایز)", Icon: Sparkles },
      { key: "show_sku",          label: "کد SKU محصول",         Icon: Tag },
      { key: "show_custom_fields",label: "فیلدهای سفارشی (اکانت/آیدی)", Icon: Fingerprint },
    ],
  },
  {
    title: "مبالغ",
    fields: [
      { key: "show_total",    label: "مبلغ کل",             Icon: Banknote },
      { key: "show_subtotal", label: "مبلغ قبل از تخفیف",   Icon: CircleDollarSign },
      { key: "show_shipping", label: "هزینه ارسال",          Icon: Truck },
      { key: "show_tax",      label: "مالیات",               Icon: Receipt },
      { key: "show_coupon",   label: "تخفیف / کد تخفیف",    Icon: Percent },
    ],
  },
  {
    title: "پرداخت",
    fields: [
      { key: "show_payment_method", label: "روش پرداخت",      Icon: CreditCard },
      { key: "show_payment_status", label: "وضعیت پرداخت",    Icon: Timer },
      { key: "show_payment_ref",    label: "شناسه تراکنش",    Icon: Bookmark },
    ],
  },
  {
    title: "اطلاعات مشتری",
    fields: [
      { key: "show_customer_name", label: "نام مشتری",          Icon: User },
      { key: "show_phone",         label: "شماره تلفن",          Icon: Phone },
      { key: "show_national_code", label: "کد ملی",              Icon: Fingerprint },
      { key: "show_verified",      label: "وضعیت احراز هویت",   Icon: ShieldCheck },
      { key: "show_address",       label: "آدرس ارسال",          Icon: MapPin },
      { key: "show_ip",            label: "آیپی کاربر",          Icon: Globe },
    ],
  },
];

// ── Component ────────────────────────────────────────────────────────────

export default function TelegramNotifyPage() {
  const { toast } = useToast();
  const [config, setConfig] = useState<TgNotifConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [registeringWebhook, setRegisteringWebhook] = useState(false);
  const [dirty, setDirty] = useState(false);

  // ── Load ─────────────────────────────────────────────────────────

  const loadConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchTgNotifConfig();
      setConfig(res.config);
    } catch {
      toast({ title: "خطا در بارگذاری تنظیمات", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => { loadConfig(); }, [loadConfig]);

  // ── Save ─────────────────────────────────────────────────────────

  const handleSave = async () => {
    if (!config) return;
    setSaving(true);
    try {
      const res = await updateTgNotifConfig(config);
      setConfig(res.config);
      setDirty(false);
      toast({ title: "تنظیمات با موفقیت ذخیره شد" });
    } catch {
      toast({ title: "خطا در ذخیره تنظیمات", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  // ── Test ─────────────────────────────────────────────────────────

  const handleTest = async () => {
    setTesting(true);
    try {
      const res = await sendTgNotifTest();
      if (res.ok) {
        toast({ title: "پیام تست با موفقیت ارسال شد" });
      } else {
        toast({ title: `خطا: ${res.error || "ارسال ناموفق"}`, variant: "destructive" });
      }
    } catch {
      toast({ title: "خطا در ارسال پیام تست", variant: "destructive" });
    } finally {
      setTesting(false);
    }
  };

  // ── Register webhook ─────────────────────────────────────────────

  const handleRegisterWebhook = async () => {
    setRegisteringWebhook(true);
    try {
      const res = await registerTgNotifWebhook();
      if (res.ok) {
        toast({ title: "وبهوک با موفقیت ثبت شد", description: res.webhook_url });
      } else {
        toast({ title: `خطا: ${res.error || "ثبت ناموفق"}`, variant: "destructive" });
      }
    } catch {
      toast({ title: "خطا در ثبت وبهوک", variant: "destructive" });
    } finally {
      setRegisteringWebhook(false);
    }
  };

  // ── Field change helper ──────────────────────────────────────────

  const updateField = (key: string, value: unknown) => {
    setConfig((prev) => (prev ? { ...prev, [key]: value } : prev));
    setDirty(true);
  };

  // ── Render ───────────────────────────────────────────────────────

  if (loading || !config) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">اطلاع‌رسانی تلگرام سفارشات</h1>
          <p className="text-muted-foreground mt-1">
            هنگام تغییر وضعیت سفارشات، پیام به بات تلگرام ارسال می‌شود
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleTest}
            disabled={testing || !config.enabled}
            className="gap-2"
          >
            {testing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            ارسال تست
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving || !dirty} className="gap-2">
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
            ذخیره تنظیمات
          </Button>
        </div>
      </div>

      {/* ── Connection Settings ────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            تنظیمات اتصال
          </CardTitle>
          <CardDescription>توکن بات تلگرام و تنظیمات امنیتی وبهوک</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Master switch */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div>
              <p className="font-medium">فعال بودن اطلاع‌رسانی</p>
              <p className="text-sm text-muted-foreground">در صورت غیرفعال بودن، هیچ پیامی ارسال نمی‌شود</p>
            </div>
            <Switch checked={config.enabled} onCheckedChange={(v) => updateField("enabled", v)} />
          </div>

          {/* Bot token */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">توکن بات تلگرام</label>
            <Input
              type="password"
              placeholder="1234567890:ABCdefGhIJKlmNoPQRsTUVwxYZ"
              value={config.bot_token}
              onChange={(e) => updateField("bot_token", e.target.value)}
              dir="ltr"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">
              از{" "}
              <a href="https://t.me/BotFather" target="_blank" rel="noopener noreferrer" className="text-primary underline">
                @BotFather
              </a>{" "}
              دریافت کنید
            </p>
          </div>

          {/* Webhook secret */}
          <div className="space-y-1.5">
            <label className="text-sm font-medium">رمز وبهوک (Webhook Secret)</label>
            <Input
              type="password"
              placeholder="یک رشته تصادفی قوی"
              value={config.webhook_secret}
              onChange={(e) => updateField("webhook_secret", e.target.value)}
              dir="ltr"
              className="font-mono"
            />
            <p className="text-xs text-muted-foreground">در production اجباری است — بدون آن وبهوک در معرض دسترسی عمومی است</p>
          </div>

          <Button
            variant="outline"
            onClick={handleRegisterWebhook}
            disabled={registeringWebhook || !config.bot_token}
            className="gap-2"
          >
            {registeringWebhook ? <Loader2 className="h-4 w-4 animate-spin" /> : <Globe className="h-4 w-4" />}
            ثبت وبهوک در تلگرام
          </Button>
        </CardContent>
      </Card>

      {/* ── Per-Status Routing ─────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <ExternalLink className="h-5 w-5" />
            مسیردهی پیام‌ها
          </CardTitle>
          <CardDescription>
            برای هر وضعیت، چت و تاپیک تلگرام مقصد را مشخص کنید.
            اگر خالی بماند از «در حال انجام» استفاده می‌شود.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            {STATUS_ENTRIES.map(({ key, Icon }) => {
              const visual = STATUS_VISUALS[key as keyof typeof STATUS_VISUALS];
              const label = visual?.label ?? key;
              return (
              <div key={key} className="rounded-lg border p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <Icon className="h-5 w-5 text-muted-foreground" />
                  <span className="font-medium">{label}</span>
                  <Badge variant="outline" className="font-mono text-xs">{key}</Badge>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Chat ID</label>
                    <Input
                      placeholder="مثلا: -1001234567890"
                      value={(config as unknown as Record<string, string>)[`chat_id_${key}`] ?? ""}
                      onChange={(e) => updateField(`chat_id_${key}`, e.target.value)}
                      dir="ltr"
                      className="font-mono text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <label className="text-xs text-muted-foreground">Topic ID (اختیاری)</label>
                    <Input
                      placeholder="شناسه تاپیک فوروم"
                      value={(config as unknown as Record<string, string>)[`topic_id_${key}`] ?? ""}
                      onChange={(e) => updateField(`topic_id_${key}`, e.target.value)}
                      dir="ltr"
                      className="font-mono text-sm"
                    />
                  </div>
                </div>
              </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* ── Field Toggles ──────────────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <MessageSquareText className="h-5 w-5" />
            فیلدهای پیام
          </CardTitle>
          <CardDescription>
            مشخص کنید کدام اطلاعات در پیام تلگرام نمایش داده شود
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {FIELD_GROUPS.map(({ title, fields }) => (
            <div key={title}>
              <p className="text-sm font-semibold text-muted-foreground mb-3">{title}</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                {fields.map(({ key, label, Icon }) => (
                  <div key={key} className="flex items-center justify-between rounded-lg border p-3">
                    <div className="flex items-center gap-2">
                      <Icon className="h-4 w-4 text-muted-foreground" />
                      <span className="text-sm">{label}</span>
                    </div>
                    <Switch
                      checked={config[key] as boolean}
                      onCheckedChange={(v) => updateField(key, v)}
                    />
                  </div>
                ))}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>

      {/* ── Status bar ─────────────────────────────────────────────── */}
      <div className="text-center text-sm text-muted-foreground pb-8">
        {config.enabled ? (
          <span className="flex items-center justify-center gap-1">
            <CheckCircle2 className="h-4 w-4 text-green-500" />
            اطلاع‌رسانی تلگرام فعال است
          </span>
        ) : (
          <span className="flex items-center justify-center gap-1">
            <AlertTriangle className="h-4 w-4 text-yellow-500" />
            اطلاع‌رسانی تلگرام غیرفعال است
          </span>
        )}
      </div>
    </div>
  );
}
