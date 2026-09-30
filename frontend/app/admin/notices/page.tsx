"use client";

/**
 * Admin notices (اعلانات زمان‌دار) + SMS dispatch.
 *
 * Two backend surfaces share this screen because they share an operator: the
 * notice window (`/notifications/notices/admin*`) and the multi-provider SMS
 * hub (`/notifications/notices/sms/dispatch`). Both were built server-side
 * and the notice half had a page, but the SMS hub had no entry point at all —
 * it is the only way an operator can force a message to a single number, and
 * it was reachable solely by typing the URL.
 *
 * All calls go through `notificationsAdminApi`, which mirrors the Pydantic
 * schemas in `backend/app/modules/notifications/schemas/notices.py`. The
 * dispatch result is reported per provider: a run that exhausts the failover
 * chain comes back `success: false` with the reason, and the operator sees
 * that reason rather than a "sent" that never happened.
 */

import { useState } from "react";
import {
  Bell,
  CheckCircle2,
  Loader2,
  MessageSquare,
  Plus,
  RefreshCw,
  Send,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import {
  notificationsAdminApi,
  type Notice,
  type NoticeTargetPage,
  type NoticeType,
  type SmsDispatchResult,
} from "@/lib/api/notifications";
import { sanitizeHtml } from "@/lib/sanitize";
import { toPersianDigits } from "@/lib/utils";

const NOTICES_QUERY_KEY = "admin-notices" as const;

/** Window applied when the operator leaves the end date blank. */
const DEFAULT_WINDOW_DAYS = 7;

const TYPE_LABELS: Record<NoticeType, string> = {
  banner: "بنر",
  popup: "پاپ‌آپ",
  alert_bar: "نوار هشدار",
};

const TARGET_PAGE_LABELS: Record<NoticeTargetPage, string> = {
  all: "همه صفحات",
  home: "صفحه اصلی",
  checkout: "تسویه‌حساب",
  dashboard: "پنل کاربری",
};

export default function AdminNoticesPage() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();

  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [noticeType, setNoticeType] = useState<NoticeType>("popup");
  const [targetPage, setTargetPage] = useState<NoticeTargetPage>("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [creating, setCreating] = useState(false);

  const [mobile, setMobile] = useState("");
  const [smsText, setSmsText] = useState("");
  const [smsPattern, setSmsPattern] = useState("");
  const [sending, setSending] = useState(false);
  const [smsResult, setSmsResult] = useState<SmsDispatchResult | null>(null);

  const {
    data,
    loading,
    reload: fetchNotices,
  } = useAdminQuery({
    queryKey: [NOTICES_QUERY_KEY],
    queryFn: notificationsAdminApi.listAllNotices,
    fallbackError: "بارگذاری اعلانات با خطا مواجه شد",
    toastOnError: true,
    toastDescription: "بارگذاری اعلانات با خطا مواجه شد",
  });
  const notices: Notice[] = data ?? [];

  const createNotice = async () => {
    if (!title.trim() || !content.trim()) {
      toast({
        title: "خطا",
        description: "عنوان و محتوای اطلاعیه الزامی است",
        variant: "destructive",
      });
      return;
    }
    // The service fills a missing end_at with `now + resolution` — a window
    // that closes in microseconds, so the notice would never be served. An
    // omitted end date therefore has to become a real default here.
    const end = endDate
      ? new Date(endDate)
      : new Date(Date.now() + DEFAULT_WINDOW_DAYS * 24 * 60 * 60 * 1000);
    const start = startDate ? new Date(startDate) : new Date();
    if (end <= start) {
      toast({
        title: "خطا",
        description: "تاریخ پایان باید بعد از تاریخ شروع باشد",
        variant: "destructive",
      });
      return;
    }
    setCreating(true);
    const result = await runMutation(
      () =>
        notificationsAdminApi.createNotice({
          title: title.trim(),
          content_html: content,
          notice_type: noticeType,
          target_page: targetPage,
          start_at: start.toISOString(),
          end_at: end.toISOString(),
        }),
      {
        fallbackError: "ایجاد اطلاعیه با خطا مواجه شد",
        invalidateKeys: [[NOTICES_QUERY_KEY]],
      },
    );
    setCreating(false);
    if (result.ok) {
      toast({ title: "موفق", description: "اطلاعیه جدید ایجاد شد" });
      setCreateOpen(false);
      setTitle("");
      setContent("");
      setStartDate("");
      setEndDate("");
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const dispatchSms = async () => {
    const number = mobile.trim();
    if (!number || !smsText.trim()) {
      toast({
        title: "خطا",
        description: "شماره موبایل و متن پیامک الزامی است",
        variant: "destructive",
      });
      return;
    }
    setSending(true);
    setSmsResult(null);
    const result = await runMutation(
      () =>
        notificationsAdminApi.dispatchSms({
          mobile: number,
          text: smsText.trim(),
          ...(smsPattern.trim() ? { pattern: smsPattern.trim() } : {}),
        }),
      { fallbackError: "ارسال پیامک ناموفق بود" },
    );
    setSending(false);
    if (!result.ok) {
      setSmsResult(null);
      toast({ title: "خطا", description: result.error, variant: "destructive" });
      return;
    }
    setSmsResult(result.data);
    if (result.data.success) {
      toast({
        title: "پیامک ارسال شد",
        description: `سرویس‌دهنده: ${result.data.provider ?? "—"}`,
      });
    } else {
      // The request succeeded but no provider accepted the message. Showing
      // this as a plain success would be the one lie the hub can't recover from.
      toast({
        title: "پیامک ارسال نشد",
        description: result.data.error ?? "همه سرویس‌دهنده‌ها پاسخ ندادند.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-4" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            اعلانات زمان‌دار
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            ایجاد و مدیریت اطلاعیه‌ها، بنرها و پاپ‌آپ‌های زمان‌دار
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void fetchNotices()}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4" />
            اطلاعیه جدید
          </Button>
        </div>
      </div>

      <Tabs defaultValue="notices" className="space-y-4">
        <TabsList className="bg-card border border-border p-1">
          <TabsTrigger value="notices" className="gap-1.5 text-xs">
            <Bell className="h-3.5 w-3.5" /> اطلاعیه‌ها
          </TabsTrigger>
          <TabsTrigger value="sms" className="gap-1.5 text-xs">
            <MessageSquare className="h-3.5 w-3.5" /> ارسال پیامک
          </TabsTrigger>
        </TabsList>

        <TabsContent value="notices" className="space-y-4">
          {loading ? (
            <div className="flex items-center justify-center p-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : notices.length === 0 ? (
            <Card className="p-12 text-center">
              <Bell className="h-12 w-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm text-muted-foreground">هنوز هیچ اطلاعیه‌ای ایجاد نشده است</p>
              <Button size="sm" className="mt-4" onClick={() => setCreateOpen(true)}>
                ایجاد اولین اطلاعیه
              </Button>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {notices.map((n) => (
                <Card key={n.id} className="p-5">
                  <div className="flex items-start justify-between">
                    <div className="space-y-1">
                      <h4 className="font-semibold text-sm">{n.title}</h4>
                      <div className="flex gap-2">
                        <Badge variant="outline">{TYPE_LABELS[n.notice_type]}</Badge>
                        <Badge variant="outline">
                          صفحه: {TARGET_PAGE_LABELS[n.target_page] ?? n.target_page}
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground" dir="ltr">
                        {toPersianDigits(new Date(n.start_at).toLocaleDateString("fa-IR"))} -{" "}
                        {toPersianDigits(new Date(n.end_at).toLocaleDateString("fa-IR"))}
                      </p>
                    </div>
                    <Badge
                      variant={n.is_active ? "success" : "secondary"}
                      className="text-[10px]"
                    >
                      {n.is_active ? "فعال" : "غیرفعال"}
                    </Badge>
                  </div>
                  <div
                    className="mt-3 text-xs text-muted-foreground line-clamp-2 prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: sanitizeHtml(n.content_html) }}
                  />
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        <TabsContent value="sms" className="space-y-4">
          <Card className="space-y-4 p-5">
            <div>
              <h3 className="text-base font-bold flex items-center gap-2">
                <MessageSquare className="h-4 w-4 text-primary" />
                ارسال پیامک تکی
              </h3>
              <p className="text-xs text-muted-foreground mt-1">
                پیام از زنجیره سرویس‌دهنده‌ها (کاوه‌نگار ← آی‌پی‌پنل ← SMS.ir) با failover خودکار
                ارسال می‌شود. اگر همه شکست بخورند، دلیل خطا همین‌جا گزارش می‌شود.
              </p>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor="sms-mobile">شماره موبایل</Label>
                <Input
                  id="sms-mobile"
                  dir="ltr"
                  value={mobile}
                  onChange={(e) => setMobile(e.target.value)}
                  placeholder="09123456789"
                  className="text-left text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="sms-pattern">کد پترن (اختیاری)</Label>
                <Input
                  id="sms-pattern"
                  dir="ltr"
                  value={smsPattern}
                  onChange={(e) => setSmsPattern(e.target.value)}
                  placeholder="برای ارسال خدماتی"
                  className="text-left text-xs"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="sms-text">متن پیامک</Label>
              <Textarea
                id="sms-text"
                rows={4}
                value={smsText}
                onChange={(e) => setSmsText(e.target.value)}
                placeholder="متن پیام…"
              />
            </div>

            <div className="flex items-center gap-2">
              <Button size="sm" onClick={() => void dispatchSms()} disabled={sending}>
                {sending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Send className="h-4 w-4" />
                )}
                ارسال پیامک
              </Button>
              {smsResult && (
                <span className="flex items-center gap-1.5 text-xs">
                  {smsResult.success ? (
                    <>
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                      <span className="text-emerald-600">
                        ارسال شد{smsResult.to ? ` به ${smsResult.to}` : ""}
                        {smsResult.provider ? ` · ${smsResult.provider}` : ""}
                      </span>
                    </>
                  ) : (
                    <>
                      <XCircle className="h-4 w-4 text-destructive" />
                      <span className="text-destructive">
                        {smsResult.error ?? "ارسال ناموفق"}
                      </span>
                    </>
                  )}
                </span>
              )}
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Create Notice Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>ایجاد اطلاعیه جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="notice-title">عنوان</Label>
              <Input
                id="notice-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="notice-content">محتوا (HTML)</Label>
              <Textarea
                id="notice-content"
                rows={4}
                value={content}
                onChange={(e) => setContent(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="notice-type">نوع</Label>
                <select
                  id="notice-type"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={noticeType}
                  onChange={(e) => setNoticeType(e.target.value as NoticeType)}
                >
                  <option value="popup">پاپ‌آپ</option>
                  <option value="banner">بنر</option>
                  <option value="alert_bar">نوار هشدار</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label htmlFor="notice-page">صفحه هدف</Label>
                <select
                  id="notice-page"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={targetPage}
                  onChange={(e) => setTargetPage(e.target.value as NoticeTargetPage)}
                >
                  <option value="all">همه صفحات</option>
                  <option value="home">صفحه اصلی</option>
                  <option value="checkout">تسویه‌حساب</option>
                  <option value="dashboard">پنل کاربری</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="notice-start">تاریخ شروع</Label>
                <Input
                  id="notice-start"
                  type="datetime-local"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="notice-end">تاریخ پایان</Label>
                <Input
                  id="notice-end"
                  type="datetime-local"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void createNotice()} disabled={creating}>
              {creating ? "در حال ایجاد..." : "ایجاد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
