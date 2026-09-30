"use client";

/**
 * Privacy / GDPR — the operator's queue.
 *
 * This page used to be one form: type a user UUID, export or erase. That is
 * a support-desk tool, not a workflow — the subject could not see it, could
 * not tell whether it happened, and the operator had no record of who asked.
 *
 * Now it is a queue over `privacy_requests`: the customer files their own
 * request (from /account/privacy), and the operator here runs the export or
 * the erasure, or rejects with a stated reason. The manual UUID form is kept
 * at the bottom as the fallback for an escalation that never became a
 * request — including hard delete, which stays operator-only because a
 * customer cannot be permitted to drop their own account row from a web form.
 */

import React, { useMemo, useState } from "react";
import {
  AlertTriangle,
  Download,
  Inbox,
  RefreshCw,
  ShieldCheck,
  Trash2,
  UserSearch,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { privacyApi } from "@/lib/api/wp-parity";
import {
  PRIVACY_REQUEST_STATUSES,
  PRIVACY_REQUEST_TYPES,
  privacyStatusLabel,
  privacyStatusVariant,
  privacyTypeLabel,
} from "@/lib/api/privacy";
import {
  fetchPrivacyQueue,
  rejectQueuedRequest,
  runQueuedErase,
  runQueuedExport,
  type AdminPrivacyRequest,
} from "@/lib/api/privacy-admin";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatJalaliDateTime } from "@/lib/date";
import { toPersianDigits } from "@/lib/utils";

const ALL = "all";
const PAGE_SIZE = 50;

export default function PrivacyPage() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();

  const [statusFilter, setStatusFilter] = useState<string>(ALL);
  const [typeFilter, setTypeFilter] = useState<string>(ALL);
  const [page, setPage] = useState(0);

  const [rejecting, setRejecting] = useState<AdminPrivacyRequest | null>(null);
  const [rejectNote, setRejectNote] = useState("");
  const [actingOn, setActingOn] = useState<string | null>(null);

  // Manual fallback — the operator types a UUID for an escalation that never
  // became a queued request. Kept deliberately unchanged: it is also the only
  // path to a hard delete.
  const [userId, setUserId] = useState("");
  const [manualBusy, setManualBusy] = useState<"export" | "erase" | null>(null);
  const [lastExport, setLastExport] = useState<Record<string, unknown> | null>(null);
  const [lastErase, setLastErase] = useState<{ actions: string[]; erased_at: string } | null>(
    null,
  );
  const [manualHardDelete, setManualHardDelete] = useState(false);

  const valid = /^[0-9a-f-]{36}$/i.test(userId.trim());

  const {
    data: queue,
    loading,
    error,
    reload,
  } = useAdminQuery({
    queryKey: ["admin-privacy-requests", statusFilter, typeFilter, page],
    queryFn: () =>
      fetchPrivacyQueue({
        status: statusFilter === ALL ? null : (statusFilter as never),
        type: typeFilter === ALL ? null : (typeFilter as never),
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      }),
    fallbackError: "بارگذاری صف درخواست‌های حریم خصوصی ناموفق بود",
  });

  const rows = queue?.items ?? [];
  const total = queue?.total ?? null;
  const totalPages = total === null ? null : Math.max(1, Math.ceil(total / PAGE_SIZE));

  const act = async (
    row: AdminPrivacyRequest,
    fn: () => Promise<AdminPrivacyRequest | null>,
    successTitle: string,
  ) => {
    setActingOn(row.id);
    const result = await runMutation(fn, { fallbackError: "انجام عملیات ناموفق بود" });
    setActingOn(null);
    if (result.ok) {
      toast({ title: successTitle });
      await reload();
    } else {
      toast({ title: result.error, variant: "destructive" });
      // A conflict means somebody else already took the row; the list on
      // screen is stale either way.
      await reload();
    }
  };

  const handleExport = async (row: AdminPrivacyRequest) => {
    await act(
      row,
      () => runQueuedExport(row.id),
      "خروجی داده‌های کاربر ساخته شد؛ کاربر می‌تواند آن را از حساب خود دریافت کند.",
    );
  };

  const handleErase = async (row: AdminPrivacyRequest) => {
    const ok = window.confirm(
      "داده‌های شخصی این کاربر ناشناس می‌شود و حساب غیرفعال خواهد شد. این عمل برای خود کاربر هم اثر دارد. ادامه می‌دهید؟",
    );
    if (!ok) return;
    await act(
      row,
      () => runQueuedErase(row.id),
      "درخواست حذف انجام شد و داده‌های کاربر ناشناس شد.",
    );
  };

  const handleReject = async () => {
    if (!rejecting) return;
    const note = rejectNote.trim();
    if (!note) {
      toast({
        title: "برای رد درخواست، دلیل الزامی است",
        variant: "destructive",
      });
      return;
    }
    setActingOn(rejecting.id);
    const result = await runMutation(
      () => rejectQueuedRequest(rejecting.id, note),
      { fallbackError: "رد درخواست ناموفق بود" },
    );
    setActingOn(null);
    if (result.ok) {
      setRejecting(null);
      setRejectNote("");
      toast({ title: "درخواست رد شد و دلیل برای کاربر ثبت شد" });
      await reload();
    } else {
      toast({ title: result.error, variant: "destructive" });
    }
  };

  const columns: DataTableColumn<AdminPrivacyRequest>[] = useMemo(
    () => [
      {
        key: "type",
        header: "نوع درخواست",
        render: (row) => (
          <span className="text-xs font-medium">{privacyTypeLabel(row.type)}</span>
        ),
      },
      {
        key: "user",
        header: "کاربر",
        className: "font-mono text-[11px]",
        render: (row) => (
          <span dir="ltr">
            {row.userId ? `${row.userId.slice(0, 8)}…` : "—"}
          </span>
        ),
      },
      {
        key: "status",
        header: "وضعیت",
        render: (row) => (
          <Badge variant={privacyStatusVariant(row.status)}>
            {privacyStatusLabel(row.status)}
          </Badge>
        ),
      },
      {
        key: "created",
        header: "تاریخ ثبت",
        className: "text-xs text-muted-foreground",
        hideOnMobile: true,
        render: (row) => <span>{formatJalaliDateTime(row.createdAt)}</span>,
      },
      {
        key: "reason",
        header: "دلیل / نتیجه",
        className: "text-xs text-muted-foreground",
        hideOnMobile: true,
        render: (row) => (
          <span className="block max-w-64 truncate">
            {row.adminNote || row.reason || "—"}
          </span>
        ),
      },
      {
        key: "actions",
        header: "عملیات",
        className: "text-left",
        render: (row) => {
          const open = row.status === "pending" || row.status === "processing";
          const busy = actingOn === row.id;
          return (
            <div className="flex flex-wrap items-center gap-1.5">
              {row.type === "export" && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => void handleExport(row)}
                  disabled={!open || busy}
                >
                  <Download className="h-3.5 w-3.5" />
                  اجرای خروجی
                </Button>
              )}
              {row.type === "erase" && (
                <Button
                  size="sm"
                  variant="destructive"
                  onClick={() => void handleErase(row)}
                  disabled={!open || busy}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  اجرای حذف
                </Button>
              )}
              <Button
                size="sm"
                variant="ghost"
                onClick={() => {
                  setRejecting(row);
                  setRejectNote("");
                }}
                disabled={!open || busy}
              >
                <XCircle className="h-3.5 w-3.5" />
                رد با دلیل
              </Button>
            </div>
          );
        },
      },
    ],
    // `actingOn` and `reload` are read inside the cell renderers; without
    // them the buttons would not reflect an action already running.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [actingOn, statusFilter, typeFilter, page],
  );

  const handleManualExport = async () => {
    if (!valid) return;
    setManualBusy("export");
    try {
      const data = await privacyApi.exportUser(userId.trim());
      setLastExport(data);
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `user-data-${userId.trim().slice(0, 8)}.json`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast({ title: "خروجی داده کاربر دانلود شد" });
    } catch {
      toast({ title: "خروجی گرفتن ناموفق بود", variant: "destructive" });
    } finally {
      setManualBusy(null);
    }
  };

  const handleManualErase = async () => {
    if (!valid) return;
    const confirmed = window.confirm(
      manualHardDelete
        ? "حذف کامل و غیرقابل بازگشت انجام می‌شود. فقط برای رسیدگی به درخواست پشتیبانی استفاده کنید. ادامه می‌دهید؟"
        : "داده‌های شخصی این کاربر ناشناس می‌شود و حساب غیرفعال خواهد شد. ادامه می‌دهید؟",
    );
    if (!confirmed) return;
    setManualBusy("erase");
    try {
      const res = await privacyApi.eraseUser(userId.trim(), !manualHardDelete);
      setLastErase(res);
      toast({ title: "داده‌های کاربر پاک/ناشناس شد" });
    } catch {
      toast({ title: "عملیات ناموفق بود", variant: "destructive" });
    } finally {
      setManualBusy(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-lg font-bold">
            <ShieldCheck className="h-5 w-5 text-primary" />
            حریم خصوصی و GDPR
          </h1>
          <p className="text-xs text-muted-foreground">
            صف درخواست‌های ثبت‌شده توسط کاربران برای دریافت نسخه داده یا حذف آن
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void reload()} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          تازه‌سازی
        </Button>
      </div>

      <Card className="flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-40 space-y-1.5">
          <Label className="text-xs">وضعیت</Label>
          <Select
            value={statusFilter}
            onValueChange={(v) => {
              setStatusFilter(v);
              setPage(0);
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="همه" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه</SelectItem>
              {PRIVACY_REQUEST_STATUSES.map((s) => (
                <SelectItem key={s} value={s}>
                  {privacyStatusLabel(s)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <div className="min-w-40 space-y-1.5">
          <Label className="text-xs">نوع</Label>
          <Select
            value={typeFilter}
            onValueChange={(v) => {
              setTypeFilter(v);
              setPage(0);
            }}
          >
            <SelectTrigger>
              <SelectValue placeholder="همه" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>همه</SelectItem>
              {PRIVACY_REQUEST_TYPES.map((t) => (
                <SelectItem key={t} value={t}>
                  {privacyTypeLabel(t)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        {total !== null && (
          <p className="ms-auto text-xs text-muted-foreground">
            {toPersianDigits(total)} درخواست
          </p>
        )}
      </Card>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        loading={loading}
        loadingMessage="در حال دریافت صف درخواست‌ها..."
        error={error}
        emptyMessage="درخواستی با این فیلترها وجود ندارد."
        emptyDescription="وقتی کاربری از صفحه حریم خصوصی حساب خود درخواستی ثبت کند، اینجا نمایش داده می‌شود."
        emptyIcon={
          <Inbox className="h-10 w-10 text-muted-foreground/40" aria-hidden="true" />
        }
        rowClassName={(row) => (row.status === "pending" ? "bg-amber-500/5" : "")}
      />

      {totalPages !== null && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0 || loading}
            onClick={() => setPage((p) => Math.max(0, p - 1))}
          >
            قبلی
          </Button>
          <span className="text-xs text-muted-foreground">
            صفحه {toPersianDigits(String(page + 1))} از{" "}
            {toPersianDigits(String(totalPages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page + 1 >= totalPages || loading}
            onClick={() => setPage((p) => p + 1)}
          >
            بعدی
          </Button>
        </div>
      )}

      {/* ── Manual fallback ─────────────────────────────────────────────── */}
      <Card className="space-y-4 p-5">
        <div>
          <h2 className="flex items-center gap-2 text-sm font-semibold">
            <UserSearch className="h-4 w-4" /> اجرای دستی (خارج از صف)
          </h2>
          <p className="mt-1 text-[11px] text-muted-foreground">
            برای رسیدگی به درخواست‌های پشتیبانی که به درخواست رسمی تبدیل
            نشده‌اند. این مسیر هیچ سابقه‌ای در صف ثبت نمی‌کند.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="privacy-user" className="text-xs">
            شناسه کاربر (UUID)
          </Label>
          <div className="flex gap-2">
            <Input
              id="privacy-user"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              placeholder="00000000-0000-0000-0000-000000000000"
              dir="ltr"
              className="font-mono text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => void handleManualExport()}
              disabled={!valid || manualBusy !== null}
            >
              <Download className="h-4 w-4" />
              {manualBusy === "export" ? "…" : "خروجی"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => void handleManualErase()}
              disabled={!valid || manualBusy !== null}
            >
              <Trash2 className="h-4 w-4" />
              {manualBusy === "erase" ? "…" : "پاک‌سازی"}
            </Button>
          </div>
          {!valid && userId.length > 0 && (
            <p className="text-[11px] text-muted-foreground">
              شناسه کاربر باید یک UUID معتبر باشد.
            </p>
          )}
        </div>

        <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
          <input
            type="checkbox"
            checked={manualHardDelete}
            onChange={(e) => setManualHardDelete(e.target.checked)}
            className="h-3.5 w-3.5"
          />
          حذف کامل و غیرقابل بازگشت به‌جای ناشناس‌سازی
        </label>

        <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-[11px] text-amber-700 dark:text-amber-300">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            در صف بالا، حذف همیشه به‌صورت <strong>ناشناس‌سازی</strong> اجرا می‌شود:
            شماره تماس، ایمیل، کد ملی و کامنت‌های شخصی پاک می‌شوند اما بدنه حساب
            باقی می‌ماند تا سفارش‌ها و سوابق حسابداری معتبر بمانند. حذف کامل فقط
            از همین مسیر دستی و به‌صورت صریح ممکن است.
          </span>
        </div>
      </Card>

      {lastExport && (
        <Card className="space-y-2 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <UserSearch className="h-4 w-4" /> نتیجه آخرین خروجی دستی
          </h3>
          <div className="flex flex-wrap gap-2">
            {Object.keys(lastExport).map((k) => (
              <Badge key={k} variant="secondary" className="text-[10px]" dir="ltr">
                {k}
              </Badge>
            ))}
          </div>
        </Card>
      )}

      {lastErase && (
        <Card className="space-y-2 p-5">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <ShieldCheck className="h-4 w-4" /> نتیجه آخرین پاک‌سازی دستی
          </h3>
          <div className="flex flex-wrap gap-2">
            {lastErase.actions.map((a) => (
              <Badge key={a} variant="outline" className="text-[10px]" dir="ltr">
                {a}
              </Badge>
            ))}
          </div>
          <p className="text-[11px] text-muted-foreground">
            {formatJalaliDateTime(lastErase.erased_at)}
          </p>
        </Card>
      )}

      <Dialog open={rejecting !== null} onOpenChange={(open) => !open && setRejecting(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>رد درخواست</DialogTitle>
            <DialogDescription>
              دلیل رد برای خود کاربر هم نمایش داده می‌شود. بدون دلیل، رد یک تصمیم
              قابل اعتراض نیست.
            </DialogDescription>
          </DialogHeader>
          <Textarea
            value={rejectNote}
            onChange={(e) => setRejectNote(e.target.value)}
            rows={4}
            placeholder="مثلاً: هویت درخواست‌کننده تلفنی تأیید نشد."
          />
          <DialogFooter>
            <Button variant="ghost" onClick={() => setRejecting(null)}>
              انصراف
            </Button>
            <Button
              variant="destructive"
              onClick={() => void handleReject()}
              disabled={actingOn !== null}
            >
              ثبت دلیل و رد درخواست
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
