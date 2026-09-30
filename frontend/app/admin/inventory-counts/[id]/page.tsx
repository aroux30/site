"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { AlertTriangle, ArrowRight, ClipboardCheck, RefreshCw, Save, Send } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { toPersianDigits } from "@/lib/utils";
import { useAdminQuery } from "@/lib/api/admin-query";
import { inventoryOperationsApi, type StockCount, type StockCountLine } from "@/lib/api/inventory-operations";

function messageOf(error: unknown, fallback: string): string {
  return (error as { response?: { data?: { error?: { message?: string }; detail?: string } } })?.response?.data?.error?.message
    ?? (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
    ?? fallback;
}

export default function InventoryCountEntryPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const countId = params.id;
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const {
    data: count = null,
    loading,
    error: loadError,
    reload: load,
  } = useAdminQuery<StockCount | null>({
    queryKey: ["admin", "inventory-counts", countId],
    enabled: Boolean(countId),
    queryFn: async () => {
      const loaded = await inventoryOperationsApi.getCount(countId);
      setDrafts(
        Object.fromEntries(
          loaded.lines.map((line) => [
            line.product_variant_id,
            line.counted_qty === null ? "" : String(line.counted_qty),
          ])
        )
      );
      return loaded;
    },
    fallbackError: "دریافت جلسه شمارش ناموفق بود",
  });

  const error = actionError || loadError;

  const isEditable = count?.status === "draft" || count?.status === "counting";
  const unsavedLines = useMemo(() => count?.lines.filter((line) => {
    const value = drafts[line.product_variant_id];
    return value !== "" && Number(value) !== line.counted_qty;
  }) ?? [], [count, drafts]);

  const saveLines = async () => {
    if (!count) return;
    const lines = count.lines
      .filter((line) => drafts[line.product_variant_id] !== "")
      .map((line) => ({
        product_variant_id: line.product_variant_id,
        counted_qty: Number(drafts[line.product_variant_id]),
        note: line.note,
      }));
    if (!lines.length) {
      setActionError("حداقل یک مقدار شمارش‌شده وارد کنید");
      return;
    }
    if (lines.some((line) => !Number.isInteger(line.counted_qty) || line.counted_qty < 0)) {
      setActionError("مقادیر شمارش باید اعداد صحیحِ صفر یا بیشتر باشند");
      return;
    }
    setSaving(true);
    setActionError(null);
    try {
      await inventoryOperationsApi.saveCountLines(count.id, lines);
      await load();
    } catch (reason) {
      setActionError(messageOf(reason, "ذخیره مقادیر شمارش ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  const review = async () => {
    if (!count) return;
    if (unsavedLines.length) {
      setActionError("ابتدا تغییرات واردشده را ذخیره کنید");
      return;
    }
    setSaving(true);
    setActionError(null);
    try {
      await inventoryOperationsApi.reviewCount(count.id);
      await load();
    } catch (reason) {
      setActionError(messageOf(reason, "ارسال برای بررسی ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  const post = async () => {
    if (!count) return;
    const confirmation = window.confirm(
      `ثبت ${count.variance_line_count} ردیف اختلاف در دفتر موجودی؟ این عمل تغییرات را از طریق تراکنش‌های حسابرسی‌شده ثبت می‌کند.`,
    );
    if (!confirmation) return;
    setSaving(true);
    setActionError(null);
    try {
      await inventoryOperationsApi.postCount(count.id);
      await load();
    } catch (reason) {
      setActionError(messageOf(reason, "ثبت نهایی شمارش ناموفق بود"));
    } finally {
      setSaving(false);
    }
  };

  const columns: DataTableColumn<StockCountLine>[] = [
    {
      key: "variant",
      header: "شناسه واریانت",
      render: (line) => <span className="font-mono text-xs" dir="ltr">{line.product_variant_id}</span>,
    },
    {
      key: "system",
      header: "موجودی سیستمی",
      render: (line) => toPersianDigits(line.system_qty.toLocaleString("en-US")),
    },
    {
      key: "counted",
      header: "شمارش فیزیکی",
      render: (line) => isEditable ? (
        <Input
          aria-label={`شمارش فیزیکی ${line.product_variant_id}`}
          className="h-8 w-24 text-center font-mono"
          dir="ltr"
          inputMode="numeric"
          min="0"
          type="number"
          value={drafts[line.product_variant_id] ?? ""}
          onChange={(event) => setDrafts((previous) => ({ ...previous, [line.product_variant_id]: event.target.value }))}
        />
      ) : (
        line.counted_qty === null ? "—" : toPersianDigits(line.counted_qty.toLocaleString("en-US"))
      ),
    },
    {
      key: "variance",
      header: "اختلاف",
      render: (line) => {
        const entered = drafts[line.product_variant_id];
        const variance = entered === "" || entered === undefined
          ? line.variance
          : Number(entered) - line.system_qty;
        return variance === null || variance === undefined ? "—" : (
          <span className={variance === 0 ? "" : variance > 0 ? "font-medium text-emerald-700 dark:text-emerald-400" : "font-medium text-destructive"}>
            {toPersianDigits(variance.toLocaleString("en-US"))}
          </span>
        );
      },
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4 border-b border-border pb-5">
        <div>
          <Button variant="ghost" size="sm" className="mb-2 px-0" onClick={() => router.push("/admin/inventory-counts")}>
            <ArrowRight className="ms-1 h-4 w-4" /> بازگشت به شمارش‌ها
          </Button>
          <h2 className="flex items-center gap-2 text-xl font-bold"><ClipboardCheck className="h-5 w-5 text-primary" /> ورود و بررسی شمارش</h2>
          {count && <p className="mt-1 text-sm text-muted-foreground">انبار: <span className="font-mono" dir="ltr">{count.warehouse_id}</span></p>}
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
      </div>

      {count && (
        <Card className="border-s-4 border-s-primary p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-3 text-sm">
              <Badge variant={count.status === "posted" ? "default" : count.status === "review" ? "secondary" : "outline"}>
                {count.status === "draft" ? "پیش‌نویس" : count.status === "counting" ? "در حال شمارش" : count.status === "review" ? "آماده بررسی" : count.status === "posted" ? "ثبت‌شده" : "لغوشده"}
              </Badge>
              <span>{toPersianDigits(`${count.counted_line_count} از ${count.line_count} ردیف وارد شده`)}</span>
              <span className="text-muted-foreground">{toPersianDigits(`${count.variance_line_count} ردیف دارای اختلاف`)}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {isEditable && <Button variant="outline" disabled={saving} onClick={() => void saveLines()}><Save className="ms-1 h-4 w-4" /> ذخیره مقادیر</Button>}
              {count.status === "counting" && <Button disabled={saving} onClick={() => void review()}><Send className="ms-1 h-4 w-4" /> ارسال برای بررسی</Button>}
              {count.status === "review" && <Button disabled={saving} onClick={() => void post()}><AlertTriangle className="ms-1 h-4 w-4" /> ثبت نهایی اختلاف‌ها</Button>}
            </div>
          </div>
        </Card>
      )}

      <DataTable
        columns={columns}
        rows={count?.lines ?? []}
        rowKey={(line) => line.product_variant_id}
        loading={loading}
        error={error}
        emptyMessage="ردیفی در دامنه این شمارش یافت نشد"
      />
    </div>
  );
}
