"use client";

/**
 * Newsletter admin (خبرنامه).
 *
 * Two tabs over one module: the double-opt-in subscriber lifecycle (list with
 * per-status totals, CSV export, lookup-by-address, GDPR erasure) and the
 * campaign mailout surface (draft → schedule → send → per-recipient delivery).
 * The public subscribe flow runs end-to-end from the storefront.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Download,
  Loader2,
  Mail,
  RefreshCw,
  Search,
  Trash2,
  UserCheck,
  Users,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { CampaignsTab } from "@/components/admin/newsletter/campaigns-tab";
import { useToast } from "@/components/ui/use-toast";
import {
  newsletterApi,
  type NewsletterSubscriber,
  type SubscriberListResponse,
} from "@/lib/api/newsletter";
import { toPersianDigits } from "@/lib/utils";

const STATUS_LABELS: Record<NewsletterSubscriber["status"], string> = {
  pending: "در انتظار تأیید",
  subscribed: "عضو",
  unsubscribed: "لغو شده",
};

const PAGE_SIZE = 20;

function SubscribersTab() {
  const { toast } = useToast();
  const [email, setEmail] = useState("");
  const [subscriber, setSubscriber] = useState<NewsletterSubscriber | null>(null);
  const [loading, setLoading] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [list, setList] = useState<SubscriberListResponse | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string | null>(null);
  const [page, setPage] = useState(1);

  const loadList = useCallback(
    async (targetPage: number) => {
      setListLoading(true);
      setListError(null);
      try {
        setList(await newsletterApi.adminList(targetPage, PAGE_SIZE));
      } catch {
        // A failed read must not render as "no subscribers" — that reads as
        // a claim about the list, which an outage cannot support.
        setListError("بارگذاری فهرست مشترکان ناموفق بود.");
      } finally {
        setListLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    void loadList(page);
  }, [loadList, page]);

  const lookup = useCallback(async () => {
    const address = email.trim().toLowerCase();
    if (!address) return;
    setLoading(true);
    setSubscriber(null);
    try {
      setSubscriber(await newsletterApi.adminGet(address));
    } catch {
      toast({ title: "مشترکی با این ایمیل یافت نشد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [email, toast]);

  const remove = useCallback(
    async (address: string) => {
      if (!confirm(`مشترک «${address}» حذف شود؟ این عملیات بازگشت‌پذیر نیست.`)) return;
      setDeleting(true);
      try {
        await newsletterApi.adminDelete(address);
        toast({ title: "مشترک حذف شد" });
        setSubscriber(null);
        setEmail("");
        await loadList(page);
      } catch {
        toast({ title: "حذف ناموفق بود", variant: "destructive" });
      } finally {
        setDeleting(false);
      }
    },
    [loadList, page, toast],
  );

  const totalPages = list ? Math.max(1, Math.ceil(list.total / PAGE_SIZE)) : 1;

  const columns: DataTableColumn<NewsletterSubscriber>[] = [
    {
      key: "email",
      header: "ایمیل",
      render: (row) => (
        <span className="font-mono text-xs" dir="ltr">
          {row.email}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (row) => (
        <Badge
          variant={row.status === "subscribed" ? "default" : "secondary"}
          className="text-[10px]"
        >
          {STATUS_LABELS[row.status]}
        </Badge>
      ),
    },
    {
      key: "source",
      header: "منبع",
      className: "text-xs text-muted-foreground",
      render: (row) => row.source,
      hideOnMobile: true,
    },
    {
      key: "created_at",
      header: "تاریخ عضویت",
      className: "text-xs",
      render: (row) => toPersianDigits(new Date(row.created_at).toLocaleDateString("fa-IR")),
    },
    {
      key: "actions",
      header: "",
      render: (row) => (
        <Button
          variant="ghost"
          size="sm"
          aria-label={`حذف ${row.email}`}
          onClick={(e) => {
            e.stopPropagation();
            void remove(row.email);
          }}
          disabled={deleting}
        >
          <Trash2 className="h-4 w-4 text-muted-foreground" />
        </Button>
      ),
    },
  ];

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2 text-xs">
          {list && (
            <>
              <Badge variant="secondary">کل: {toPersianDigits(String(list.total))}</Badge>
              <Badge variant="secondary">
                عضو: {toPersianDigits(String(list.status_counts.subscribed ?? 0))}
              </Badge>
              <Badge variant="secondary">
                در انتظار تأیید: {toPersianDigits(String(list.status_counts.pending ?? 0))}
              </Badge>
              <Badge variant="secondary">
                لغو شده: {toPersianDigits(String(list.status_counts.unsubscribed ?? 0))}
              </Badge>
            </>
          )}
        </div>
        <Button variant="outline" size="sm" onClick={() => void loadList(page)} disabled={listLoading}>
          <RefreshCw className={`h-4 w-4 ${listLoading ? "animate-spin" : ""}`} /> بروزرسانی
        </Button>
      </div>

      <DataTable
        columns={columns}
        rows={list?.items ?? []}
        rowKey={(row) => row.email}
        loading={listLoading}
        error={listError}
        emptyMessage="هنوز مشترکی ثبت نشده است"
        emptyDescription="پس از اولین ثبت‌نام از فوتر فروشگاه، مشترکان اینجا فهرست می‌شوند."
      />

      {list && list.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || listLoading}
          >
            قبلی
          </Button>
          <span className="text-muted-foreground">
            صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(totalPages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page >= totalPages || listLoading}
          >
            بعدی
          </Button>
        </div>
      )}

      <Card className="space-y-4 p-5">
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[240px] flex-1 space-y-1.5">
            <label className="text-xs font-medium" htmlFor="newsletter-lookup">
              جستجوی مشترک با ایمیل
            </label>
            <div className="flex gap-2">
              <Input
                id="newsletter-lookup"
                type="email"
                dir="ltr"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void lookup();
                }}
                placeholder="user@example.com"
                className="text-left text-xs"
              />
              <Button size="sm" onClick={() => void lookup()} disabled={loading}>
                {loading ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Search className="h-4 w-4" />
                )}
                جستجو
              </Button>
            </div>
          </div>
        </div>

        {subscriber && (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-muted/30 p-4">
            <div className="space-y-1">
              <div className="flex items-center gap-2">
                <UserCheck className="h-4 w-4 text-primary" />
                <span className="font-mono text-xs" dir="ltr">
                  {subscriber.email}
                </span>
                <Badge
                  variant={subscriber.status === "subscribed" ? "default" : "secondary"}
                  className="text-[10px]"
                >
                  {STATUS_LABELS[subscriber.status]}
                </Badge>
              </div>
              <p className="text-[11px] text-muted-foreground">
                منبع ثبت: {subscriber.source} · عضویت از{" "}
                {toPersianDigits(
                  new Date(subscriber.created_at).toLocaleDateString("fa-IR"),
                )}
              </p>
            </div>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void remove(subscriber.email)}
              disabled={deleting}
              className="gap-1.5"
            >
              {deleting ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5" />
              )}
              حذف (GDPR)
            </Button>
          </div>
        )}
      </Card>
    </>
  );
}

export default function NewsletterAdminPage() {
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">خبرنامه</h1>
          <p className="text-xs text-muted-foreground">
            عضویت دوعاملی: آدرس‌ها فقط پس از کلیک روی لینک ایمیلی عضو می‌شوند
          </p>
        </div>
        <Button variant="outline" size="sm" asChild>
          {/* Direct navigation: the backend sets Content-Disposition with a
              filename; streaming through axios would lose it. */}
          <a href={newsletterApi.exportCsvUrl()} download>
            <Download className="h-4 w-4" /> خروجی CSV
          </a>
        </Button>
      </div>

      <Tabs defaultValue="subscribers" className="space-y-4">
        <TabsList className="bg-card border border-border p-1">
          <TabsTrigger value="subscribers" className="gap-1.5 text-xs">
            <Users className="h-3.5 w-3.5" /> مشترکان
          </TabsTrigger>
          <TabsTrigger value="campaigns" className="gap-1.5 text-xs">
            <Mail className="h-3.5 w-3.5" /> کمپین‌ها
          </TabsTrigger>
        </TabsList>

        <TabsContent value="subscribers" className="space-y-4">
          <SubscribersTab />
        </TabsContent>
        <TabsContent value="campaigns" className="space-y-4">
          <CampaignsTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
