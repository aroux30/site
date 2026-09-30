"use client";

import React, { useState } from "react";
import { Download, FileDown, RefreshCw } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  dataExchangeApi,
  saveBlob,
  type DataExchangeEntity,
  type ExportJob,
} from "@/lib/api/data-exchange";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const DATA_EXCHANGE_EXPORT_QUERY_KEY = "admin-data-exchange-export" as const;

export default function DataExchangeExportPage() {
  const { toast } = useToast();
  const [entityType, setEntityType] = useState("product");
  const [category, setCategory] = useState("");
  const [isActive, setIsActive] = useState<string>("");
  const [creating, setCreating] = useState(false);

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [DATA_EXCHANGE_EXPORT_QUERY_KEY],
    queryFn: async () => {
      const [ents, list] = await Promise.all([
        dataExchangeApi.entities(),
        dataExchangeApi.listExportJobs({ page_size: 50 }),
      ]);
      return { entities: ents, jobs: list.items };
    },
    fallbackError: "دریافت اطلاعات ناموفق بود",
  });
  const entities: DataExchangeEntity[] = data?.entities ?? [];
  const jobs: ExportJob[] = data?.jobs ?? [];
  const runMutation = useAdminMutation();

  const doExport = async () => {
    setCreating(true);
    try {
      const filters: Record<string, unknown> = {};
      if (category.trim()) filters.category = category.trim();
      if (isActive !== "") filters.is_active = isActive === "true";
      const job = await dataExchangeApi.createExportJob(entityType, filters);
      if (job.status === "completed") {
        const blob = await dataExchangeApi.downloadExport(job.id);
        saveBlob(blob, `${job.entity_type}-export.csv`);
        toast({ title: "خروجی آماده شد", description: `${job.row_count ?? 0} ردیف` });
      }
      void load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "خروجی گرفتن ناموفق بود", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const columns: DataTableColumn<ExportJob>[] = [
    {
      key: "entity",
      header: "موجودیت",
      render: (j) => entities.find((e) => e.entity_type === j.entity_type)?.label ?? j.entity_type,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (j) => (
        <Badge variant={j.status === "completed" ? "default" : j.status === "failed" ? "destructive" : "secondary"}>
          {j.status === "completed" ? "تکمیل‌شده" : j.status === "failed" ? "ناموفق" : "در حال پردازش"}
        </Badge>
      ),
    },
    { key: "rows", header: "ردیف‌ها", render: (j) => j.row_count ?? "—" },
    {
      key: "filters",
      header: "فیلترها",
      hideOnMobile: true,
      render: (j) =>
        j.filters && Object.keys(j.filters).length
          ? Object.entries(j.filters)
              .map(([k, v]) => `${k}=${String(v)}`)
              .join("، ")
          : "—",
    },
    {
      key: "created",
      header: "ایجاد",
      hideOnMobile: true,
      render: (j) => (j.created_at ? new Date(j.created_at).toLocaleString("fa-IR") : "—"),
    },
    {
      key: "download",
      header: "دانلود",
      render: (j) =>
        j.status === "completed" ? (
          <Button
            size="sm"
            variant="outline"
            onClick={async () => {
              const blob = await dataExchangeApi.downloadExport(j.id);
              saveBlob(blob, `${j.entity_type}-export.csv`);
            }}
          >
            <Download className="h-3.5 w-3.5 ms-1" />
            CSV
          </Button>
        ) : (
          "—"
        ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h2 className="text-xl font-bold flex items-center gap-2">
          <FileDown className="h-5 w-5 text-primary" />
          خروجی داده (Export)
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          خروجی CSV از موجودیت‌ها با فیلتر اختیاری (دسته‌بندی و وضعیت فعال)
        </p>
      </div>

      <Card className="p-6 space-y-4">
        <h3 className="text-lg font-semibold">export جدید</h3>
        <div className="flex flex-wrap items-center gap-3">
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={entityType}
            onChange={(e) => setEntityType(e.target.value)}
          >
            {entities.map((e) => (
              <option key={e.entity_type} value={e.entity_type}>
                {e.label}
              </option>
            ))}
          </select>
          <Input
            className="w-48"
            placeholder="نامک یا شناسه دسته‌بندی (اختیاری)"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          />
          <select
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={isActive}
            onChange={(e) => setIsActive(e.target.value)}
          >
            <option value="">همه وضعیت‌ها</option>
            <option value="true">فقط فعال</option>
            <option value="false">فقط غیرفعال</option>
          </select>
          <Button onClick={() => void doExport()} disabled={creating}>
            <Download className="h-4 w-4 ms-1" />
            {creating ? "در حال آماده‌سازی..." : "ساخت و دانلود خروجی"}
          </Button>
          <Button variant="ghost" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      </Card>

      <DataTable
        columns={columns}
        rows={jobs}
        rowKey={(j) => j.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز هیچ export ساخته نشده است"
      />
    </div>
  );
}
