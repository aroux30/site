"use client";

import { useState } from "react";

import {
  editorialWorkflowApi,
  type PendingReviewPost,
} from "@/lib/api/wp-parity";
import { useAdminQuery } from "@/lib/api/admin-query";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";

const QUEUE_QUERY_KEY = "editorial-pending-review" as const;

interface Props {
  /** Called after approve/reject so the posts list can refresh. */
  onChanged?: () => void | Promise<void>;
}

/**
 * The editorial queue: posts a contributor submitted that need a publisher to
 * approve or send back.
 *
 * The whole workflow existed on the server — submit, approve, reject, and this
 * listing — with no caller in the admin, so a post that entered
 * `pending_review` was invisible to the editor who had to act on it. That is
 * the whole point of the status: without this table the role is a dead end.
 */
export function ReviewQueueTab({ onChanged }: Props) {
  const [busyId, setBusyId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const {
    data: pending,
    loading,
    error: loadError,
    reload,
  } = useAdminQuery<PendingReviewPost[]>({
    queryKey: [QUEUE_QUERY_KEY],
    queryFn: () => editorialWorkflowApi.pending(1, 50),
    fallbackError: "دریافت صف بازبینی ناموفق بود",
  });

  const queue = pending ?? [];

  async function act(
    postId: string,
    verb: "approve" | "reject",
  ): Promise<void> {
    setBusyId(postId);
    setError(null);
    try {
      if (verb === "approve") {
        await editorialWorkflowApi.approve(postId);
      } else {
        await editorialWorkflowApi.reject(postId, "بازگردانده شد برای ویرایش");
      }
      // The row leaves the queue either way, so the listing has to be refetched
      // — and the posts list, because the status just changed under it.
      await reload();
      await onChanged?.();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "انجام عملیات بازبینی ناموفق بود. لطفاً دوباره تلاش کنید.",
      );
    } finally {
      setBusyId(null);
    }
  }

  const columns: DataTableColumn<PendingReviewPost>[] = [
    { key: "title", header: "عنوان", render: (p) => p.title || "— بدون عنوان —" },
    {
      key: "slug",
      header: "نشانی",
      render: (p) => (
        <span dir="ltr" className="text-xs text-muted-foreground">
          {p.slug}
        </span>
      ),
    },
    {
      key: "updated_at",
      header: "آخرین ویرایش",
      render: (p) => {
        const d = new Date(p.updated_at);
        return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString("fa-IR");
      },
    },
    {
      key: "actions",
      header: "عملیات",
      render: (p) => (
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            disabled={busyId === p.id}
            onClick={() => void act(p.id, "approve")}
          >
            {busyId === p.id ? "در حال انجام..." : "انتشار"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busyId === p.id}
            onClick={() => void act(p.id, "reject")}
          >
            بازگشت به پیش‌نویس
          </Button>
        </div>
      ),
    },
  ];

  return (
    <Card className="p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">صف بازبینی</h3>
          {queue.length > 0 && (
            <Badge variant="secondary">{queue.length} در انتظار</Badge>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => void reload()}
          disabled={loading}
        >
          {loading ? "در حال بارگذاری..." : "تازه‌سازی"}
        </Button>
      </div>

      {/* A failed action is stated, not swallowed: the post stays in the queue
          and the editor has to know why nothing happened. */}
      {error && (
        <p className="mb-3 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
          {error}
        </p>
      )}

      <DataTable<PendingReviewPost>
        columns={columns}
        rows={queue}
        rowKey={(p) => p.id}
        loading={loading}
        error={loadError}
        emptyMessage="هیچ نوشته‌ای در انتظار بازبینی نیست."
      />

      {queue.length > 0 && (
        <p className="mt-3 text-xs text-muted-foreground">
          تا زمانی که این صف خالی نشود، پیش‌نویس‌های ارسال‌شده منتشر نمی‌شوند.
        </p>
      )}
    </Card>
  );
}