"use client";

/**
 * The customer's own data-subject request surface (GDPR articles 15 & 17).
 *
 * Before this page the account area had no privacy surface at all: the only
 * way to get a copy of your data or ask for it to be erased was for an
 * operator to run it after you opened a support ticket. GDPR requires the
 * subject to be able to make the request themselves, so both live here.
 *
 * Two rules shape the screen:
 *   - Nothing on it names a user id. The backend derives the subject from the
 *     session, so there is nothing here that could aim a request at somebody
 *     else's data.
 *   - The export is collected inline, over the same authenticated session.
 *     It is a copy of the customer's own record, shown on the page they
 *     asked for it on — not a link to a file somewhere with a secret in it.
 *     The backend drops the stored copy the first time it is read, so the
 *     "download" button is single-use and the page says so.
 */

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Download, FileJson, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import { apiErrorMessage } from "@/lib/api/error-message";
import { formatJalaliDateTime } from "@/lib/date";
import {
  fetchMyPrivacyRequests,
  fetchPrivacyExportResult,
  privacyStatusLabel,
  privacyStatusVariant,
  privacyTypeLabel,
  submitPrivacyRequest,
  type PrivacyRequest,
} from "@/lib/api/privacy";

export default function AccountPrivacyPage() {
  const { toast } = useToast();

  const [items, setItems] = useState<PrivacyRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [reason, setReason] = useState("");
  const [password, setPassword] = useState("");
  const [busyType, setBusyType] = useState<"export" | "erase" | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      setItems(await fetchMyPrivacyRequests());
    } catch (err) {
      // An empty list and a failed read look identical here, and "you have
      // made no requests" is a statement about the customer's history. Say
      // which one it is.
      setLoadError(
        apiErrorMessage(err, "دریافت درخواست‌های شما ناموفق بود. لطفاً دوباره تلاش کنید."),
      );
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const hasOpen = (type: string) =>
    items.some((i) => i.type === type && (i.status === "pending" || i.status === "processing"));

  const submit = async (type: "export" | "erase") => {
    if (type === "erase") {
      const ok = window.confirm(
        "با ثبت این درخواست، داده‌های شخصی حساب شما ناشناس‌سازی می‌شود و حساب غیرفعال خواهد شد. سفارش‌ها و سوابق مالی برای اعتبار حسابداری باقی می‌مانند. ادامه می‌دهید؟",
      );
      if (!ok) return;
    }
    setBusyType(type);
    try {
      await submitPrivacyRequest({
        type,
        reason: reason || null,
        // The password is only demanded for an erase, but sending it for an
        // export too is harmless: the backend verifies a volunteered one
        // rather than ignoring it.
        password: password || null,
      });
      setPassword("");
      toast({
        title: "درخواست شما ثبت شد",
        description: "وضعیت آن از همین صفحه قابل پیگیری است.",
      });
      await load();
    } catch (err) {
      toast({
        title: apiErrorMessage(err, "ثبت درخواست ناموفق بود."),
        variant: "destructive",
      });
    } finally {
      setBusyType(null);
    }
  };

  const download = async (id: string) => {
    setDownloadingId(id);
    try {
      const data = await fetchPrivacyExportResult(id);
      const blob = new Blob([JSON.stringify(data, null, 2)], {
        type: "application/json",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `my-data-export.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast({
        title: "نسخه داده‌های شما دانلود شد",
        description:
          "این نسخه از سیستم حذف شد؛ برای دریافت دوباره باید درخواست تازه ثبت کنید.",
      });
      await load();
    } catch (err) {
      toast({
        title: apiErrorMessage(
          err,
          "دریافت خروجی ناموفق بود. ممکن است قبلاً دریافت شده یا منقضی شده باشد.",
        ),
        variant: "destructive",
      });
      await load();
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground">
            <ShieldAlert className="h-5 w-5 text-primary" />
            حریم خصوصی و داده‌های من
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            می‌توانید نسخه‌ای از داده‌های شخصی خود را دریافت کنید یا درخواست حذف
            آن‌ها را ثبت کنید. وضعیت هر درخواست از همین صفحه قابل پیگیری است.
          </p>
        </div>
        <Button variant="outline" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`ms-1 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          تازه‌سازی
        </Button>
      </div>

      <Card className="space-y-4 p-5">
        <div className="space-y-1.5">
          <Label htmlFor="privacy-reason" className="text-xs">
            دلیل درخواست (اختیاری)
          </Label>
          <Textarea
            id="privacy-reason"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            rows={2}
            placeholder="مثلاً: برای بررسی شخصی داده‌هایی که از من ذخیره شده است."
          />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="privacy-password" className="text-xs">
            رمز عبور حساب (برای درخواست حذف الزامی است)
          </Label>
          <Input
            id="privacy-password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            dir="ltr"
          />
          <p className="text-[11px] text-muted-foreground">
            حذف برگشت‌پذیر نیست، بنابراین برای اطمینان از اینکه درخواست از سوی
            خودتان ثبت می‌شود، رمز عبور حسابتان را وارد کنید. رمز شما ذخیره
            نمی‌شود.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => void submit("export")}
            disabled={busyType !== null || hasOpen("export")}
          >
            <FileJson className="h-4 w-4" />
            {busyType === "export"
              ? "…"
              : hasOpen("export")
                ? "درخواست خروجی در انتظار است"
                : "درخواست نسخه داده‌ها"}
          </Button>
          <Button
            variant="destructive"
            onClick={() => void submit("erase")}
            disabled={busyType !== null || hasOpen("erase")}
          >
            <Trash2 className="h-4 w-4" />
            {busyType === "erase"
              ? "…"
              : hasOpen("erase")
                ? "درخواست حذف در انتظار است"
                : "درخواست حذف داده‌ها"}
          </Button>
        </div>

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          درخواست‌ها ابتدا توسط کارشناسان بررسی می‌شوند و سپس انجام می‌گیرند.
          حذف به‌صورت پیش‌فرض به شکل <strong>ناشناس‌سازی</strong> است: شماره
          تماس، ایمیل، کد ملی و کامنت‌های شخصی پاک می‌شوند اما بدنه حساب
          باقی می‌ماند تا سفارش‌ها و سوابق مالی معتبر بمانند.
        </p>
      </Card>

      {loadError ? (
        <Card role="alert" className="space-y-3 p-10 text-center">
          <p className="font-semibold text-foreground">
            دریافت درخواست‌ها ناموفق بود
          </p>
          <p className="text-sm text-muted-foreground">{loadError}</p>
          <Button variant="outline" onClick={() => void load()}>
            تلاش مجدد
          </Button>
          <p className="text-[11px] text-muted-foreground">
            این پیام به‌معنای نبود درخواست نیست؛ فهرست در این لحظه خوانده نشد.
          </p>
        </Card>
      ) : loading ? (
        <Card className="p-10 text-center text-sm text-muted-foreground">
          در حال دریافت درخواست‌ها...
        </Card>
      ) : items.length === 0 ? (
        <Card className="p-10 text-center">
          <p className="font-semibold text-foreground">هنوز درخواستی ثبت نکرده‌اید</p>
          <p className="mt-1 text-sm text-muted-foreground">
            با فرم بالا می‌توانید نسخه داده‌های خود را بخواهید یا درخواست حذف
            ثبت کنید.
          </p>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <caption className="sr-only">
                درخواست‌های حریم خصوصی ثبت‌شده توسط شما
              </caption>
              <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">نوع</th>
                  <th scope="col" className="px-4 py-3">وضعیت</th>
                  <th scope="col" className="px-4 py-3">تاریخ ثبت</th>
                  <th scope="col" className="px-4 py-3">توضیح</th>
                  <th scope="col" className="px-4 py-3">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60">
                {items.map((item) => (
                  <tr key={item.id}>
                    <td className="px-4 py-3">{privacyTypeLabel(item.type)}</td>
                    <td className="px-4 py-3">
                      <Badge variant={privacyStatusVariant(item.status)}>
                        {privacyStatusLabel(item.status)}
                      </Badge>
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {formatJalaliDateTime(item.createdAt)}
                    </td>
                    <td className="px-4 py-3 text-xs text-muted-foreground">
                      {item.status === "rejected" && item.adminNote
                        ? item.adminNote
                        : item.reason || "—"}
                    </td>
                    <td className="px-4 py-3">
                      {/* A partial export is still a real file: withholding the
                          download would hide the data that did collect. The
                          status badge already says it is incomplete, and the
                          server rejects serving one without the report. */}
                      {item.type === "export" &&
                        (item.status === "completed" || item.status === "partial") && (
                        item.hasResult ? (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => void download(item.id)}
                            disabled={downloadingId === item.id}
                          >
                            <Download className="h-3.5 w-3.5" />
                            {downloadingId === item.id ? "…" : "دریافت فایل"}
                          </Button>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">
                            خروجی منقضی یا دریافت شده — درخواست تازه ثبت کنید
                          </span>
                        )
                      )}
                      {item.type === "erase" && item.status === "completed" && (
                        <span className="text-[11px] text-muted-foreground">
                          داده‌های شما ناشناس شد
                        </span>
                      )}
                      {item.type === "erase" && item.status === "partial" && (
                        <span className="text-[11px] text-amber-700 dark:text-amber-400">
                          بخشی از داده‌ها هنوز حذف نشده — کارشناسان در جریان تکمیل آن
                          هستند
                        </span>
                      )}
                      {(item.status === "pending" || item.status === "processing") && (
                        <span className="text-[11px] text-muted-foreground">
                          در حال بررسی توسط کارشناسان
                        </span>
                      )}
                      {item.status === "rejected" && (
                        <span className="text-[11px] text-muted-foreground">
                          اگر اعتراض دارید از{" "}
                          <Link href="/account/tickets" className="text-primary hover:underline">
                            مرکز تیکت‌ها
                          </Link>{" "}
                          پیگیری کنید.
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
