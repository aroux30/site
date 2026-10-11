"use client";

/**
 * 404 Monitor — every not-found path the storefront answered, most-hit
 * first (Rank Math's "404 Monitor" panel).
 *
 * The one action that matters here is "turn this broken path into a
 * redirect": the row's redirect button pre-fills the redirect form with the
 * dead path, so fixing a broken link is two clicks instead of
 * copy-path → open redirects → paste.
 */

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertTriangle, FileSearch, Loader2, RefreshCw, Signpost, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  clearNotFoundLogs,
  deleteNotFoundLog,
  fetchNotFoundLogs,
  type NotFoundLog,
} from "@/lib/api/seo";
import { toPersianDigits } from "@/lib/utils";

export default function NotFoundMonitorPage() {
  const router = useRouter();
  const { toast } = useToast();
  const confirm = useConfirm();
  const [items, setItems] = useState<NotFoundLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const pageSize = 50;

  const load = useCallback(async (p: number, q: string) => {
    setLoading(true);
    setError(false);
    try {
      const data = await fetchNotFoundLogs({
        page: p,
        page_size: pageSize,
        search: q.trim() || undefined,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(page, search);
    // A search change resets to page 1 (page 5 of the old result set has no
    // meaning in the new one).
  }, [page, search, load]);

  const handleDelete = async (id: string) => {
    try {
      await deleteNotFoundLog(id);
      toast({ title: "رکورد ۴۰۴ حذف شد" });
      await load(page, search);
    } catch {
      toast({ title: "حذف ناموفق بود", variant: "destructive" });
    }
  };

  const handleClear = async () => {
    const ok = await confirm({
      title: "پاک‌سازی رکوردهای ۴۰۴",
      description: "همهٔ رکوردهای ۴۰۴ پاک شوند؟ این کار برگشت‌پذیر نیست.",
      confirmLabel: "پاک‌سازی",
      destructive: true,
    });
    if (!ok) return;
    try {
      const r = await clearNotFoundLogs();
      toast({ title: `${toPersianDigits(String(r.removed))} رکورد پاک شد` });
      await load(1, search);
      setPage(1);
    } catch {
      toast({ title: "پاک‌سازی ناموفق بود", variant: "destructive" });
    }
  };

  const goToRedirect = (path: string) => {
    router.push(`/admin/redirects?from=${encodeURIComponent(path)}`);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-black">مانیتور ۴۰۴</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            مسیرهایی که بازدیدکننده یا کرالر خواسته و پیدا نشده‌اند. پرتکرارها
            را به ریدایرکت تبدیل کنید تا اعتبار لینک از دست نرود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={() => void load(page, search)}>
            <RefreshCw className="h-3.5 w-3.5 ms-1" />
            بازخوانی
          </Button>
          {total > 0 && (
            <Button variant="outline" size="sm" className="text-destructive" onClick={() => void handleClear()}>
              <Trash2 className="h-3.5 w-3.5 ms-1" />
              پاک‌سازی همه
            </Button>
          )}
        </div>
      </div>

      <Input
        value={search}
        onChange={(e) => {
          setSearch(e.target.value);
          setPage(1);
        }}
        placeholder="جست‌وجو در مسیرها..."
        className="max-w-sm"
      />

      {loading ? (
        <div className="flex items-center justify-center gap-2 py-16 text-muted-foreground">
          <Loader2 className="h-5 w-5 animate-spin" />
          در حال خواندن...
        </div>
      ) : error ? (
        <div className="rounded-2xl border border-destructive/40 bg-destructive/5 p-6 text-sm">
          <p className="flex items-center gap-2 font-bold text-destructive">
            <AlertTriangle className="h-4 w-4" />
            خواندن رکوردهای ۴۰۴ ناموفق بود
          </p>
        </div>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-dashed border-border py-16 text-center">
          <FileSearch className="h-8 w-8 text-muted-foreground/50" />
          <p className="text-sm font-medium">
            {search ? "مسیری با این متن پیدا نشد." : "هیچ ۴۰۴ ثبت‌شده‌ای وجود ندارد."}
          </p>
          <p className="max-w-md text-xs text-muted-foreground">
            {search
              ? "عبارت جست‌وجو را تغییر دهید."
              : "وقتی بازدیدکننده یا کرالری به مسیر ناموجودی برسد، اینجا ثبت می‌شود."}
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-2xl border border-border">
            <table className="w-full text-sm">
              <thead className="bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-3 text-start font-medium">مسیر</th>
                  <th className="px-4 py-3 text-start font-medium">تعداد</th>
                  <th className="px-4 py-3 text-start font-medium">آخرین بازدید</th>
                  <th className="px-4 py-3 text-start font-medium">ارجاع‌دهنده</th>
                  <th className="px-4 py-3 text-start font-medium">عملیات</th>
                </tr>
              </thead>
              <tbody>
                {items.map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="max-w-[280px] px-4 py-3">
                      <span dir="ltr" className="block truncate font-mono text-xs" title={r.path}>
                        {r.path}
                      </span>
                      {r.user_agent && (
                        <span className="mt-0.5 block truncate text-[10px] text-muted-foreground" title={r.user_agent}>
                          {r.user_agent.includes("bot") || r.user_agent.includes("Bot")
                            ? "کرالر"
                            : "مرورگر"}
                          {" — "}
                          {r.user_agent.slice(0, 60)}
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant={r.hit_count >= 10 ? "destructive" : "outline"} className="tabular-nums">
                        {toPersianDigits(String(r.hit_count))}
                      </Badge>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-xs text-muted-foreground">
                      {new Date(r.last_seen_at).toLocaleDateString("fa-IR")}
                    </td>
                    <td className="max-w-[200px] px-4 py-3">
                      {r.referrer ? (
                        <span dir="ltr" className="block truncate font-mono text-[10px]" title={r.referrer}>
                          {r.referrer}
                        </span>
                      ) : (
                        <span className="text-xs text-muted-foreground">—</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          className="h-7 px-2 text-xs"
                          onClick={() => goToRedirect(r.path)}
                          title="ساخت ریدایرکت برای این مسیر"
                        >
                          <Signpost className="h-3.5 w-3.5 ms-1" />
                          ریدایرکت
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 px-2 text-xs text-muted-foreground hover:text-destructive"
                          onClick={() => void handleDelete(r.id)}
                          title="حذف رکورد"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm">
              <span className="text-muted-foreground">
                {toPersianDigits(String(total))} مسیر — صفحهٔ{" "}
                {toPersianDigits(String(page))} از {toPersianDigits(String(totalPages))}
              </span>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  قبلی
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  بعدی
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
