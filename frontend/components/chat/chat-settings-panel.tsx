"use client";

import { useEffect, useState } from "react";
import {
  Activity,
  Bot,
  GitBranch,
  HelpCircle,
  Image as ImageIcon,
  Link2,
  type LucideIcon,
  Monitor,
  Newspaper,
  Palette,
  Phone,
  Rocket,
  Ruler,
  Save,
  Settings,
  Smartphone,
  Loader2,
  MessageSquare,
  ClipboardList,
  Globe,
  FileText,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/use-toast";
import { QuickFlowBuilder } from "@/components/chat/quick-flow-builder";
import { ImageField } from "@/components/chat/image-field";
import {
  PrechatFieldsEditor,
  normalizePrechatKeys,
} from "@/components/chat/prechat-fields-editor";
import { FaqEditor, NewsEditor, type FaqRow, type NewsRow } from "@/components/chat/faq-news-editors";
import type { PrechatField, QuickFlowNode } from "@/lib/api/chat";

/**
 * Widget configuration panel — the WordPress plugin's settings page, ported.
 *
 * Tabs mirror the plugin: ظاهر / اندازه / محتوا / فرم پیش از چت / فنی /
 * مانیتورینگ / لوگو. Edits the single `chat.widget` SiteSetting row. Secrets
 * (telegram token / webhook secret) are masked on read and preserved on a
 * masked write, so the live credential never leaves the server.
 */

interface Props {
  load: () => Promise<{ config: Record<string, unknown> }>;
  save: (config: Record<string, unknown>) => Promise<{ config: Record<string, unknown> }>;
}

const ONLINE_FIELDS: { key: string; label: string; Icon: LucideIcon }[] = [
  { key: "ip", label: "آدرس IP", Icon: Globe },
  { key: "ua", label: "مرورگر و دستگاه", Icon: Monitor },
  { key: "phone", label: "شماره تلفن", Icon: Phone },
];

export function ChatSettingsPanel({ load, save }: Props) {
  const { toast } = useToast();
  const [config, setConfig] = useState<Record<string, unknown> | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    void load()
      .then((r) => setConfig(r.config))
      .catch(() => toast({ title: "خطا در بارگذاری تنظیمات", variant: "destructive" }));
  }, [load, toast]);

  if (!config) {
    return (
      <div className="flex justify-center py-16">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const set = (key: string, value: unknown) => setConfig((c) => ({ ...(c || {}), [key]: value }));
  const str = (key: string) => String(config[key] ?? "");
  const num = (key: string) => Number(config[key] ?? 0);
  const bool = (key: string) => Boolean(config[key]);
  const onlineShow = (config.online_show_fields as string[]) || ["ip", "ua", "phone"];

  const onSave = async () => {
    setSaving(true);
    const payload: Record<string, unknown> = {
      ...config,
      prechat_fields: normalizePrechatKeys((config.prechat_fields as PrechatField[]) || []),
      quick_replies:
        typeof config.quick_replies === "string"
          ? (config.quick_replies as string)
              .split("\n")
              .map((s) => s.trim())
              .filter(Boolean)
          : config.quick_replies,
    };
    const res = await save(payload);
    setSaving(false);
    setConfig(res.config);
    toast({ title: "تنظیمات ذخیره شد" });
  };

  return (
    <Tabs defaultValue="appearance" dir="rtl" className="space-y-4">
      <TabsList className="flex h-auto flex-wrap justify-start gap-1 bg-muted p-1">
        <TabsTrigger value="appearance" className="flex items-center gap-1.5">
          <Palette className="h-4 w-4" /> ظاهر و رنگ‌ها
        </TabsTrigger>
        <TabsTrigger value="position" className="flex items-center gap-1.5">
          <Ruler className="h-4 w-4" /> اندازه و موقعیت
        </TabsTrigger>
        <TabsTrigger value="content" className="flex items-center gap-1.5">
          <FileText className="h-4 w-4" /> محتوا و زبان
        </TabsTrigger>
        <TabsTrigger value="prechat" className="flex items-center gap-1.5">
          <ClipboardList className="h-4 w-4" /> فرم پیش از چت
        </TabsTrigger>
        <TabsTrigger value="tech" className="flex items-center gap-1.5">
          <Link2 className="h-4 w-4" /> تنظیمات فنی
        </TabsTrigger>
        <TabsTrigger value="monitoring" className="flex items-center gap-1.5">
          <Activity className="h-4 w-4" /> مانیتورینگ
        </TabsTrigger>
        <TabsTrigger value="logos" className="flex items-center gap-1.5">
          <ImageIcon className="h-4 w-4" /> لوگو و آواتار
        </TabsTrigger>
      </TabsList>

      {/* ── Appearance ── */}
      <TabsContent value="appearance">
        <Card className="space-y-4 p-6">
          <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
            <Palette className="h-4 w-4" /> پالت رنگی
          </h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <ColorField label="رنگ اصلی (Accent)" value={str("color_primary")} onChange={(v) => set("color_primary", v)} />
            <ColorField label="رنگ هدر" value={str("color_header")} onChange={(v) => set("color_header", v)} />
            <ColorField label="رنگ دکمه ویجت" value={str("color_button")} onChange={(v) => set("color_button", v)} />
            <ColorField label="بک‌گراند چت" value={str("color_chatbg")} onChange={(v) => set("color_chatbg", v)} />
            <ColorField label="بک‌گراند محتوا" value={str("color_viewbg")} onChange={(v) => set("color_viewbg", v)} />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">زبان ویجت</Label>
              <select
                value={str("lang")}
                onChange={(e) => set("lang", e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              >
                <option value="fa">فارسی (RTL)</option>
                <option value="en">English (LTR)</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-sm font-semibold">فرمت تاریخ</Label>
              <select
                value={str("date_format")}
                onChange={(e) => set("date_format", e.target.value)}
                className="h-10 w-full rounded-md border bg-background px-3 text-sm"
              >
                <option value="shamsi">شمسی (جلالی)</option>
                <option value="miladi">میلادی</option>
              </select>
            </div>
          </div>
        </Card>
      </TabsContent>

      {/* ── Position & size ── */}
      <TabsContent value="position">
        <Card className="space-y-4 p-6">
          <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
            <Ruler className="h-4 w-4" /> اندازه و موقعیت
          </h2>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumField label="عرض ویجت (px)" value={num("widget_width")} onChange={(v) => set("widget_width", v)} min={280} max={600} />
            <NumField label="ارتفاع ویجت (px)" value={num("widget_height")} onChange={(v) => set("widget_height", v)} min={400} max={900} />
          </div>
          <h3 className="flex items-center gap-1.5 border-b pb-2 pt-2 text-sm font-bold">
            <Monitor className="h-3.5 w-3.5" /> دسکتاپ
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumField label="فاصله از پایین (px)" value={num("btn_bottom_desktop")} onChange={(v) => set("btn_bottom_desktop", v)} />
            <NumField label="فاصله از کنار (px)" value={num("btn_side_desktop")} onChange={(v) => set("btn_side_desktop", v)} />
          </div>
          <h3 className="flex items-center gap-1.5 border-b pb-2 pt-2 text-sm font-bold">
            <Smartphone className="h-3.5 w-3.5" /> موبایل
          </h3>
          <div className="grid gap-4 sm:grid-cols-2">
            <NumField label="فاصله از پایین (px)" value={num("btn_bottom_mobile")} onChange={(v) => set("btn_bottom_mobile", v)} />
            <NumField label="فاصله از کنار (px)" value={num("btn_side_mobile")} onChange={(v) => set("btn_side_mobile", v)} />
          </div>
        </Card>
      </TabsContent>

      {/* ── Content ── */}
      <TabsContent value="content">
        <div className="space-y-4">
          <Card className="space-y-4 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <FileText className="h-4 w-4" /> متون ثابت
            </h2>
            <TextField label="عنوان خوش‌آمدگویی" value={str("welcome_title")} onChange={(v) => set("welcome_title", v)} />
            <TextField label="زیرعنوان خوش‌آمدگویی" value={str("welcome_sub")} onChange={(v) => set("welcome_sub", v)} />
            <TextField label="پیام خودکار خوش‌آمدگویی" value={str("welcome_message")} onChange={(v) => set("welcome_message", v)} placeholder="سلام! سوالی دارید؟" />
            <TextField label="متن دکمهٔ انتقال به انسان" value={str("handoff_button_text")} onChange={(v) => set("handoff_button_text", v)} />
            <TextField label="متن موفقیت انتقال به انسان" value={str("handoff_success_text")} onChange={(v) => set("handoff_success_text", v)} />
            <TextField label="پیام سیستمی درخواست پشتیبانی" value={str("handoff_system_message")} onChange={(v) => set("handoff_system_message", v)} />
            <TextField label="نام پیش‌فرض پشتیبان" value={str("default_support_name")} onChange={(v) => set("default_support_name", v)} />
            <div className="border-t pt-4">
              <Label className="mb-1 flex items-center gap-1.5 text-sm font-semibold">
                <MessageSquare className="h-3.5 w-3.5" /> پاسخ‌های سریع (هر خط یک دکمه)
              </Label>
              <textarea
                value={
                  Array.isArray(config.quick_replies)
                    ? (config.quick_replies as string[]).join("\n")
                    : str("quick_replies")
                }
                onChange={(e) => set("quick_replies", e.target.value)}
                rows={4}
                placeholder={"قیمت محصولات\nپیگیری سفارش\nساعات کاری"}
                className="w-full rounded-lg border bg-background p-2 text-sm"
              />
            </div>
          </Card>

          <Card className="space-y-3 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <GitBranch className="h-4 w-4" /> فلو پاسخ‌های سریع (چندمرحله‌ای)
            </h2>
            <p className="text-xs text-muted-foreground">
              دکمه‌هایی که یا پاسخ آماده می‌فرستند یا زیرمنو باز می‌کنند. با تکمیل فلو، کل گفتگو به
              n8n ارسال می‌شود تا هوش مصنوعی با دانش آمادهٔ شما پاسخ دهد.
            </p>
            <QuickFlowBuilder
              value={(config.quick_flow as QuickFlowNode[]) || []}
              onChange={(nodes) => set("quick_flow", nodes)}
            />
          </Card>

          <Card className="space-y-3 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <Rocket className="h-4 w-4" /> پاپ‌آپ هوشمند (Proactive)
            </h2>
            <div className="flex items-center gap-3">
              <Switch checked={bool("proactive_enabled")} onCheckedChange={(v) => set("proactive_enabled", v)} />
              <Label className="text-sm font-semibold">فعال‌سازی پاپ‌آپ هوشمند</Label>
            </div>
            {bool("proactive_enabled") && (
              <>
                <TextField label="متن پاپ‌آپ" value={str("proactive_text")} onChange={(v) => set("proactive_text", v)} />
                <div className="grid gap-4 sm:grid-cols-2">
                  <NumField label="تأخیر نمایش (ثانیه)" value={num("proactive_delay")} onChange={(v) => set("proactive_delay", v)} min={0} />
                  <NumField label="کول‌داون تکرار (ساعت)" value={num("proactive_cooldown")} onChange={(v) => set("proactive_cooldown", v)} min={0} />
                </div>
                <div className="grid gap-4 sm:grid-cols-2">
                  <ColorField label="رنگ پس‌زمینه پاپ‌آپ" value={str("color_proactive_bg")} onChange={(v) => set("color_proactive_bg", v)} />
                  <ColorField label="رنگ متن پاپ‌آپ" value={str("color_proactive_text")} onChange={(v) => set("color_proactive_text", v)} />
                </div>
              </>
            )}
          </Card>

          <Card className="space-y-3 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <HelpCircle className="h-4 w-4" /> سوالات متداول
            </h2>
            <p className="text-xs text-muted-foreground">
              اگر خالی بماند، تب «سوالات» در ویجت حالت خالی («سوالی نیست») نشان می‌دهد.
            </p>
            <FaqEditor
              value={(config.faqs as FaqRow[]) || []}
              onChange={(rows) => set("faqs", rows)}
            />
          </Card>

          <Card className="space-y-3 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <Newspaper className="h-4 w-4" /> اخبار
            </h2>
            <p className="text-xs text-muted-foreground">
              اگر خالی بماند، تب «اخبار» در ویجت حالت خالی («خبری نیست») نشان می‌دهد.
            </p>
            <NewsEditor
              value={(config.news as NewsRow[]) || []}
              onChange={(rows) => set("news", rows)}
            />
          </Card>
        </div>
      </TabsContent>

      {/* ── Pre-chat form ── */}
      <TabsContent value="prechat">
        <Card className="space-y-3 p-6">
          <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
            <ClipboardList className="h-4 w-4" /> فیلدهای فرم پیش از چت
          </h2>
          <PrechatFieldsEditor
            value={(config.prechat_fields as PrechatField[]) || []}
            onChange={(fields) => set("prechat_fields", fields)}
          />
        </Card>
      </TabsContent>

      {/* ── Technical ── */}
      <TabsContent value="tech">
        <div className="space-y-4">
          <Card className="space-y-4 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <Link2 className="h-4 w-4" /> اتصال n8n
            </h2>
            <TextField
              label="آدرس Webhook در n8n"
              value={str("webhook_url")}
              onChange={(v) => set("webhook_url", v)}
              dir="ltr"
              placeholder="https://n8n.example.com/webhook/chat"
            />
            <p className="text-xs text-muted-foreground">
              پیام کاربر به این آدرس ارسال می‌شود و پاسخ JSON (با کلید output یا text) به‌عنوان پاسخ
              هوش مصنوعی ثبت می‌شود.
            </p>
          </Card>

          <Card className="space-y-4 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <Bot className="h-4 w-4" /> تلگرام (پشتیبانی انسانی)
            </h2>
            <TextField label="توکن ربات تلگرام" value={str("telegram_bot_token")} onChange={(v) => set("telegram_bot_token", v)} dir="ltr" type="password" placeholder="123456:ABC-DEF..." />
            <TextField label="شناسه گروه/چت مدیریت (Chat ID)" value={str("telegram_chat_id")} onChange={(v) => set("telegram_chat_id", v)} dir="ltr" placeholder="-1001234567890" />
            <TextField label="کلید مخفی وب‌هوک (اختیاری)" value={str("telegram_webhook_secret")} onChange={(v) => set("telegram_webhook_secret", v)} dir="ltr" type="password" />
            <p className="text-xs text-muted-foreground">
              آدرس وب‌هوک را در BotFather/Telegram با متد setWebhook روی مسیر{" "}
              <code dir="ltr">/api/v1/chat/telegram/webhook</code> تنظیم کنید.
            </p>
          </Card>

          <Card className="space-y-4 p-6">
            <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
              <Settings className="h-4 w-4" /> رفتار
            </h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <NumField label="مدت انتقال به انسان (دقیقه)" value={num("handoff_duration")} onChange={(v) => set("handoff_duration", v)} min={1} />
              <NumField label="حذف خودکار چت پس از (روز)" value={num("auto_delete_days")} onChange={(v) => set("auto_delete_days", v)} min={0} />
            </div>
          </Card>
        </div>
      </TabsContent>

      {/* ── Monitoring ── */}
      <TabsContent value="monitoring">
        <Card className="space-y-4 p-6">
          <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
            <Activity className="h-4 w-4" /> اطلاعات نمایشی کاربران آنلاین
          </h2>
          <p className="text-sm text-muted-foreground">
            انتخاب کنید کدام اطلاعات در کارت‌های لایو نمایش داده شود:
          </p>
          {ONLINE_FIELDS.map((f) => (
            <label key={f.key} className="flex cursor-pointer items-center gap-3 rounded-lg border p-3 hover:bg-muted/50">
              <input
                type="checkbox"
                checked={onlineShow.includes(f.key)}
                onChange={(e) => {
                  const next = e.target.checked
                    ? [...onlineShow, f.key]
                    : onlineShow.filter((k) => k !== f.key);
                  set("online_show_fields", next);
                }}
                className="h-4 w-4 rounded accent-primary"
              />
              <span className="flex items-center gap-1.5 text-sm font-medium">
                <f.Icon className="h-4 w-4" />
                {f.label}
              </span>
            </label>
          ))}
        </Card>
      </TabsContent>

      {/* ── Logos ── */}
      <TabsContent value="logos">
        <Card className="space-y-6 p-6">
          <h2 className="flex items-center gap-1.5 border-b pb-2 text-base font-bold">
            <ImageIcon className="h-4 w-4" /> لوگو و آواتارها
          </h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
            <ImageField label="آیکن دکمه ویجت" value={str("widget_icon_url")} onChange={(v) => set("widget_icon_url", v)} />
            <ImageField label="آواتار کاربر" value={str("user_avatar_url")} onChange={(v) => set("user_avatar_url", v)} />
            <ImageField label="آواتار هوش مصنوعی" value={str("ai_avatar_url")} onChange={(v) => set("ai_avatar_url", v)} />
            <ImageField label="آواتار پشتیبان (انسان)" value={str("admin_avatar_url")} onChange={(v) => set("admin_avatar_url", v)} />
          </div>
        </Card>
      </TabsContent>

      <Button onClick={() => void onSave()} disabled={saving} className="w-full">
        {saving ? <Loader2 className="me-2 h-4 w-4 animate-spin" /> : <Save className="me-2 h-4 w-4" />}
        ذخیرهٔ تنظیمات
      </Button>
    </Tabs>
  );
}

function TextField({
  label,
  value,
  onChange,
  dir,
  type,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  dir?: string;
  type?: string;
  placeholder?: string;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="block text-sm font-semibold">{label}</Label>
      <Input value={value} onChange={(e) => onChange(e.target.value)} dir={dir} type={type} placeholder={placeholder} />
    </div>
  );
}

function NumField({
  label,
  value,
  onChange,
  min,
  max,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  min?: number;
  max?: number;
}) {
  return (
    <div className="space-y-1.5">
      <Label className="block text-sm font-semibold">{label}</Label>
      <Input type="number" value={value} min={min} max={max} onChange={(e) => onChange(Number(e.target.value))} />
    </div>
  );
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div className="space-y-1.5">
      <Label className="block text-sm font-semibold">{label}</Label>
      <div className="flex items-center gap-2">
        <input type="color" value={value || "#000000"} onChange={(e) => onChange(e.target.value)} className="h-10 w-12 rounded border p-1" />
        <Input value={value} onChange={(e) => onChange(e.target.value)} dir="ltr" className="h-10 flex-1" />
      </div>
    </div>
  );
}
