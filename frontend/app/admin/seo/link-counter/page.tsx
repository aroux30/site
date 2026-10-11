"use client";

/**
 * Link counter (Rank Math's Link Counter): per-post internal/external link
 * counts, the orphan list (posts with no internal link), and the distinct
 * external hosts so a dead domain used across many posts is visible once.
 *
 * Counts are computed server-side from the stored bodies — this page renders
 * what the API reports and never recounts client-side (a second
 * implementation would drift from the one the operator's decisions rest on).
 */

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ExternalLink, Link2, Loader2, RefreshCw } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import { fetchLinkCounter, type LinkCounterResult } from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

export default function LinkCounterPage() {
  const { toast } = useToast();
  const [data, setData] = useState<LinkCounterResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [orphansOnly, setOrphansOnly] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = useCallback(
    async (orphans: boolean) => {
      setLoading(true);
      try {
        const result = await fetchLinkCounter({ orphans_only: orphans, page_size: 100 });
        setData(result);
      } catch {
        toast({ title: "دریافت شمارش لینک‌ها ناموفق بود", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void load(orphansOnly);
  }, [load, orphansOnly]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold">
            <Link2 className="h-5 w-5 text-primary" />
            شمارش لینک‌ها
          </h1>
          <p className="mt-1 text-xs text-muted-foreground">
            لینک‌های داخلی و خارجی هر نوشته؛ نوشتهٔ بدون لینک داخلی «یتیم» علامت می‌خورد.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs cursor-pointer">
            <input
              type="checkbox"
              checked={orphansOnly}
              onChange={(e) => setOrphansOnly(e.target.checked)}
              className="h-4 w-4 rounded border-input"
            />
            فقط نوشته‌های یتیم
          </label>
          <Button variant="outline" size="sm" onClick={() => void load(orphansOnly)}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
        </div>
      </div>

      {data && (
        <div className="grid gap-4 sm:grid-cols-3">
          <Card className="p-4">
            <div className="text-xs text-muted-foreground">نوشته‌های بررسی‌شده</div>
            <div className="mt-1 text-2xl font-black tabular-nums">
              {toPersianDigits(String(data.total))}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-xs text-muted-foreground">نوشته‌های یتیم (بدون لینک داخلی)</div>
            <div
              className={`mt-1 text-2xl font-black tabular-nums ${
                data.orphan_count > 0 ? "text-amber-600" : "text-emerald-600"
              }`}
            >
              {toPersianDigits(String(data.orphan_count))}
            </div>
          </Card>
          <Card className="p-4">
            <div className="text-xs text-muted-foreground">دامنه‌های خارجی یکتا</div>
            <div className="mt-1 text-2xl font-black tabular-nums">
              {toPersianDigits(String(data.external_hosts.length))}
            </div>
          </Card>
        </div>
      )}

      <Card className="p-6">
        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : !data || data.items.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            {orphansOnly ? "نوشتهٔ یتیمی پیدا نشد" : "نوشته‌ای برای بررسی نیست"}
          </p>
        ) : (
          <div className="space-y-2">
            {data.items.map((item) => (
              <div key={item.post_id} className="rounded-lg border p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    {item.is_orphan && (
                      <Badge variant="outline" className="border-amber-500 text-amber-700 shrink-0">
                        یتیم
                      </Badge>
                    )}
                    <Link
                      href={`/blog/${item.slug}`}
                      target="_blank"
                      className="truncate text-sm font-medium hover:text-primary"
                      title={item.title}
                    >
                      {item.title}
                    </Link>
                  </div>
                  <div className="flex items-center gap-3 text-xs shrink-0">
                    <span className="text-muted-foreground">
                      داخلی: <b className="text-foreground">{toPersianDigits(String(item.internal))}</b>
                    </span>
                    <span className="text-muted-foreground">
                      خارجی: <b className="text-foreground">{toPersianDigits(String(item.external))}</b>
                    </span>
                    {item.external > 0 && (
                      <button
                        type="button"
                        onClick={() =>
                          setExpanded(expanded === item.post_id ? null : item.post_id)
                        }
                        className="flex items-center gap-1 text-primary hover:underline"
                      >
                        <ExternalLink className="h-3 w-3" />
                        دامنه‌ها
                      </button>
                    )}
                  </div>
                </div>
                {expanded === item.post_id && (
                  <ul dir="ltr" className="mt-2 space-y-1 border-t border-border pt-2">
                    {item.external_urls.map((url) => (
                      <li key={url} className="truncate text-[11px] text-muted-foreground">
                        <a
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer nofollow"
                          className="hover:text-foreground hover:underline"
                        >
                          {url}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
