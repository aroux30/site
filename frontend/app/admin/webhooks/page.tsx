"use client";

import React, { useState } from "react";
import { PlugZap, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  webhooksApi,
  type WebhookDelivery,
  type WebhookEndpoint,
} from "@/lib/api/cms-admin";
import { toPersianDigits } from "@/lib/utils";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const WEBHOOKS_QUERY_KEY = "admin-webhooks" as const;

export default function AdminWebhooksPage() {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [editingEp, setEditingEp] = useState<WebhookEndpoint | null>(null);
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [secret, setSecret] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const [deliveryFilter, setDeliveryFilter] = useState<string>("all");
  const [expandedDelivery, setExpandedDelivery] = useState<string | null>(null);
  const [busyEp, setBusyEp] = useState<string | null>(null);

  // Three reads in one query, all settled independently — matching the old
  // Promise.allSettled, so a deliveries outage still shows the endpoint list.
  //
  // The delivery filter belongs in the key. The previous code had it in the
  // effect's deps but NOT in the useCallback's, so changing the filter
  // refetched with the previous filter's value — a stale-results bug that a
  // keyed query cannot express.
  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [WEBHOOKS_QUERY_KEY, deliveryFilter],
    queryFn: async () => {
      const [eps, dls, evs] = await Promise.allSettled([
        webhooksApi.list(),
        webhooksApi.deliveries({
          status: deliveryFilter === "all" ? undefined : deliveryFilter,
        }),
        webhooksApi.listEvents(),
      ]);
      return {
        endpoints: eps.status === "fulfilled" ? eps.value : [],
        deliveries: dls.status === "fulfilled" ? dls.value : [],
        events: evs.status === "fulfilled" ? evs.value : [],
      };
    },
    fallbackError: "بارگذاری وبهوکها ناموفق بود",
  });
  const endpoints: WebhookEndpoint[] = data?.endpoints ?? [];
  const deliveries: WebhookDelivery[] = data?.deliveries ?? [];
  const events: string[] = data?.events ?? [];
  const runMutation = useAdminMutation();

  const toggleEvent = (ev: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(ev)) next.delete(ev);
      else next.add(ev);
      return next;
    });
  };

  const openCreate = () => {
    setEditingEp(null);
    setName(""); setUrl(""); setSecret(""); setSelected(new Set());
    setOpen(true);
  };

  const openEdit = (ep: WebhookEndpoint) => {
    setEditingEp(ep);
    setName(ep.name);
    setUrl(ep.url);
    setSecret("");
    setSelected(new Set(ep.events));
    setOpen(true);
  };

  const create = async () => {
    if (!name.trim() || !url.trim() || selected.size === 0) {
      toast({ title: "خطا", description: "نام، نشانی و حداقل یک رویداد الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      if (editingEp) {
        await webhooksApi.update(editingEp.id, {
          name: name.trim(),
          url: url.trim(),
          events: [...selected],
          ...(secret.trim() ? { secret: secret.trim() } : {}),
        });
        toast({ title: "موفق", description: "وب‌هوک به‌روزرسانی شد" });
      } else {
        await webhooksApi.create({
          name: name.trim(),
          url: url.trim(),
          events: [...selected],
          secret: secret.trim() || undefined,
        });
        toast({ title: "موفق", description: "وب‌هوک ایجاد شد" });
      }
      setOpen(false);
      void load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { error?: { message?: string }; detail?: string } } })?.response?.data;
      toast({
        title: "خطا",
        description: detail?.error?.message ?? detail?.detail ?? "ذخیره وب‌هوک ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const testEndpoint = async (ep: WebhookEndpoint) => {
    setBusyEp(ep.id);
    try {
      const d = await webhooksApi.test(ep.id);
      if (d.status === "success") {
        toast({ title: "تست موفق", description: `پاسخ HTTP ${toPersianDigits(String(d.response_status ?? 0))} دریافت شد` });
      } else {
        toast({
          title: "تست ناموفق",
          description: d.last_error ?? "مقصد پاسخ معتبری نداد",
          variant: "destructive",
        });
      }
      void load();
    } catch {
      toast({ title: "خطا", description: "ارسال تست ناموفق بود", variant: "destructive" });
    } finally {
      setBusyEp(null);
    }
  };

  const rotateSecret = async (ep: WebhookEndpoint) => {
    if (!confirm(`کلید امضای «${ep.name}» چرخش کند؟ کلید قبلی بی‌اعتبار می‌شود.`)) return;
    setBusyEp(ep.id);
    try {
      const res = await webhooksApi.rotateSecret(ep.id);
      await navigator.clipboard?.writeText(res.secret).catch(() => undefined);
      toast({
        title: "کلید جدید ساخته شد (کپی شد)",
        description: res.secret.slice(0, 16) + "…",
      });
      void load();
    } catch {
      toast({ title: "خطا", description: "چرخش کلید ناموفق بود", variant: "destructive" });
    } finally {
      setBusyEp(null);
    }
  };

  const remove = async (id: string) => {
    if (!confirm("این وب‌هوک حذف شود؟")) return;
    try {
      await webhooksApi.remove(id);
      void load();
    } catch {
      toast({ title: "خطا", description: "حذف ناموفق بود", variant: "destructive" });
    }
  };

  const toggleActive = async (ep: WebhookEndpoint) => {
    try {
      await webhooksApi.update(ep.id, { is_active: !ep.is_active });
      void load();
    } catch {
      toast({ title: "خطا", description: "تغییر وضعیت ناموفق بود", variant: "destructive" });
    }
  };

  const statusBadge = (s: WebhookDelivery["status"]) =>
    s === "success"
      ? "bg-emerald-500/10 text-emerald-500"
      : s === "failed"
        ? "bg-red-500/10 text-red-500"
        : "bg-amber-500/10 text-amber-500";

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <PlugZap className="h-5 w-5 text-primary" />
            وب‌هوک‌های خروجی
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            اعلان رویدادهای محتوا به سیستم‌های بیرونی با امضای HMAC و تلاش مجدد خودکار
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 ms-1" />
            وب‌هوک جدید
          </Button>
        </div>
      </div>

      <Card className="p-6">
        <h3 className="text-lg font-semibold mb-4">نقاط پایانی</h3>
        {loading ? (
          <div className="flex justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : endpoints.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            هنوز وب‌هوکی تعریف نشده است
          </p>
        ) : (
          <div className="space-y-2">
            {endpoints.map((ep) => (
              <div key={ep.id} className="flex items-center justify-between rounded-lg border p-3">
                <div>
                  <p className="font-medium text-sm">{ep.name}</p>
                  <p className="text-xs text-muted-foreground font-mono" dir="ltr">{ep.url}</p>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {ep.events.map((e) => (
                      <Badge key={e} variant="outline" className="text-[10px]">{e}</Badge>
                    ))}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <Button
                    size="sm"
                    variant={ep.is_active ? "default" : "outline"}
                    onClick={() => toggleActive(ep)}
                  >
                    {ep.is_active ? "فعال" : "غیرفعال"}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busyEp === ep.id}
                    onClick={() => testEndpoint(ep)}
                    title="ارسال یک تحویل تستی و نمایش نتیجه واقعی"
                  >
                    {busyEp === ep.id ? "..." : "تست"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(ep)}>
                    ویرایش
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={busyEp === ep.id}
                    onClick={() => rotateSecret(ep)}
                    title="ساخت کلید امضای جدید (یک‌بار نمایش داده می‌شود)"
                  >
                    چرخش کلید
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(ep.id)}
                    // Icon-only: without a name a screen reader announces just
                    // "button", and a test can only reach it by position —
                    // which broke whenever the row re-rendered mid-flow.
                    aria-label={`حذف وب‌هوک ${ep.name}`}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="p-6">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">تحویل‌های اخیر</h3>
          <select
            value={deliveryFilter}
            onChange={(e) => setDeliveryFilter(e.target.value)}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs"
            aria-label="فیلتر وضعیت تحویل"
          >
            <option value="all">همه وضعیت‌ها</option>
            <option value="success">موفق</option>
            <option value="pending">در صف</option>
            <option value="failed">ناموفق</option>
          </select>
        </div>
        {deliveries.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-6">تحویلی ثبت نشده است</p>
        ) : (
          <div className="space-y-2 max-h-80 overflow-y-auto">
            {deliveries.map((d) => (
              <div key={d.id} className="rounded-lg border p-3">
                <button
                  className="flex w-full items-center justify-between text-right"
                  onClick={() => setExpandedDelivery(expandedDelivery === d.id ? null : d.id)}
                >
                  <div>
                    <p className="text-sm font-medium" dir="ltr">{d.event}</p>
                    {d.created_at && (
                      <p className="text-[10px] text-muted-foreground">
                        {toPersianDigits(new Date(d.created_at).toLocaleString("fa-IR"))}
                      </p>
                    )}
                    {d.last_error && (
                      <p className="text-xs text-destructive mt-1" dir="ltr">{d.last_error}</p>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">
                      تلاش {toPersianDigits(String(d.attempts))}
                      {d.response_status ? ` · HTTP ${toPersianDigits(String(d.response_status))}` : ""}
                    </span>
                    <Badge className={statusBadge(d.status)}>
                      {d.status === "success" ? "موفق" : d.status === "failed" ? "ناموفق" : "در صف"}
                    </Badge>
                  </div>
                </button>
                {expandedDelivery === d.id && (
                  <div className="mt-2 space-y-1.5 border-t pt-2 text-xs">
                    {d.status === "pending" && d.next_attempt_at && (
                      <p className="text-muted-foreground">
                        تلاش بعدی:{" "}
                        {toPersianDigits(new Date(d.next_attempt_at).toLocaleString("fa-IR"))}
                      </p>
                    )}
                    {d.delivered_at && (
                      <p className="text-muted-foreground">
                        تحویل:{" "}
                        {toPersianDigits(new Date(d.delivered_at).toLocaleString("fa-IR"))}
                      </p>
                    )}
                    {d.payload && (
                      <pre dir="ltr" className="max-h-48 overflow-auto rounded bg-muted/50 p-2 font-mono text-[11px]">
                        {JSON.stringify(d.payload, null, 2)}
                      </pre>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingEp ? "ویرایش وب‌هوک" : "وب‌هوک جدید"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="wh-name">نام</Label>
              <Input id="wh-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="اطلاع‌رسانی انبار" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wh-url">نشانی مقصد</Label>
              <Input id="wh-url" dir="ltr" value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://example.com/hook" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="wh-secret">{editingEp ? "رمز امضا (خالی = بدون تغییر)" : "رمز امضا (اختیاری — HMAC-SHA256)"}</Label>
              <Input id="wh-secret" dir="ltr" type="password" value={secret} onChange={(e) => setSecret(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>رویدادها</Label>
              <div className="flex flex-wrap gap-1">
                {events.map((ev) => (
                  <Button
                    key={ev}
                    type="button"
                    size="sm"
                    variant={selected.has(ev) ? "default" : "outline"}
                    className="h-7 text-xs"
                    onClick={() => toggleEvent(ev)}
                  >
                    {ev}
                  </Button>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>انصراف</Button>
            <Button onClick={create} disabled={saving}>
              {saving ? "در حال ذخیره..." : editingEp ? "به‌روزرسانی" : "ایجاد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
