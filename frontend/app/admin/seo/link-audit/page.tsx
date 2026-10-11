"use client";

/**
 * Broken-link crawler (Rank Math Pro's Link Genius "Audit").
 *
 * Lists every URL the site links to with its HTTP verdict, grouped by
 * severity (broken first). "بررسی کن" runs the crawler now; the nightly task
 * checks the rest. A URL that blocks bots but works in a browser (403,
 * paywall) can be marked safe and hidden without deleting its row.
 *
 * Destructive/irreversible actions use the in-app confirm dialog, never
 * `window.confirm` (a silent no-op in a sandboxed iframe — see
 * confirm-dialog.tsx).
 */

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ExternalLink,
  Link2,
  Loader2,
  RefreshCw,
  ShieldCheck,
  Trash2,
} from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  clearLinkAudit,
  fetchLinkAudit,
  markLinkSafe,
  runLinkAudit,
  type LinkAuditCategory,
  type LinkAuditList,
} from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

const CATEGORY_LABELS: Record<LinkAuditCategory, string> = {
  broken: "خراب",
  error: "خطا",
  timeout: "بی‌پاسخ",
  redirect: "ریدایرکت",
  blocked: "مسدود (امنیتی)",
  ok: "سالم",
};

const CATEGORY_CLASSES: Record<LinkAuditCategory, string> = {
  broken: "border-destructive text-destructive",
  error: "border-destructive/60 text-destructive/90",
  timeout: "border-amber-500 text-amber-700",
  redirect: "border-sky-500 text-sky-700",
  blocked: "border-muted-foreground/40 text-muted-foreground",
  ok: "border-emerald-500 text-emerald-700",
};

export default function LinkAuditPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const [data, setData] = useState<LinkAuditList | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [filter, setFilter] = useState<LinkAuditCategory | "">("");

  const load = useCallback(
    async (category: LinkAuditCategory | "") => {
      setLoading(true);
      try {
        const res = await fetchLinkAudit({
          category: category || undefined,
          page_size: 100,
        });
        setData(res);
      } catch {
        toast({ title: "دریافت نتایج بررسی لینک‌ها ناموفق بود", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void load(filter);
  }, [load, filter]);

  const handleRun = useCallback(async () => {
    setRunning(true);
    try {
      const res = await runLinkAudit({ force: true, batch_size: 50 });
      toast({
        title: `${toPersianDigits(String(res.checked))} لینک بررسی شد؛ ${toPersianDigits(
          String(res.broken),
        )} خراب`,
      });
      await load(filter);
    } catch {
      toast({ title: "اجرای بررسی ناموفق بود", variant: "destructive" });
    } finally {
      setRunning(false);
    }
  }, [load, filter, toast]);

  const handleMarkSafe = useCallback(
    async (id: string) => {
      try {
        await markLinkSafe(id, true);
        toast({ title: "به‌عنوان سالم علامت خورد" });
        await load(filter);
      } catch {
        toast({ title: "ثبت ناموفق بود", variant: "destructive" });
      }
    },
    [load, filter, toast],
  );

  const handleClear = useCallback(async () => {
    const ok = await confirm({
      title: "پاک کردن نتایج بررسی",
      description: "همهٔ نتایج بررسی لینک‌ها حذف می‌شود. با اجرای بعدی دوباره ساخته می‌شوند.",
      confirmLabel: "پاک کن",
      destructive: true,
    });
    if (!ok) return;
    try {
      await clearLinkAudit();
      toast({ title: "نتایج پاک شد" });
      await load(filter);
    } catch {
      toast({ title: "پاک کردن ناموفق بود", variant: "destructive" });
    }
  }, [confirm, load, filter, toast]);

  const counts = data?.counts ?? {};
  const brokenTotal = (counts.broken ?? 0) + (counts.error ?? 0) + (counts.timeout ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Link2 className="h-5 w-5 text-primary" />
            بررسی لینک‌های شکسته
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            همهٔ لینک‌های سایت بررسی می‌شوند؛ لینک‌های خراب، بی‌پاسخ و ریدایرکت‌شده
            جداگانه نمایش داده می‌شوند. لینک‌های مسدودشده هرگز واکشی نمی‌شوند.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button size="sm" onClick={() => void handleRun()} disabled={running}>
            {running ? (
              <Loader2 className="h-4 w-4 animate-spin ms-2" />
            ) : (
              <RefreshCw className="h-4 w-4 ms-2" />
            )}
            بررسی کن
          </Button>
          <Button size="sm" variant="ghost" onClick={() => void handleClear()}>
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-4">
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">لینک‌های خراب (خراب+خطا+بی‌پاسخ)</div>
          <div
            className={`mt-1 text-2xl font-black tabular-nums ${
              brokenTotal > 0 ? "text-destructive" : "text-emerald-600"
            }`}
          >
            {toPersianDigits(String(brokenTotal))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">ریدایرکت</div>
          <div className="mt-1 text-2xl font-black tabular-nums text-sky-600">
            {toPersianDigits(String(counts.redirect ?? 0))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">سالم</div>
          <div className="mt-1 text-2xl font-black tabular-nums text-emerald-600">
            {toPersianDigits(String(counts.ok ?? 0))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="text-xs text-muted-foreground">مسدود (امنیتی)</div>
          <div className="mt-1 text-2xl font-black tabular-nums text-muted-foreground">
            {toPersianDigits(String(counts.blocked ?? 0))}
          </div>
        </Card>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button
          size="sm"
          variant={filter === "" ? "default" : "outline"}
          onClick={() => setFilter("")}
        >
          همه
        </Button>
        {(["broken", "error", "timeout", "redirect", "ok"] as const).map((cat) => (
          <Button
            key={cat}
            size="sm"
            variant={filter === cat ? "default" : "outline"}
            onClick={() => setFilter(cat)}
          >
            {CATEGORY_LABELS[cat]}
          </Button>
        ))}
      </div>

      <Card className="p-6">
        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            نتیجه‌ای برای نمایش نیست — «بررسی کن» را بزنید
          </p>
        ) : (
          <div className="space-y-2">
            {data.items.map((item) => (
              <div key={item.id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex min-w-0 items-center gap-2">
                    <Badge
                      variant="outline"
                      className={`shrink-0 ${CATEGORY_CLASSES[item.category]}`}
                    >
                      {CATEGORY_LABELS[item.category]}
                    </Badge>
                    {item.http_status !== null && (
                      <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
                        {toPersianDigits(String(item.http_status))}
                      </span>
                    )}
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer nofollow"
                      dir="ltr"
                      className="flex min-w-0 items-center gap-1 truncate text-xs text-foreground hover:text-primary"
                      title={item.url}
                    >
                      <ExternalLink className="h-3 w-3 shrink-0" />
                      {item.url}
                    </a>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => void handleMarkSafe(item.id)}
                    title="این لینک را نادیده بگیر"
                  >
                    <ShieldCheck className="h-4 w-4" />
                  </Button>
                </div>
                {item.detail && (
                  <div className="mt-1 truncate text-[11px] text-muted-foreground">
                    {item.detail}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      <p className="flex items-center gap-1 text-[11px] text-muted-foreground">
        {brokenTotal === 0 ? (
          <>
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            هیچ لینک شکسته‌ای یافت نشد
          </>
        ) : (
          <>
            <AlertTriangle className="h-3.5 w-3.5 text-destructive" />
            {toPersianDigits(String(brokenTotal))} لینک نیازمند اصلاح است
          </>
        )}
      </p>
    </div>
  );
}
