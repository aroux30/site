"use client";

/**
 * Admin newsletter campaigns (کمپین‌های خبرنامه).
 *
 * The backend has shipped the full lifecycle — create, edit, schedule, send,
 * test-send, preview, per-recipient delivery status — since the campaigns
 * table landed, but nothing in the admin ever called it: subscribers were
 * collected and then silently ignored. This tab is that surface.
 *
 * The lifecycle is enforced server-side (`draft → scheduled → sending →
 * sent | failed`), so the buttons here are gated on `status` to match: only a
 * draft is editable or deletable, and a `sending` row is frozen because a
 * worker owns it.
 */

import { keepPreviousData } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import {
  CalendarClock,
  Eye,
  Loader2,
  Mail,
  Pencil,
  Plus,
  RefreshCw,
  Send,
  Trash2,
  Users,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import {
  newsletterCampaignsApi,
  type CampaignRecipient,
  type CampaignStatus,
  type NewsletterCampaign,
  type RecipientStatus,
} from "@/lib/api/newsletter-campaigns";
import { sanitizeHtml } from "@/lib/sanitize";
import { toPersianDigits } from "@/lib/utils";

const CAMPAIGNS_QUERY_KEY = "admin-newsletter-campaigns" as const;
const PAGE_SIZE = 20;

const STATUS_META: Record<CampaignStatus, { label: string; variant: "default" | "secondary" | "success" | "warning" | "destructive" | "info" }> = {
  draft: { label: "پیش‌نویس", variant: "secondary" },
  scheduled: { label: "زمان‌بندی‌شده", variant: "info" },
  sending: { label: "در حال ارسال", variant: "warning" },
  sent: { label: "ارسال‌شده", variant: "success" },
  failed: { label: "ناموفق", variant: "destructive" },
};

const RECIPIENT_STATUS_META: Record<RecipientStatus, { label: string; variant: "secondary" | "success" | "destructive" | "info" }> = {
  pending: { label: "در انتظار", variant: "secondary" },
  sent: { label: "ارسال‌شده", variant: "success" },
  failed: { label: "ناموفق", variant: "destructive" },
};

/** Persian-localised rendering; the server stores naive UTC timestamps. */
function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return toPersianDigits(parsed.toLocaleString("fa-IR"));
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "—";
  return toPersianDigits(parsed.toLocaleDateString("fa-IR"));
}

/** `datetime-local` yields a wall-clock string with no zone; make it explicit. */
function toIsoOrUndefined(local: string): string | undefined {
  if (!local) return undefined;
  const parsed = new Date(local);
  return Number.isNaN(parsed.getTime()) ? undefined : parsed.toISOString();
}

export function CampaignsTab() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();

  const [page, setPage] = useState(1);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<NewsletterCampaign | null>(null);
  const [saving, setSaving] = useState(false);

  const [formName, setFormName] = useState("");
  const [formSubject, setFormSubject] = useState("");
  const [formPreheader, setFormPreheader] = useState("");
  const [formBodyHtml, setFormBodyHtml] = useState("");
  const [formBodyText, setFormBodyText] = useState("");

  const [scheduleTarget, setScheduleTarget] = useState<NewsletterCampaign | null>(null);
  const [scheduleAt, setScheduleAt] = useState("");

  const [previewTarget, setPreviewTarget] = useState<NewsletterCampaign | null>(null);
  const [recipientsTarget, setRecipientsTarget] = useState<NewsletterCampaign | null>(null);

  const [testEmail, setTestEmail] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const {
    data: list,
    loading,
    error,
    reload,
  } = useAdminQuery({
    queryKey: [CAMPAIGNS_QUERY_KEY, page],
    queryFn: () => newsletterCampaignsApi.list(page, PAGE_SIZE),
    fallbackError: "بارگذاری کمپین‌ها ناموفق بود.",
    options: { placeholderData: keepPreviousData },
  });

  const resetEditor = useCallback(() => {
    setEditing(null);
    setFormName("");
    setFormSubject("");
    setFormPreheader("");
    setFormBodyHtml("");
    setFormBodyText("");
  }, []);

  const openCreate = useCallback(() => {
    resetEditor();
    setEditorOpen(true);
  }, [resetEditor]);

  const openEdit = useCallback((campaign: NewsletterCampaign) => {
    setEditing(campaign);
    setFormName(campaign.name);
    setFormSubject(campaign.subject);
    setFormPreheader(campaign.preheader ?? "");
    setFormBodyHtml(campaign.body_html);
    setFormBodyText(campaign.body_text ?? "");
    setEditorOpen(true);
  }, []);

  const save = useCallback(async () => {
    if (!formName.trim() || !formSubject.trim() || !formBodyHtml.trim()) {
      toast({
        title: "خطا",
        description: "نام، عنوان و محتوای کمپین الزامی است",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    const payload = {
      name: formName.trim(),
      subject: formSubject.trim(),
      body_html: formBodyHtml,
      ...(formPreheader.trim() ? { preheader: formPreheader.trim() } : {}),
      ...(formBodyText.trim() ? { body_text: formBodyText } : {}),
    };
    const result = editing
      ? await runMutation(() => newsletterCampaignsApi.update(editing.id, payload), {
          fallbackError: "ذخیره کمپین ناموفق بود",
          invalidateKeys: [[CAMPAIGNS_QUERY_KEY]],
        })
      : await runMutation(() => newsletterCampaignsApi.create(payload), {
          fallbackError: "ایجاد کمپین ناموفق بود",
          invalidateKeys: [[CAMPAIGNS_QUERY_KEY]],
        });
    setSaving(false);
    if (result.ok) {
      toast({ title: editing ? "کمپین ویرایش شد" : "کمپین پیش‌نویس ساخته شد" });
      setEditorOpen(false);
      resetEditor();
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  }, [editing, formBodyHtml, formBodyText, formName, formPreheader, formSubject, resetEditor, runMutation, toast]);

  const remove = useCallback(
    async (campaign: NewsletterCampaign) => {
      if (!confirm(`کمپین «${campaign.name}» و گیرنده‌های آن حذف شود؟`)) return;
      const result = await runMutation(() => newsletterCampaignsApi.remove(campaign.id), {
        fallbackError: "حذف کمپین ناموفق بود",
        invalidateKeys: [[CAMPAIGNS_QUERY_KEY]],
      });
      if (result.ok) toast({ title: "کمپین حذف شد" });
      else toast({ title: "خطا", description: result.error, variant: "destructive" });
    },
    [runMutation, toast],
  );

  const sendNow = useCallback(
    async (campaign: NewsletterCampaign) => {
      if (
        !confirm(
          `کمپین «${campaign.name}» همین حالا برای همه اعضای تأییدشده ارسال شود؟ این عملیات بازگشت‌پذیر نیست.`,
        )
      ) {
        return;
      }
      setBusyId(campaign.id);
      const result = await runMutation(() => newsletterCampaignsApi.send(campaign.id), {
        fallbackError: "ارسال کمپین ناموفق بود",
        invalidateKeys: [[CAMPAIGNS_QUERY_KEY]],
      });
      setBusyId(null);
      if (result.ok) {
        const { mode, total_recipients, total_sent, total_failed } = result.data;
        const detail =
          mode === "queued"
            ? `${toPersianDigits(total_recipients)} گیرنده در صف ارسال قرار گرفت.`
            : `${toPersianDigits(total_sent)} ارسال موفق، ${toPersianDigits(total_failed)} ناموفق از ${toPersianDigits(total_recipients)} گیرنده.`;
        toast({ title: "ارسال آغاز شد", description: detail });
      } else {
        toast({ title: "خطا", description: result.error, variant: "destructive" });
      }
    },
    [runMutation, toast],
  );

  const schedule = useCallback(async () => {
    if (!scheduleTarget) return;
    const iso = toIsoOrUndefined(scheduleAt);
    if (!iso) {
      toast({
        title: "خطا",
        description: "تاریخ و ساعت زمان‌بندی را انتخاب کنید",
        variant: "destructive",
      });
      return;
    }
    const result = await runMutation(
      () => newsletterCampaignsApi.schedule(scheduleTarget.id, iso),
      {
        fallbackError: "زمان‌بندی کمپین ناموفق بود",
        invalidateKeys: [[CAMPAIGNS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({ title: "کمپین زمان‌بندی شد", description: "ارسال در بازه یک دقیقه‌ای توسط زمان‌بند اجرا می‌شود." });
      setScheduleTarget(null);
      setScheduleAt("");
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  }, [runMutation, scheduleAt, scheduleTarget, toast]);

  const testSend = useCallback(async () => {
    if (!recipientsTarget) return;
    const address = testEmail.trim();
    if (!address) {
      toast({ title: "خطا", description: "ایمیل مقصد را وارد کنید", variant: "destructive" });
      return;
    }
    setBusyId(recipientsTarget.id);
    const result = await runMutation(
      () => newsletterCampaignsApi.testSend(recipientsTarget.id, address),
      { fallbackError: "ارسال ایمیل آزمایشی ناموفق بود" },
    );
    setBusyId(null);
    if (result.ok && result.data.sent) {
      toast({ title: "ایمیل آزمایشی ارسال شد", description: address });
      setTestEmail("");
    } else {
      toast({
        title: "ارسال آزمایشی انجام نشد",
        description: result.ok ? "سرویس ایمیل ارسال را تأیید نکرد." : result.error,
        variant: "destructive",
      });
    }
  }, [recipientsTarget, runMutation, testEmail, toast]);

  const totalPages = list ? Math.max(1, Math.ceil(list.total / PAGE_SIZE)) : 1;

  const columns: DataTableColumn<NewsletterCampaign>[] = [
    {
      key: "name",
      header: "نام",
      render: (row) => (
        <div className="space-y-0.5">
          <span className="text-sm font-medium">{row.name}</span>
          <span className="block text-[11px] text-muted-foreground">{row.subject}</span>
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (row) => (
        <Badge variant={STATUS_META[row.status].variant} className="text-[10px]">
          {STATUS_META[row.status].label}
        </Badge>
      ),
    },
    {
      key: "scheduled_at",
      header: "زمان‌بندی",
      className: "text-xs",
      render: (row) => {
        if (row.scheduled_at) {
          return (
            <span className="flex items-center gap-1">
              <CalendarClock className="h-3.5 w-3.5 text-muted-foreground" />
              {formatDateTime(row.scheduled_at)}
            </span>
          );
        }
        return (
          <span className="text-muted-foreground">
            {row.sent_at ? `ارسال: ${formatDate(row.sent_at)}` : "—"}
          </span>
        );
      },
      hideOnMobile: true,
    },
    {
      key: "counters",
      header: "گیرنده / ارسال",
      className: "text-xs",
      render: (row) => (
        <span className="whitespace-nowrap">
          {`${toPersianDigits(String(row.total_recipients))} / ${toPersianDigits(String(row.total_sent))}`}
          {row.total_failed > 0 && (
            <span className="text-destructive">
              {` · ${toPersianDigits(String(row.total_failed))} ناموفق`}
            </span>
          )}
        </span>
      ),
      hideOnMobile: true,
    },
    {
      key: "actions",
      header: "",
      render: (row) => {
        const busy = busyId === row.id;
        // The server only edits/deletes a draft; `sending` is owned by a worker.
        const editable = row.status === "draft";
        const sendable = row.status === "draft" || row.status === "scheduled" || row.status === "failed";
        return (
          <div className="flex items-center justify-end gap-1">
            <Button
              variant="ghost"
              size="sm"
              aria-label={`پیش‌نمایش ${row.name}`}
              onClick={(e) => {
                e.stopPropagation();
                setPreviewTarget(row);
              }}
            >
              <Eye className="h-4 w-4 text-muted-foreground" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              aria-label={`گیرنده‌های ${row.name}`}
              onClick={(e) => {
                e.stopPropagation();
                setRecipientsTarget(row);
                setTestEmail("");
              }}
            >
              <Users className="h-4 w-4 text-muted-foreground" />
            </Button>
            {editable && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`ویرایش ${row.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  openEdit(row);
                }}
              >
                <Pencil className="h-4 w-4 text-muted-foreground" />
              </Button>
            )}
            {sendable && (
              <>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  aria-label={`زمان‌بندی ${row.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    setScheduleTarget(row);
                    setScheduleAt("");
                  }}
                >
                  <CalendarClock className="h-4 w-4 text-muted-foreground" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={busy}
                  aria-label={`ارسال ${row.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    void sendNow(row);
                  }}
                >
                  {busy ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Send className="h-4 w-4 text-muted-foreground" />
                  )}
                </Button>
              </>
            )}
            {editable && (
              <Button
                variant="ghost"
                size="sm"
                aria-label={`حذف ${row.name}`}
                onClick={(e) => {
                  e.stopPropagation();
                  void remove(row);
                }}
              >
                <Trash2 className="h-4 w-4 text-destructive" />
              </Button>
            )}
          </div>
        );
      },
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-bold flex items-center gap-2">
            <Mail className="h-4 w-4 text-primary" />
            کمپین‌های خبرنامه
          </h2>
          <p className="text-xs text-muted-foreground">
            ارسال ایمیل به اعضای تأییدشده؛ فهرست لغو عضویت به‌صورت خودکار در انتهای هر ایمیل درج می‌شود.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> بروزرسانی
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4" /> کمپین جدید
          </Button>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={list?.items ?? []}
        rowKey={(row) => row.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز کمپینی ساخته نشده است"
        emptyDescription="اولین کمپین را به‌صورت پیش‌نویس بسازید، سپس پیش‌نمایش بگیرید و در پایان ارسال کنید."
        emptyAction={
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4" /> ساخت کمپین
          </Button>
        }
        emptyIcon={<Mail className="h-10 w-10" />}
      />

      {list && list.total > PAGE_SIZE && (
        <div className="flex items-center justify-between text-xs">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page <= 1 || loading}
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
            disabled={page >= totalPages || loading}
          >
            بعدی
          </Button>
        </div>
      )}

      {/* Create / Edit Dialog */}
      <Dialog open={editorOpen} onOpenChange={(open) => !open && setEditorOpen(false)}>
        <DialogContent className="max-w-3xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش کمپین" : "کمپین جدید"}</DialogTitle>
            <DialogDescription>
              کمپین به‌صورت پیش‌نویس ذخیره می‌شود؛ تا پیش از ارسال قابل ویرایش است.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="campaign-name">نام داخلی کمپین</Label>
                <Input
                  id="campaign-name"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="کمپین تابستان"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="campaign-subject">عنوان ایمیل</Label>
                <Input
                  id="campaign-subject"
                  value={formSubject}
                  onChange={(e) => setFormSubject(e.target.value)}
                  placeholder="تخفیف ویژه تابستان"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="campaign-preheader">متن پیش‌نمایش (اختیاری)</Label>
              <Input
                id="campaign-preheader"
                value={formPreheader}
                onChange={(e) => setFormPreheader(e.target.value)}
                placeholder="متنی که در صندوق ورودی، پیش از باز شدن ایمیل دیده می‌شود"
              />
            </div>
            <div className="space-y-1.5">
              <Label>محتوای ایمیل</Label>
              <RichBodyEditor
                value={formBodyHtml}
                onChange={setFormBodyHtml}
                placeholder="محتوای کمپین را بنویسید…"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="campaign-body-text">نسخه متنی (اختیاری)</Label>
              <Textarea
                id="campaign-body-text"
                rows={3}
                value={formBodyText}
                onChange={(e) => setFormBodyText(e.target.value)}
                placeholder="اگر خالی بماند، از محتوای HTML ساخته می‌شود"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void save()} disabled={saving}>
              {saving && <Loader2 className="h-4 w-4 animate-spin" />}
              {editing ? "ذخیره تغییرات" : "ساخت پیش‌نویس"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Schedule Dialog */}
      <Dialog
        open={scheduleTarget !== null}
        onOpenChange={(open) => !open && setScheduleTarget(null)}
      >
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>زمان‌بندی ارسال</DialogTitle>
            <DialogDescription>
              کمپین «{scheduleTarget?.name}» در زمان تعیین‌شده ارسال می‌شود؛ زمان‌بند حداکثر یک دقیقه
              تاخیر دارد.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 py-2">
            <Label htmlFor="campaign-schedule-at">تاریخ و ساعت</Label>
            <Input
              id="campaign-schedule-at"
              type="datetime-local"
              value={scheduleAt}
              onChange={(e) => setScheduleAt(e.target.value)}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setScheduleTarget(null)}>
              انصراف
            </Button>
            <Button onClick={() => void schedule()}>زمان‌بندی</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <CampaignPreviewDialog campaign={previewTarget} onClose={() => setPreviewTarget(null)} />

      <RecipientsDialog
        campaign={recipientsTarget}
        testEmail={testEmail}
        onTestEmailChange={setTestEmail}
        onTestSend={() => void testSend()}
        sendingTest={busyId !== null && recipientsTarget !== null && busyId === recipientsTarget.id}
        onClose={() => setRecipientsTarget(null)}
      />
    </div>
  );
}

function CampaignPreviewDialog({
  campaign,
  onClose,
}: {
  campaign: NewsletterCampaign | null;
  onClose: () => void;
}) {
  const {
    data,
    loading,
    error,
  } = useAdminQuery({
    queryKey: ["admin-newsletter-campaign-preview", campaign?.id ?? "none"],
    queryFn: () => newsletterCampaignsApi.preview(campaign!.id),
    fallbackError: "دریافت پیش‌نمایش ناموفق بود.",
    enabled: campaign !== null,
  });

  return (
    <Dialog open={campaign !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="max-w-3xl" dir="rtl">
        <DialogHeader>
          <DialogTitle>پیش‌نمایش: {campaign?.name}</DialogTitle>
          <DialogDescription>
            ایمیل به‌صورت رندرشده نهایی — شامل پاورقی لغو عضویت — نمایش داده می‌شود.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          {loading && (
            <div className="flex items-center justify-center py-10">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          )}
          {!loading && error && (
            <p className="py-6 text-center text-sm text-destructive">{error}</p>
          )}
          {!loading && !error && data && (
            <>
              <p className="text-xs text-muted-foreground">
                <span className="font-medium text-foreground">موضوع: </span>
                {data.subject}
              </p>
              <iframe
                title="پیش‌نمایش ایمیل"
                dir="rtl"
                srcDoc={sanitizeHtml(data.html)}
                className="h-96 w-full rounded-lg border border-border bg-white"
              />
            </>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            بستن
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function RecipientsDialog({
  campaign,
  testEmail,
  onTestEmailChange,
  onTestSend,
  sendingTest,
  onClose,
}: {
  campaign: NewsletterCampaign | null;
  testEmail: string;
  onTestEmailChange: (_value: string) => void;  onTestSend: () => void;
  sendingTest: boolean;
  onClose: () => void;
}) {
  const [page, setPage] = useState(1);
  const RECIPIENT_PAGE_SIZE = 50;

  const {
    data,
    loading,
    error,
  } = useAdminQuery({
    queryKey: ["admin-newsletter-campaign-recipients", campaign?.id ?? "none", page],
    queryFn: () => newsletterCampaignsApi.recipients(campaign!.id, page, RECIPIENT_PAGE_SIZE),
    fallbackError: "بارگذاری وضعیت گیرنده‌ها ناموفق بود.",
    enabled: campaign !== null,
    options: { placeholderData: keepPreviousData },
  });

  const totalPages = data ? Math.max(1, Math.ceil(data.total / RECIPIENT_PAGE_SIZE)) : 1;

  const columns: DataTableColumn<CampaignRecipient>[] = [
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
        <Badge variant={RECIPIENT_STATUS_META[row.status].variant} className="text-[10px]">
          {RECIPIENT_STATUS_META[row.status].label}
        </Badge>
      ),
    },
    {
      key: "sent_at",
      header: "زمان ارسال",
      className: "text-xs",
      render: (row) => {
        return <span className="text-muted-foreground">{formatDateTime(row.sent_at)}</span>;
      },
      hideOnMobile: true,
    },
    {
      key: "error",
      header: "خطا",
      className: "text-xs",
      render: (row) => {
        return <span className="text-destructive">{row.error ?? "—"}</span>;
      },
      hideOnMobile: true,
    },
  ];

  return (
    <Dialog
      open={campaign !== null}
      onOpenChange={(open) => {
        if (!open) {
          setPage(1);
          onClose();
        }
      }}
    >
      <DialogContent className="max-w-3xl" dir="rtl">
        <DialogHeader>
          <DialogTitle>گیرنده‌های: {campaign?.name}</DialogTitle>
          <DialogDescription>
            فهرست گیرنده‌ها در لحظه ارسال از اعضای تأییدشده گرفته می‌شود؛ لغو عضویتِ میان ارسال
            هم به‌طور خودکار این گیرنده را حذف می‌کند.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-[240px] flex-1 space-y-1.5">
              <Label htmlFor="campaign-test-email">ارسال ایمیل آزمایشی</Label>
              <Input
                id="campaign-test-email"
                type="email"
                dir="ltr"
                value={testEmail}
                onChange={(e) => onTestEmailChange(e.target.value)}
                placeholder="you@example.com"
                className="text-left text-xs"
              />
            </div>
            <Button size="sm" onClick={onTestSend} disabled={sendingTest}>
              {sendingTest ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Send className="h-4 w-4" />
              )}
              ارسال آزمایشی
            </Button>
          </div>

          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(row) => row.email}
            loading={loading}
            error={error}
            emptyMessage="گیرنده‌ای ثبت نشده است"
            emptyDescription="گیرنده‌ها فقط هنگام ارسال کمپین ساخته می‌شوند."
          />

          {data && data.total > RECIPIENT_PAGE_SIZE && (
            <div className="flex items-center justify-between text-xs">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
              >
                قبلی
              </Button>
              <span className="text-muted-foreground">
                صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(totalPages))} · کل{" "}
                {toPersianDigits(String(data.total))}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
              >
                بعدی
              </Button>
            </div>
          )}
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            بستن
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
