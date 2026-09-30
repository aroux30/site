"use client";

import React, { useState } from "react";
import {
  Webhook,
  RefreshCw,
  Plus,
  KeyRound,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Copy,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useToast } from "@/components/ui/use-toast";
import {
  inboundWebhooksApi,
  type InboundDelivery,
  type InboundDeliveryStatus,
  type InboundEndpoint,
} from "@/lib/api/inbound-webhooks";
import { toPersianDigits } from "@/lib/utils";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const ENDPOINTS_QUERY_KEY = "admin-inbound-webhooks" as const;

const STATUS_LABELS: Record<InboundDeliveryStatus, string> = {
  received: "دریافت شده",
  verified: "تایید امضا",
  rejected_signature: "امضای نامعتبر",
  rejected_duplicate: "تکراری",
  processed: "پردازش شده",
  failed: "ناموفق",
};

const STATUS_VARIANTS: Record<
  InboundDeliveryStatus,
  "default" | "secondary" | "destructive" | "outline"
> = {
  received: "secondary",
  verified: "default",
  rejected_signature: "destructive",
  rejected_duplicate: "outline",
  processed: "default",
  failed: "destructive",
};

export default function AdminInboundWebhooksPage() {
  const { toast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", ips: "" });
  const [secretDialog, setSecretDialog] = useState<{
    name: string;
    secret: string;
  } | null>(null);
  const [copied, setCopied] = useState(false);

  // Endpoints and deliveries are one fetch: the old page loaded them in a
  // single try/catch, so one failure must blank both, not just one.
  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [ENDPOINTS_QUERY_KEY],
    queryFn: async () => {
      const [eps, dels] = await Promise.all([
        inboundWebhooksApi.listEndpoints(),
        inboundWebhooksApi.listDeliveries({ limit: 100 }),
      ]);
      return { endpoints: eps, deliveries: dels };
    },
    fallbackError: "خطا در دریافت گیرنده‌های ورودی",
    // This page reported load failures as a toast; keep that behaviour.
    toastOnError: true,
  });
  const endpoints: InboundEndpoint[] = data?.endpoints ?? [];
  const deliveries: InboundDelivery[] = data?.deliveries ?? [];

  const runMutation = useAdminMutation();

  const create = async () => {
    if (!form.name.trim()) {
      toast({ title: "نام گیرنده الزامی است", variant: "destructive" });
      return;
    }
    const ips = form.ips
      .split(/[,\n]/)
      .map((s) => s.trim())
      .filter(Boolean);
    setCreating(true);
    const result = await runMutation(
      () =>
        inboundWebhooksApi.createEndpoint({
          name: form.name.trim(),
          description: form.description.trim() || null,
          ip_whitelist: ips.length ? ips : null,
        }),
      {
        fallbackError: "ایجاد گیرنده ناموفق بود",
        invalidateKeys: [[ENDPOINTS_QUERY_KEY]],
        onSuccess: (created) => {
          setCreateOpen(false);
          setForm({ name: "", description: "", ips: "" });
          setSecretDialog({ name: created.endpoint.name, secret: created.secret });
        },
      },
    );
    if (!result.ok) {
      toast({
        title: "ایجاد گیرنده ناموفق بود",
        description: "ممکن است نام تکراری باشد.",
        variant: "destructive",
      });
    }
    setCreating(false);
  };

  const rotate = async (endpoint: InboundEndpoint) => {
    const result = await runMutation(() => inboundWebhooksApi.rotateSecret(endpoint.id), {
      fallbackError: "چرخش راز ناموفق بود",
      invalidateKeys: [[ENDPOINTS_QUERY_KEY]],
      onSuccess: (rotated) =>
        setSecretDialog({ name: rotated.endpoint.name, secret: rotated.secret }),
    });
    if (!result.ok) {
      toast({ title: result.error, variant: "destructive" });
    }
  };

  const copySecret = async () => {
    if (!secretDialog) return;
    try {
      await navigator.clipboard.writeText(secretDialog.secret);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast({ title: "کپی ناموفق بود — دستی کپی کنید", variant: "destructive" });
    }
  };

  const endpointColumns: DataTableColumn<InboundEndpoint>[] = [
    {
      key: "name",
      header: "گیرنده",
      render: (e) => (
        <div>
          <p className="font-medium" dir="ltr">
            {e.name}
          </p>
          {e.description && (
            <p className="text-xs text-muted-foreground">{e.description}</p>
          )}
        </div>
      ),
    },
    {
      key: "url",
      header: "آدرس دریافت",
      render: (e) => (
        <code className="rounded bg-muted px-2 py-1 text-[11px]" dir="ltr">
          POST /api/v1/integrations/inbound/{e.name}
        </code>
      ),
    },
    {
      key: "ips",
      header: "محدودیت IP",
      render: (e) =>
        e.ip_whitelist && e.ip_whitelist.length ? (
          <span className="font-mono text-[11px]" dir="ltr">
            {e.ip_whitelist.join(", ")}
          </span>
        ) : (
          <span className="text-xs text-muted-foreground">بدون محدودیت</span>
        ),
    },
    {
      key: "count",
      header: "دریافت‌ها",
      render: (e) => toPersianDigits(String(e.total_received)),
    },
    {
      key: "last",
      header: "آخرین دریافت",
      render: (e) =>
        e.last_received_at
          ? toPersianDigits(new Date(e.last_received_at).toLocaleString("fa-IR"))
          : "—",
    },
    {
      key: "actions",
      header: "",
      render: (e) => (
        <Button variant="outline" size="sm" onClick={() => rotate(e)}>
          <KeyRound className="ms-1.5 h-3.5 w-3.5" />
          چرخش راز
        </Button>
      ),
    },
  ];

  const deliveryColumns: DataTableColumn<InboundDelivery>[] = [
    {
      key: "status",
      header: "نتیجه",
      render: (d) => (
        <Badge variant={STATUS_VARIANTS[d.status]}>
          {d.status === "verified" || d.status === "processed" ? (
            <CheckCircle2 className="ms-1 h-3 w-3" />
          ) : d.status === "rejected_signature" || d.status === "failed" ? (
            <XCircle className="ms-1 h-3 w-3" />
          ) : null}
          {STATUS_LABELS[d.status]}
        </Badge>
      ),
    },
    {
      key: "event",
      header: "رویداد",
      render: (d) => (
        <span className="font-mono text-xs" dir="ltr">
          {d.event_type ?? "—"}
        </span>
      ),
    },
    {
      key: "key",
      header: "کلید idempotency",
      render: (d) => (
        <span className="font-mono text-[11px] text-muted-foreground" dir="ltr">
          {d.idempotency_key ?? "—"}
        </span>
      ),
    },
    {
      key: "ip",
      header: "منبع",
      render: (d) => (
        <span className="font-mono text-[11px]" dir="ltr">
          {d.source_ip ?? "—"}
        </span>
      ),
    },
    {
      key: "error",
      header: "خطا",
      render: (d) =>
        d.error ? (
          <span className="text-xs text-destructive" dir="ltr">
            {d.error}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "at",
      header: "زمان",
      render: (d) => toPersianDigits(new Date(d.received_at).toLocaleString("fa-IR")),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Webhook className="h-5 w-5 text-primary" />
            گیرنده‌های webhook ورودی
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            سیستم‌های بیرونی (نرم‌افزار حسابداری، پیام‌رسان، DMS) با امضای
            HMAC به این آدرس‌ها رویداد ارسال می‌کنند. تأیید امضا پیش از هر
            پردازش انجام می‌شود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="ms-2 h-4 w-4" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="ms-2 h-4 w-4" />
            گیرنده جدید
          </Button>
        </div>
      </div>

      <Card className="border-amber-500/30 bg-amber-500/5 p-4">
        <div className="flex items-start gap-2 text-xs text-muted-foreground">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
          <p>
            راز امضا فقط یک‌بار در زمان ساخت (یا چرخش) نمایش داده می‌شود و در
            سرور به‌صورت رمزنگاری‌شده نگهداری می‌گردد. امضا به شکل{" "}
            <code dir="ltr">X-Webhook-Signature: sha256=&lt;hex&gt;</code> روی
            بدنه خام درخواست محاسبه می‌شود.
          </p>
        </div>
      </Card>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
          گیرنده‌ها
        </h3>
        <Card className="p-1">
          <DataTable
            columns={endpointColumns}
            rows={endpoints}
            rowKey={(e) => e.id}
            loading={loading}
            emptyMessage="گیرنده‌ای تعریف نشده است"
            emptyDescription="با «گیرنده جدید» اولین سیستم بیرونی را وصل کنید."
          />
        </Card>
      </section>

      <section>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground">
          لاگ تحویل‌ها (۱۰۰ مورد آخر — شامل درخواست‌های ردشده)
        </h3>
        <Card className="p-1">
          <DataTable
            columns={deliveryColumns}
            rows={deliveries}
            rowKey={(d) => d.id}
            loading={loading}
            emptyMessage="تحویلی ثبت نشده است"
          />
        </Card>
      </section>

      {/* Create dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>گیرنده webhook جدید</DialogTitle>
            <DialogDescription>
              نام گیرنده بخشی از آدرس دریافت است و بعداً قابل تغییر نیست.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="iw-name">نام گیرنده (انگلیسی)</Label>
              <Input
                id="iw-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                placeholder="accounting_software"
                dir="ltr"
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="iw-desc">توضیح (اختیاری)</Label>
              <Input
                id="iw-desc"
                value={form.description}
                onChange={(e) => setForm((f) => ({ ...f, description: e.target.value }))}
                className="mt-1"
              />
            </div>
            <div>
              <Label htmlFor="iw-ips">
                محدودیت IP (اختیاری — هر خط یک آدرس یا CIDR)
              </Label>
              <textarea
                id="iw-ips"
                value={form.ips}
                onChange={(e) => setForm((f) => ({ ...f, ips: e.target.value }))}
                placeholder="10.0.0.0/8"
                dir="ltr"
                rows={3}
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono"
              />
              <p className="mt-1 text-[11px] text-muted-foreground">
                خالی بگذارید تا فقط امضا ملاک باشد. ورودی نامعتبر نادیده گرفته
                می‌شود، نه اینکه دسترسی را باز کند.
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              انصراف
            </Button>
            <Button onClick={create} disabled={creating}>
              {creating ? "در حال ایجاد..." : "ایجاد و نمایش راز"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* One-time secret dialog */}
      <Dialog
        open={secretDialog !== null}
        onOpenChange={(open) => {
          if (!open) {
            setSecretDialog(null);
            setCopied(false);
          }
        }}
      >
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>راز امضای گیرنده «{secretDialog?.name}»</DialogTitle>
            <DialogDescription>
              این مقدار فقط همین یک‌بار نمایش داده می‌شود. آن را در سیستم
              بیرونی ذخیره کنید؛ پس از بستن، بازیابی ممکن نیست (فقط چرخش).
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <code
                className="flex-1 break-all rounded-md bg-muted p-3 text-xs"
                dir="ltr"
              >
                {secretDialog?.secret}
              </code>
              <Button variant="outline" size="sm" onClick={copySecret}>
                {copied ? (
                  <Check className="h-4 w-4 text-emerald-600" />
                ) : (
                  <Copy className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="text-[11px] text-muted-foreground">
              در سیستم بیرونی:{" "}
              <code dir="ltr">
                sig = hmac_sha256(secret, raw_body) → &quot;sha256=&quot; + hex
              </code>
            </p>
          </div>
          <DialogFooter>
            <Button onClick={() => setSecretDialog(null)}>متوجه شدم</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
