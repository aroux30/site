"use client";

import React, { useState } from "react";
import { ScrollText, RefreshCw, Search, History, ChevronDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import {
  auditApi,
  changeLogApi,
  type AuditLog,
  type EntityChange,
  type TrackedEntitySummary,
} from "@/lib/api/audit";
import { useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const AUDIT_LOGS_QUERY_KEY = "admin-audit-logs" as const;
const AUDIT_CHANGES_QUERY_KEY = "admin-audit-changes" as const;

const ENTITY_TYPE_LABELS: Record<string, string> = {
  product: "محصول",
  variant: "واریانت",
  discount: "تخفیف",
  tax_rule: "قاعده مالیات",
  reorder_rule: "قاعده سفارش مجدد",
  vendor: "فروشنده",
  wallet: "کیف پول",
  price_list_rule: "قاعده قیمت‌گذاری",
};

const OPERATION_LABELS: Record<string, string> = {
  create: "ایجاد",
  update: "ویرایش",
  delete: "حذف",
};

const SOURCE_LABELS: Record<string, string> = {
  api: "API",
  admin: "پنل مدیریت",
  service: "سرویس",
  seed: "Seed",
};

function ChangeDiffRow({ change }: { change: EntityChange }) {
  return (
    <div className="mt-3 space-y-2 border-t pt-3">
      <div className="flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
        <Badge variant="outline">{OPERATION_LABELS[change.operation] ?? change.operation}</Badge>
        <Badge variant="secondary">{SOURCE_LABELS[change.source] ?? change.source}</Badge>
        {change.actor_type === "user" && change.actor_id && (
          <span className="font-mono" dir="ltr">{change.actor_id.slice(0, 8)}…</span>
        )}
        {change.actor_type !== "user" && (
          <span>{change.actor_type === "celery" ? "کار پس‌زمینه" : "سیستم"}</span>
        )}
        {change.truncated && (
          <Badge variant="destructive" className="text-[10px]">مقدار بریده‌شده</Badge>
        )}
      </div>
      <div className="space-y-1.5">
        {change.changed_fields.map((f, idx) => (
          <div
            key={idx}
            className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-center gap-2 rounded bg-muted/40 p-2 text-xs"
          >
            <div className="min-w-0">
              <span className="block text-[10px] text-muted-foreground mb-0.5">قبل</span>
              <code dir="ltr" className="block truncate text-rose-600 dark:text-rose-400">
                {f.old_value === null ? "—" : String(f.old_value)}
              </code>
            </div>
            <div className="text-center">
              <span className="block text-[10px] font-semibold text-muted-foreground" dir="ltr">
                {f.field}
              </span>
              <span className="text-muted-foreground">←</span>
            </div>
            <div className="min-w-0">
              <span className="block text-[10px] text-muted-foreground mb-0.5">بعد</span>
              <code dir="ltr" className="block truncate text-emerald-600 dark:text-emerald-400">
                {f.new_value === null ? "—" : String(f.new_value)}
              </code>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Audit trail browser (WordPress-style activity log).
 * The backend and typed client existed, but /admin/exceptions is an anomaly
 * console — not a filterable audit history. This is the missing surface.
 * The "تغییرات فیلدها" tab is the ERP #9 field-level change log.
 */
export default function AdminAuditPage() {
  const { toast } = useToast();
  const [tab, setTab] = useState<"actions" | "changes">("actions");
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  // ── Field-level change log state ──
  const [changesPage, setChangesPage] = useState(1);
  const [entityFilter, setEntityFilter] = useState("");
  const [fieldFilter, setFieldFilter] = useState("");
  const [expandedChange, setExpandedChange] = useState<string | null>(null);

  // Two independent queries behind two tabs. Each tab's failure is reported on
  // its own — one screen's outage must not blank the other tab's data.
  const {
    data: changesData,
    loading: changesLoading,
    reload: loadChanges,
  } = useAdminQuery({
    queryKey: [AUDIT_CHANGES_QUERY_KEY, changesPage, entityFilter, fieldFilter],
    // Only fetched while the changes tab is open, matching the old effect.
    enabled: tab === "changes",
    queryFn: async () => {
      const [res, summaries] = await Promise.all([
        changeLogApi.list({
          page: changesPage,
          page_size: 25,
          entity_type: entityFilter || undefined,
          field: fieldFilter.trim() || undefined,
        }),
        changeLogApi.entities(),
      ]);
      return { changes: res.items, total: res.total, summaries };
    },
    fallbackError: "خطا در دریافت تاریخچه تغییرات",
    toastOnError: true,
    toastDescription: "دسترسی audit:read لازم است.",
  });
  const changes: EntityChange[] = changesData?.changes ?? [];
  const changesTotal = changesData?.total ?? 0;
  const entitySummaries: TrackedEntitySummary[] = changesData?.summaries ?? [];

  const {
    data: logsData,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [AUDIT_LOGS_QUERY_KEY, page, actionFilter, resourceFilter],
    queryFn: () =>
      auditApi.listAuditLogs({
        page,
        page_size: 25,
        action: actionFilter.trim() || undefined,
        resource: resourceFilter.trim() || undefined,
      }),
    fallbackError: "خطا در دریافت لاگ audit",
    toastOnError: true,
    toastDescription: "دسترسی audit:read لازم است.",
  });
  const logs: AuditLog[] = logsData?.items ?? [];
  const total = logsData?.total ?? 0;

  const changesPages = Math.max(1, Math.ceil(changesTotal / 25));
  const pages = Math.max(1, Math.ceil(total / 25));

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <ScrollText className="h-5 w-5 text-primary" />
            گزارش رویدادها (Audit Trail)
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            تاریخچه تغییرات حساس سیستم — قابل فیلتر بر اساس عملیات و منبع
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={tab === "actions" ? load : loadChanges}
        >
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      {/* Tab selector */}
      <div className="flex gap-2 border-b">
        <button
          onClick={() => setTab("actions")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "actions"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <ScrollText className="h-4 w-4 inline ms-1.5" />
          رویدادها
        </button>
        <button
          onClick={() => setTab("changes")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            tab === "changes"
              ? "border-b-2 border-primary text-primary"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <History className="h-4 w-4 inline ms-1.5" />
          تاریخچه تغییرات فیلدها
        </button>
      </div>

      {tab === "changes" ? (
        <ChangeLogTab
          changes={changes}
          loading={changesLoading}
          total={changesTotal}
          page={changesPage}
          pages={changesPages}
          entityFilter={entityFilter}
          fieldFilter={fieldFilter}
          expandedChange={expandedChange}
          entitySummaries={entitySummaries}
          onEntityFilter={(v) => {
            setEntityFilter(v);
            setChangesPage(1);
          }}
          onFieldFilter={(v) => {
            setFieldFilter(v);
            setChangesPage(1);
          }}
          onToggleExpand={(id) =>
            setExpandedChange(expandedChange === id ? null : id)
          }
          onPageChange={setChangesPage}
        />
      ) : (
        <>
      <Card className="p-4">
        <div className="flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                setPage(1);
              }}
              placeholder="فیلتر عملیات (مثلاً cms_page.updated)"
              className="ps-9"
              dir="ltr"
            />
          </div>
          <Input
            value={resourceFilter}
            onChange={(e) => {
              setResourceFilter(e.target.value);
              setPage(1);
            }}
            placeholder="منبع (resource)"
            dir="ltr"
            className="sm:w-64"
          />
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : logs.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          رکوردی یافت نشد
        </Card>
      ) : (
        <div className="space-y-2">
          {logs.map((log) => (
            <Card key={log.id} className="p-3">
              <button
                className="flex w-full items-center justify-between text-right"
                onClick={() => setExpanded(expanded === log.id ? null : log.id)}
              >
                <div className="flex items-center gap-3">
                  <Badge variant="outline" className="font-mono text-xs" dir="ltr">
                    {log.action}
                  </Badge>
                  <span className="text-xs text-muted-foreground font-mono" dir="ltr">
                    {log.resource}
                  </span>
                  {log.ip_address && (
                    <span className="text-[10px] text-muted-foreground font-mono" dir="ltr">
                      {log.ip_address}
                    </span>
                  )}
                </div>
                <span className="text-[11px] text-muted-foreground">
                  {toPersianDigits(new Date(log.created_at).toLocaleString("fa-IR"))}
                </span>
              </button>
              {expanded === log.id && (
                <div className="mt-3 space-y-2 border-t pt-3 text-xs">
                  {log.actor_id && (
                    <p className="text-muted-foreground">
                      کاربر عامل: <span className="font-mono" dir="ltr">{log.actor_id}</span>
                    </p>
                  )}
                  {log.before && (
                    <div>
                      <p className="mb-1 text-muted-foreground">قبل:</p>
                      <pre dir="ltr" className="overflow-x-auto rounded bg-muted/50 p-2 font-mono text-[11px]">
                        {JSON.stringify(log.before, null, 2)}
                      </pre>
                    </div>
                  )}
                  {log.after && (
                    <div>
                      <p className="mb-1 text-muted-foreground">بعد:</p>
                      <pre dir="ltr" className="overflow-x-auto rounded bg-muted/50 p-2 font-mono text-[11px]">
                        {JSON.stringify(log.after, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            قبلی
          </Button>
          <span className="text-sm text-muted-foreground">
            صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(pages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => setPage((p) => p + 1)}
          >
            بعدی
          </Button>
        </div>
      )}
        </>
      )}
    </div>
  );
}

// ── Field-level change log tab (ERP feature #9) ─────────────────────────────

function ChangeLogTab({
  changes,
  loading,
  total,
  page,
  pages,
  entityFilter,
  fieldFilter,
  expandedChange,
  entitySummaries,
  onEntityFilter,
  onFieldFilter,
  onToggleExpand,
  onPageChange,
}: {
  changes: EntityChange[];
  loading: boolean;
  total: number;
  page: number;
  pages: number;
  entityFilter: string;
  fieldFilter: string;
  expandedChange: string | null;
  entitySummaries: TrackedEntitySummary[];
  onEntityFilter: (v: string) => void;
  onFieldFilter: (v: string) => void;
  onToggleExpand: (id: string) => void;
  onPageChange: (p: number) => void;
}) {
  return (
    <div className="space-y-4">
      {entitySummaries.length > 0 && (
        <Card className="p-3">
          <p className="mb-2 text-xs font-medium text-muted-foreground">
            موجودیت‌های ردیابی‌شده
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => onEntityFilter("")}
              className={`rounded-full px-3 py-1 text-xs transition-colors ${
                entityFilter === ""
                  ? "bg-primary text-primary-foreground"
                  : "bg-muted hover:bg-muted/80"
              }`}
            >
              همه
            </button>
            {entitySummaries.map((e) => (
              <button
                key={e.entity_type}
                onClick={() => onEntityFilter(e.entity_type)}
                className={`rounded-full px-3 py-1 text-xs transition-colors ${
                  entityFilter === e.entity_type
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted hover:bg-muted/80"
                }`}
              >
                {ENTITY_TYPE_LABELS[e.entity_type] ?? e.entity_type}
                <span className="ms-1 text-[10px] opacity-75">
                  ({toPersianDigits(String(e.row_count))})
                </span>
              </button>
            ))}
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={fieldFilter}
            onChange={(e) => onFieldFilter(e.target.value)}
            placeholder="فیلتر نام فیلد (مثلاً price)"
            className="ps-9"
            dir="ltr"
          />
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : changes.length === 0 ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          هنوز تغییری ثبت نشده است. تغییرات پس از ویرایش قیمت، تخفیف، مالیات،
          کمیسیون فروشنده یا موجودی انبار اینجا نمایش داده می‌شوند.
        </Card>
      ) : (
        <div className="space-y-2">
          {changes.map((ch) => (
            <Card key={ch.id} className="p-3">
              <button
                className="flex w-full items-center justify-between text-right"
                onClick={() => onToggleExpand(ch.id)}
              >
                <div className="flex items-center gap-2 min-w-0">
                  <ChevronDown
                    className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
                      expandedChange === ch.id ? "rotate-180" : ""
                    }`}
                  />
                  <Badge variant="outline" className="shrink-0">
                    {ENTITY_TYPE_LABELS[ch.entity_type] ?? ch.entity_type}
                  </Badge>
                  <span
                    className="truncate text-xs text-muted-foreground font-mono"
                    dir="ltr"
                  >
                    {ch.entity_id.slice(0, 8)}…
                  </span>
                  <span className="shrink-0 text-[11px] text-muted-foreground">
                    {toPersianDigits(String(ch.changed_fields.length))} فیلد
                  </span>
                </div>
                <span className="shrink-0 text-[11px] text-muted-foreground">
                  {toPersianDigits(new Date(ch.occurred_at).toLocaleString("fa-IR"))}
                </span>
              </button>
              {expandedChange === ch.id && <ChangeDiffRow change={ch} />}
            </Card>
          ))}
        </div>
      )}

      {total > 0 && (
        <p className="text-center text-xs text-muted-foreground">
          مجموع {toPersianDigits(String(total))} تغییر ثبت‌شده
        </p>
      )}

      {pages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => onPageChange(page - 1)}
          >
            قبلی
          </Button>
          <span className="text-sm text-muted-foreground">
            صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(pages))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= pages}
            onClick={() => onPageChange(page + 1)}
          >
            بعدی
          </Button>
        </div>
      )}
    </div>
  );
}
