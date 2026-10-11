"use client";

/**
 * Instant Indexing card (Rank Math parity): IndexNow + Google.
 *
 * IndexNow is fully functional here — the key is generated server-side, the
 * public key file is served by the API, and enabling the toggle makes every
 * publish submit the new post automatically.
 *
 * Google is deliberately a status read, not an integration: its Indexing API
 * needs a service account (and covers only JobPosting/BroadcastEvent for
 * general sites), so the card says "not connected" honestly instead of
 * offering a button that would fail silently.
 */

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Copy, Loader2, Send, XCircle, Zap } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import {
  fetchIndexingStatus,
  submitToIndexNow,
  toggleIndexNow,
  type IndexingStatus,
} from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

export function IndexingSettingsCard() {
  const { toast } = useToast();
  const [status, setStatus] = useState<IndexingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [manualUrls, setManualUrls] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const load = useCallback(async () => {
    try {
      setStatus(await fetchIndexingStatus());
    } catch {
      toast({ title: "خواندن وضعیت ایندکس ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const toggle = async (enabled: boolean) => {
    setSaving(true);
    try {
      setStatus(await toggleIndexNow(enabled));
      toast({ title: enabled ? "ارسال خودکار فعال شد" : "ارسال خودکار غیرفعال شد" });
    } catch {
      toast({ title: "تغییر وضعیت ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const copyKeyPath = async () => {
    if (!status?.key_file_path) return;
    try {
      await navigator.clipboard.writeText(status.key_file_path);
      toast({ title: "آدرس فایل کلید کپی شد" });
    } catch {
      // Clipboard can be blocked; the value is visible on screen anyway.
    }
  };

  const submitManual = async () => {
    const urls = manualUrls
      .split("\n")
      .map((u) => u.trim())
      .filter(Boolean);
    if (urls.length === 0) {
      toast({ title: "آدرسی وارد نشده است", variant: "destructive" });
      return;
    }
    setSubmitting(true);
    try {
      const result = await submitToIndexNow(urls);
      const labels: Record<string, string> = {
        ok: `${toPersianDigits(String(result.submitted))} آدرس ارسال شد`,
        skipped: "ارسال غیرفعال است — اول فعالش کنید",
        rate_limited: "محدودیت نرخ — بعداً دوباره تلاش کنید",
        rejected: `رد شد: ${result.reason ?? ""}`,
        error: "خطای شبکه در ارسال",
      };
      toast({
        title: labels[result.status] ?? result.status,
        variant: result.status === "ok" ? undefined : "destructive",
      });
    } catch {
      toast({ title: "ارسال ناموفق بود", variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <Card className="flex items-center justify-center p-6">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Zap className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">ایندکس فوری</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        با فعال‌بودن، هر نوشتهٔ تازه‌منتشرشده بلافاصله به موتورهای جستجو (Bing و
        Yandex از طریق IndexNow) معرفی می‌شود.
      </p>

      {/* IndexNow section */}
      <div className="space-y-4 rounded-lg border border-border p-4">
        <label className="flex items-start gap-3 cursor-pointer">
          <input
            type="checkbox"
            checked={status?.indexnow_enabled ?? false}
            onChange={(e) => void toggle(e.target.checked)}
            disabled={saving}
            className="mt-1 h-4 w-4 rounded border-input"
          />
          <span>
            <span className="block text-sm font-medium">ارسال خودکار در انتشار (IndexNow)</span>
            <span className="block text-xs text-muted-foreground">
              Bing و Yandex از IndexNow مستقیماً استفاده می‌کنند.
            </span>
          </span>
        </label>

        {status?.key_file_path && (
          <div className="space-y-1">
            <div className="text-xs font-medium">فایل کلید (خودکار ساخته و سرو می‌شود)</div>
            <div className="flex items-center gap-2">
              <Input dir="ltr" readOnly value={status.key_file_path} className="text-[11px] font-mono" />
              <Button variant="outline" size="sm" onClick={() => void copyKeyPath()}>
                <Copy className="h-3.5 w-3.5" />
              </Button>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <div className="text-xs font-medium">ارسال دستی آدرس‌ها (هر خط یکی)</div>
          <textarea
            dir="ltr"
            value={manualUrls}
            onChange={(e) => setManualUrls(e.target.value)}
            rows={3}
            placeholder={"https://example.com/blog/post-1\nhttps://example.com/products/x"}
            className="w-full rounded-md border border-input bg-background p-2 font-mono text-[11px]"
          />
          <Button size="sm" onClick={() => void submitManual()} disabled={submitting}>
            {submitting ? (
              <Loader2 className="h-3.5 w-3.5 ms-1 animate-spin" />
            ) : (
              <Send className="h-3.5 w-3.5 ms-1" />
            )}
            ارسال به IndexNow
          </Button>
        </div>
      </div>

      {/* Google section — honest skeleton */}
      <div className="mt-4 flex items-start gap-3 rounded-lg border border-dashed border-border p-4">
        {status?.google.connected ? (
          <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
        ) : (
          <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <div>
          <div className="text-sm font-medium">
            Google Indexing API —{" "}
            {status?.google.connected ? "متصل" : "متصل نشده"}
          </div>
          <p className="mt-0.5 text-xs text-muted-foreground">{status?.google.note}</p>
        </div>
      </div>
    </Card>
  );
}

export default IndexingSettingsCard;
