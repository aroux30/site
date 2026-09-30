"use client";

import { useState } from "react";
import { Check, RefreshCw, Star, X } from "lucide-react";
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
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import {
  MissingDataNotice,
  PartialDataNotice,
  UnavailableValue,
} from "@/components/admin/async-state";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { formatJalaliDateTime } from "@/lib/date";
import { toPersianDigits } from "@/lib/utils";
import {
  fetchPendingReviews,
  moderateReview,
  type AdminReview,
  type ReviewModerationDecision,
} from "@/lib/api/reviews";

const PENDING_REVIEWS_QUERY_KEY = "admin-pending-reviews" as const;

/**
 * Review moderation queue (admin).
 *
 * Shows exactly the reviews the backend reports as `pending` and offers the two
 * decisions its contract accepts: `approved` or `rejected`. The endpoint takes
 * a target STATUS, not an action verb — the distinction matters because the
 * backend validates it against `^(approved|rejected)$`.
 *
 * A rejection note is optional but encouraged: it is the only place a moderator
 * records WHY a review was removed, and the author's own view of the review
 * never shows it.
 */
export default function AdminReviewsPage() {
  const [page, setPage] = useState(1);
  const [target, setTarget] = useState<{
    review: AdminReview;
    decision: ReviewModerationDecision;
  } | null>(null);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const runMutation = useAdminMutation();

  const { data, loading, error, reload } = useAdminQuery({
    queryKey: [PENDING_REVIEWS_QUERY_KEY, page],
    queryFn: () => fetchPendingReviews({ page, size: 20 }),
    fallbackError: "دریافت نظرات در انتظار تأیید ناموفق بود",
  });
  const reviews: AdminReview[] = data?.reviews ?? [];
  const total = data?.total ?? null;
  const totalPages = data?.totalPages ?? null;
  const missingCount = data?.missingCount ?? null;
  const invalidCount = data?.invalidCount ?? 0;

  const openDecision = (review: AdminReview, decision: ReviewModerationDecision) => {
    setTarget({ review, decision });
    setReason("");
    setFormError(null);
  };

  const confirmDecision = async () => {
    if (!target) return;
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () => moderateReview(target.review.id, target.decision, reason || null),
      {
        fallbackError:
          target.decision === "approved" ? "تأیید نظر ناموفق بود" : "رد نظر ناموفق بود",
      },
    );
    if (result.ok) {
      setTarget(null);
      await reload();
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const distribution = data?.distribution;

  const columns: DataTableColumn<AdminReview>[] = [
    {
      key: "product",
      header: "کالا / کاربر",
      render: (r) => (
        <div>
          <div className="font-mono text-[11px] text-muted-foreground" dir="ltr">
            {r.productId.slice(0, 8)}
          </div>
          <div className="text-xs">
            {r.user.displayName ?? (
              <UnavailableValue reason="نام نمایشی ثبت نشده." />
            )}
          </div>
        </div>
      ),
    },
    {
      key: "rating",
      header: "امتیاز",
      render: (r) =>
        r.rating === null ? (
          <UnavailableValue reason="گزارش نشد." />
        ) : (
          <span className="inline-flex items-center gap-0.5" aria-label={`${r.rating} از ۵`}>
            {Array.from({ length: r.rating }).map((_, i) => (
              <Star
                key={i}
                className="h-3.5 w-3.5 fill-amber-500 text-amber-500"
                aria-hidden="true"
              />
            ))}
            <span className="ms-1 font-mono text-xs text-muted-foreground">
              {toPersianDigits(String(r.rating))}
            </span>
          </span>
        ),
    },
    {
      key: "content",
      header: "متن نظر",
      render: (r) => (
        <div className="max-w-md space-y-0.5">
          {r.title && <div className="text-xs font-medium text-foreground">{r.title}</div>}
          <div className="line-clamp-2 text-xs text-muted-foreground">
            {r.body ?? <UnavailableValue reason="متن ثبت نشده." />}
          </div>
        </div>
      ),
    },
    {
      key: "verified",
      header: "خرید تأییدشده",
      hideOnMobile: true,
      render: (r) =>
        r.isVerifiedPurchase ? (
          <Badge variant="secondary">بله</Badge>
        ) : (
          <span className="text-xs text-muted-foreground">خیر</span>
        ),
    },
    {
      key: "created",
      header: "تاریخ ثبت",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs text-muted-foreground">
          {formatJalaliDateTime(r.createdAt)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="sm"
            className="gap-1 text-emerald-700 dark:text-emerald-400"
            onClick={() => openDecision(r, "approved")}
          >
            <Check className="h-3.5 w-3.5" aria-hidden="true" />
            تأیید
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="gap-1 text-destructive"
            onClick={() => openDecision(r, "rejected")}
          >
            <X className="h-3.5 w-3.5" aria-hidden="true" />
            رد
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Star className="h-5 w-5 text-primary" />
            بررسی نظرات کاربران
          </h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">
            صف نظرات در انتظار بررسی. تأیید نظر آن را در صفحه کالا منتشر می‌کند و
            رد آن را از دید عمومی خارج می‌سازد.
          </p>
        </div>
        <Button variant="outline" onClick={() => void reload()}>
          <RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی
        </Button>
      </section>

      {distribution && (
        <Card className="p-4">
          <div className="grid grid-cols-3 gap-4 sm:grid-cols-6">
            <div>
              <div className="text-[11px] text-muted-foreground">در انتظار بررسی</div>
              <div className="mt-0.5 text-lg font-bold">
                {total === null ? (
                  <UnavailableValue reason="گزارش نشد." />
                ) : (
                  toPersianDigits(String(total))
                )}
              </div>
            </div>
            <div>
              <div className="text-[11px] text-muted-foreground">میانگین امتیاز</div>
              <div className="mt-0.5 font-mono text-lg font-bold">
                {data?.averageRating === null || data?.averageRating === undefined ? (
                  <UnavailableValue reason="گزارش نشد." />
                ) : (
                  toPersianDigits(data.averageRating.toFixed(2))
                )}
              </div>
            </div>
            {(
              [
                ["۵ ستاره", distribution.star5],
                ["۴ ستاره", distribution.star4],
                ["۳ ستاره", distribution.star3],
                ["۲ ستاره", distribution.star2],
              ] as const
            ).map(([label, count]) => (
              <div key={label}>
                <div className="text-[11px] text-muted-foreground">{label}</div>
                <div className="mt-0.5 font-mono text-sm">
                  {count === null ? "—" : toPersianDigits(String(count))}
                </div>
              </div>
            ))}
          </div>
        </Card>
      )}

      <PartialDataNotice count={invalidCount} label="نظرات بازگشتی" />
      <MissingDataNotice count={missingCount ?? 0} label="نظرات در انتظار بررسی" />

      <DataTable
        columns={columns}
        rows={reviews}
        rowKey={(r) => r.id}
        loading={loading}
        error={error}
        emptyMessage="نظری در انتظار بررسی نیست"
        emptyDescription="همه نظرات بررسی شده‌اند. صف به‌صورت خودکار با ثبت نظرات جدید پر می‌شود."
      />

      {totalPages !== null && totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            قبلی
          </Button>
          <span className="text-xs text-muted-foreground">
            صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(totalPages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            بعدی
          </Button>
        </div>
      )}

      <Dialog
        open={target !== null}
        onOpenChange={(open) => {
          if (!open) setTarget(null);
        }}
      >
        <DialogContent dir="rtl">
          <DialogHeader>
            <DialogTitle>
              {target?.decision === "approved" ? "تأیید نظر" : "رد نظر"}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-3 py-2">
            <p className="text-sm text-muted-foreground">
              {target?.decision === "approved"
                ? "این نظر پس از تأیید در صفحه کالا برای همه کاربران نمایش داده می‌شود."
                : "این نظر از دید عمومی خارج می‌شود. ثبت دلیل به پیگیری‌های بعدی کمک می‌کند."}
            </p>
            {target?.review.body && (
              <blockquote className="rounded-md border border-border bg-muted/30 p-3 text-xs leading-5 text-muted-foreground">
                {target.review.body}
              </blockquote>
            )}
            <div className="space-y-1.5">
              <label
                htmlFor="moderation-reason"
                className="block text-[11px] font-medium text-muted-foreground"
              >
                دلیل {target?.decision === "rejected" ? "" : "(اختیاری)"}
              </label>
              <Input
                id="moderation-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder={
                  target?.decision === "rejected"
                    ? "مثلاً: محتوای تبلیغاتی یا نامرتبط"
                    : "توضیح اختیاری"
                }
              />
            </div>
          </div>
          {formError && (
            <p role="alert" className="text-sm text-destructive">
              {formError}
            </p>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setTarget(null)}>
              انصراف
            </Button>
            <Button
              variant={target?.decision === "rejected" ? "destructive" : "default"}
              disabled={saving}
              onClick={() => void confirmDecision()}
            >
              {saving
                ? "در حال ثبت..."
                : target?.decision === "approved"
                  ? "تأیید نظر"
                  : "رد نظر"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
