"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  Percent,
  Plus,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Download,
  FileText,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { toPersianDigits } from "@/lib/utils";
import apiClient from "@/lib/api/client";
import { apiErrorMessage } from "@/lib/api/error-message";
import {
  taxApi,
  saveBlob,
  type TaxHealth,
  type TaxReport,
  type TaxRule,
  type TaxRuleScopeValue,
  type TaxRuleTypeValue,
} from "@/lib/api/tax";
import { useAdminQuery } from "@/lib/api/admin-query";

const TAX_RULES_QUERY_KEY = "admin-tax-rules" as const;
const TAX_CATEGORIES_QUERY_KEY = "admin-tax-categories" as const;
const TAX_REPORT_QUERY_KEY = "admin-tax-report" as const;

const TYPE_LABELS: Record<TaxRuleTypeValue, string> = {
  vat: "ارزش افزوده",
  exempt: "معاف",
  compound: "مرکب",
  withholding: "تکلیفی (کسر از فروشنده)",
};

const TYPE_VARIANTS: Record<TaxRuleTypeValue, "default" | "secondary" | "destructive" | "outline"> = {
  vat: "default",
  exempt: "secondary",
  compound: "outline",
  withholding: "destructive",
};

const SCOPE_LABELS: Record<TaxRuleScopeValue, string> = {
  default: "پیش‌فرض",
  category: "دسته‌بندی",
  product: "کالا",
};

interface CategoryOption {
  id: string;
  name: string;
}

function formatToman(rial: number | undefined | null): string {
  if (rial === undefined || rial === null) return "—";
  return `${toPersianDigits(Math.trunc(rial / 10).toLocaleString("en-US"))} تومان`;
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("fa-IR");
}

const EMPTY_FORM = {
  name: "",
  code: "",
  rule_type: "vat" as TaxRuleTypeValue,
  scope: "default" as TaxRuleScopeValue,
  category_id: "",
  product_id: "",
  rate_percent: "9",
  priority: "0",
  effective_from: "",
  effective_to: "",
  exempt_reason: "",
  description: "",
};

export default function AdminTaxPage() {
  const [tab, setTab] = useState<"rules" | "report">("rules");

  // ── Rules state ──
  const [typeFilter, setTypeFilter] = useState("");
  const [scopeFilter, setScopeFilter] = useState("");

  // ── Create/Edit dialog ──
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<TaxRule | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  // ── Report state ──
  const today = useMemo(() => new Date(), []);
  const [fromDate, setFromDate] = useState(() => {
    const d = new Date();
    d.setMonth(d.getMonth() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [toDate, setToDate] = useState(() => today.toISOString().slice(0, 10));
  const [groupBy, setGroupBy] = useState<"period" | "rule" | "category">("period");
  // CSV export failures belong to the export action, not the report query, so
  // they stay a local message and are shown beside the download button.
  const [csvError, setCsvError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  // Rules and tax health load together: the old Promise.all treated them as
  // one read, and the health banner describes the same rule set the table
  // shows, so splitting them could display a health verdict for a different
  // filter than the visible rows.
  const {
    data: rulesData,
    loading,
    error,
    reload: loadRules,
  } = useAdminQuery({
    queryKey: [TAX_RULES_QUERY_KEY, typeFilter, scopeFilter],
    queryFn: async () => {
      const [list, healthData] = await Promise.all([
        taxApi.listRules({
          rule_type: (typeFilter || undefined) as TaxRuleTypeValue | undefined,
          scope: (scopeFilter || undefined) as TaxRuleScopeValue | undefined,
        }),
        taxApi.health(),
      ]);
      return { rules: list.items, health: healthData };
    },
    fallbackError: "دریافت قواعد مالیاتی ناموفق بود",
  });
  const rules: TaxRule[] = rulesData?.rules ?? [];
  const health: TaxHealth | null = rulesData?.health ?? null;

  // Categories for the override scope dropdown. Failure degraded silently to
  // an empty dropdown in the original, which the query preserves.
  const { data: categoriesData } = useAdminQuery({
    queryKey: [TAX_CATEGORIES_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/catalog/categories");
      const items = Array.isArray(res.data?.items)
        ? res.data.items
        : Array.isArray(res.data)
          ? res.data
          : [];
      return items.map((c: { id: string; name: string }) => ({ id: c.id, name: c.name }));
    },
    fallbackError: "دریافت دسته‌بندی‌ها ناموفق بود",
  });
  const categories: CategoryOption[] = categoriesData ?? [];

  const openCreate = () => {
    setEditing(null);
    setForm({ ...EMPTY_FORM });
    setFormError(null);
    setDialogOpen(true);
  };

  const openEdit = (rule: TaxRule) => {
    setEditing(rule);
    setForm({
      name: rule.name,
      code: rule.code,
      rule_type: rule.rule_type,
      scope: rule.scope,
      category_id: rule.category_id ?? "",
      product_id: rule.product_id ?? "",
      rate_percent: (rule.rate_basis_points / 100).toString(),
      priority: String(rule.priority),
      effective_from: rule.effective_from ? rule.effective_from.slice(0, 10) : "",
      effective_to: rule.effective_to ? rule.effective_to.slice(0, 10) : "",
      exempt_reason: rule.exempt_reason ?? "",
      description: rule.description ?? "",
    });
    setFormError(null);
    setDialogOpen(true);
  };

  const submit = async () => {
    setSaving(true);
    setFormError(null);
    const rateBp = Math.round(parseFloat(form.rate_percent || "0") * 100);
    const payload = {
      name: form.name,
      code: form.code,
      rule_type: form.rule_type,
      scope: form.scope,
      category_id: form.scope === "category" && form.category_id ? form.category_id : null,
      product_id: form.scope === "product" && form.product_id ? form.product_id : null,
      rate_basis_points: rateBp,
      priority: parseInt(form.priority || "0", 10) || 0,
      effective_from: form.effective_from ? new Date(form.effective_from).toISOString() : null,
      effective_to: form.effective_to ? new Date(form.effective_to).toISOString() : null,
      exempt_reason: form.exempt_reason || null,
      description: form.description || null,
    };
    try {
      if (editing) {
        await taxApi.updateRule(editing.id, payload);
      } else {
        await taxApi.createRule(payload);
      }
      setDialogOpen(false);
      await loadRules();
    } catch (e: unknown) {
      const detail =
        (e as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setFormError(detail ?? "ذخیره قاعده ناموفق بود");
    } finally {
      setSaving(false);
    }
  };

  const deactivate = async (rule: TaxRule) => {
    try {
      await taxApi.deactivateRule(rule.id);
      await loadRules();
    } catch (err: unknown) {
      // Action failures used to write into the page-level error, which blanked
      // the table behind the dialog. They belong to the action, so they get
      // their own message.
      setActionError(apiErrorMessage(err, "غیرفعال‌سازی قاعده ناموفق بود"));
    }
  };

  const {
    data: reportData,
    loading: reportLoading,
    error: reportError,
    reload: loadReport,
  } = useAdminQuery({
    queryKey: [TAX_REPORT_QUERY_KEY, fromDate, toDate, groupBy],
    // Only fetched while the report tab is open, matching the old effect.
    enabled: tab === "report",
    queryFn: () =>
      taxApi.report({
        from: new Date(fromDate).toISOString(),
        to: new Date(`${toDate}T23:59:59`).toISOString(),
        group_by: groupBy,
      }),
    fallbackError: "دریافت گزارش مالیات ناموفق بود",
  });
  const report: TaxReport | null = reportData ?? null;

  const downloadCsv = async () => {
    try {
      const blob = await taxApi.reportCsv({
        from: new Date(fromDate).toISOString(),
        to: new Date(`${toDate}T23:59:59`).toISOString(),
        group_by: groupBy,
      });
      saveBlob(blob, `vat-report-${fromDate}-${toDate}-${groupBy}.csv`);
    } catch {
      setCsvError("دریافت فایل CSV ناموفق بود");
    }
  };

  const ruleColumns: DataTableColumn<TaxRule>[] = [
    {
      key: "name",
      header: "نام / کد",
      render: (r) => (
        <div>
          <div className="font-medium">{r.name}</div>
          <div className="font-mono text-[11px] text-muted-foreground">{r.code}</div>
        </div>
      ),
    },
    {
      key: "type",
      header: "نوع",
      render: (r) => (
        <Badge variant={TYPE_VARIANTS[r.rule_type]}>{TYPE_LABELS[r.rule_type]}</Badge>
      ),
    },
    {
      key: "rate",
      header: "نرخ",
      render: (r) => (
        <span className="font-mono">
          {toPersianDigits((r.rate_basis_points / 100).toString())}٪
        </span>
      ),
    },
    {
      key: "scope",
      header: "دامنه",
      hideOnMobile: true,
      render: (r) => SCOPE_LABELS[r.scope],
    },
    {
      key: "effective",
      header: "دوره اثر",
      hideOnMobile: true,
      render: (r) => (
        <span className="text-xs">
          {formatDate(r.effective_from)} ← {formatDate(r.effective_to)}
        </span>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (r) =>
        r.is_active ? (
          <Badge variant="secondary">فعال</Badge>
        ) : (
          <Badge variant="outline">غیرفعال</Badge>
        ),
    },
    {
      key: "actions",
      header: "",
      render: (r) => (
        <div className="flex gap-1">
          <Button variant="outline" size="sm" onClick={() => openEdit(r)}>
            ویرایش
          </Button>
          {r.is_active && (
            <Button variant="ghost" size="sm" onClick={() => void deactivate(r)}>
              غیرفعال
            </Button>
          )}
        </div>
      ),
    },
  ];

  const reportColumns: DataTableColumn<TaxReport["buckets"][number]>[] = [
    { key: "bucket", header: "سطل", render: (b) => <span className="font-mono">{b.bucket}</span> },
    {
      key: "orders",
      header: "تعداد سفارش",
      render: (b) => toPersianDigits(String(b.order_count)),
    },
    {
      key: "taxable",
      header: "مبنای مشمول",
      hideOnMobile: true,
      render: (b) => <span className="font-mono">{formatToman(b.taxable_total_rial)}</span>,
    },
    {
      key: "vat",
      header: "ارزش افزوده",
      render: (b) => <span className="font-mono">{formatToman(b.vat_total_rial)}</span>,
    },
    {
      key: "withholding",
      header: "تکلیفی",
      hideOnMobile: true,
      render: (b) => <span className="font-mono">{formatToman(b.withholding_total_rial)}</span>,
    },
    {
      key: "tax",
      header: "جمع مالیات",
      render: (b) => <span className="font-mono">{formatToman(b.tax_total_rial)}</span>,
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Percent className="h-5 w-5 text-primary" />
            موتور مالیات
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            قواعد مؤثر تاریخ‌دار (ارزش افزوده، معافیت، مرکب، تکلیفی) و گزارش مالیات بر ارزش افزوده
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={() => void loadRules()}>
            <RefreshCw className="h-4 w-4 ms-1" />
            تازه‌سازی
          </Button>
          {tab === "rules" && (
            <Button onClick={openCreate}>
              <Plus className="h-4 w-4 ms-1" />
              قاعده جدید
            </Button>
          )}
        </div>
      </div>

      {health && !health.ok && (
        <Card className="p-4 flex items-center gap-3 border border-destructive/40 bg-destructive/5">
          <ShieldAlert className="h-5 w-5 text-destructive" />
          <div className="text-sm">
            {health.warnings.map((w) => (
              <div key={w}>{w}</div>
            ))}
          </div>
        </Card>
      )}
      {health?.ok && (
        <Card className="p-3 flex items-center gap-3 border border-green-500/40 bg-green-500/5">
          <ShieldCheck className="h-4 w-4 text-green-600" />
          <div className="text-xs text-muted-foreground">
            قاعده پیش‌فرض فعال: <span className="font-mono">{health.default_rule_code}</span> —{" "}
            {toPersianDigits(String(health.active_rules_count))} قاعده فعال
          </div>
        </Card>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border">
        {(
          [
            { id: "rules", label: "قواعد مالیاتی", icon: Percent },
            { id: "report", label: "گزارش ارزش افزوده", icon: FileText },
          ] as const
        ).map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`flex items-center gap-2 px-4 py-2 text-sm font-medium border-b-2 -mb-px transition-colors ${
              tab === t.id
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <t.icon className="h-4 w-4" />
            {t.label}
          </button>
        ))}
      </div>

      {tab === "rules" && (
        <>
          <Card className="p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <FilterSelect
                id="type"
                label="نوع قاعده"
                value={typeFilter}
                onChange={setTypeFilter}
                options={[
                  { value: "", label: "همه انواع" },
                  { value: "vat", label: "ارزش افزوده" },
                  { value: "exempt", label: "معاف" },
                  { value: "compound", label: "مرکب" },
                  { value: "withholding", label: "تکلیفی" },
                ]}
              />
              <FilterSelect
                id="scope"
                label="دامنه"
                value={scopeFilter}
                onChange={setScopeFilter}
                options={[
                  { value: "", label: "همه دامنه‌ها" },
                  { value: "default", label: "پیش‌فرض" },
                  { value: "category", label: "دسته‌بندی" },
                  { value: "product", label: "کالا" },
                ]}
              />
            </div>
          </Card>
          {actionError && (
            <div role="alert" className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive">
              {actionError}
            </div>
          )}
          <DataTable
            columns={ruleColumns}
            rows={rules}
            rowKey={(r) => r.id}
            loading={loading}
            error={error}
            emptyMessage="هنوز قاعده‌ای ثبت نشده است"
          />
        </>
      )}

      {tab === "report" && (
        <>
          <Card className="p-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-4">
              <div className="space-y-1.5">
                <label htmlFor="from" className="block text-[11px] font-medium text-muted-foreground">
                  از تاریخ
                </label>
                <Input id="from" type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <label htmlFor="to" className="block text-[11px] font-medium text-muted-foreground">
                  تا تاریخ
                </label>
                <Input id="to" type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
              </div>
              <FilterSelect
                id="group_by"
                label="گروه‌بندی"
                value={groupBy}
                onChange={(v) => setGroupBy(v as "period" | "rule" | "category")}
                options={[
                  { value: "period", label: "دوره (ماه)" },
                  { value: "rule", label: "قاعده" },
                  { value: "category", label: "دسته‌بندی" },
                ]}
              />
              <div className="flex items-end gap-2">
                <Button onClick={() => void loadReport()} disabled={reportLoading}>
                  {reportLoading ? "در حال محاسبه..." : "محاسبه"}
                </Button>
                {csvError && (
                  <span role="alert" className="text-sm text-destructive">{csvError}</span>
                )}
                <Button variant="outline" onClick={() => void downloadCsv()}>
                  <Download className="h-4 w-4 ms-1" />
                  CSV
                </Button>
              </div>
            </div>
          </Card>

          {report && (
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Card className="p-4">
                <div className="text-[11px] text-muted-foreground">سفارش‌های مشمول</div>
                <div className="text-lg font-bold">{toPersianDigits(String(report.order_count))}</div>
              </Card>
              <Card className="p-4">
                <div className="text-[11px] text-muted-foreground">ارزش افزوده</div>
                <div className="text-lg font-bold">{formatToman(report.vat_total_rial)}</div>
              </Card>
              <Card className="p-4">
                <div className="text-[11px] text-muted-foreground">تکلیفی (کسر)</div>
                <div className="text-lg font-bold">{formatToman(report.withholding_total_rial)}</div>
              </Card>
              <Card className="p-4">
                <div className="text-[11px] text-muted-foreground">جمع مالیات</div>
                <div className="text-lg font-bold">{formatToman(report.tax_total_rial)}</div>
              </Card>
            </div>
          )}

          <DataTable
            columns={reportColumns}
            rows={report?.buckets ?? []}
            rowKey={(b) => b.bucket}
            loading={reportLoading}
            error={reportError}
            emptyMessage="در این بازه داده‌ای نیست"
          />
        </>
      )}

      {/* Create / Edit dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش قاعده" : "قاعده مالیاتی جدید"}</DialogTitle>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-3 py-2">
            <div className="col-span-2 space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">نام</label>
              <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">کد (یکتا)</label>
              <Input
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                className="font-mono"
                disabled={!!editing}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">نرخ (٪)</label>
              <Input
                type="number"
                step="0.01"
                value={form.rate_percent}
                onChange={(e) => setForm({ ...form, rate_percent: e.target.value })}
              />
            </div>
            <FilterSelect
              id="f-type"
              label="نوع"
              value={form.rule_type}
              onChange={(v) => setForm({ ...form, rule_type: v as TaxRuleTypeValue })}
              options={[
                { value: "vat", label: "ارزش افزوده" },
                { value: "exempt", label: "معاف" },
                { value: "compound", label: "مرکب" },
                { value: "withholding", label: "تکلیفی" },
              ]}
            />
            <FilterSelect
              id="f-scope"
              label="دامنه"
              value={form.scope}
              onChange={(v) => setForm({ ...form, scope: v as TaxRuleScopeValue })}
              options={[
                { value: "default", label: "پیش‌فرض" },
                { value: "category", label: "دسته‌بندی" },
                { value: "product", label: "کالا" },
              ]}
            />
            {form.scope === "category" && (
              <div className="col-span-2">
                <FilterSelect
                  id="f-cat"
                  label="دسته‌بندی"
                  value={form.category_id}
                  onChange={(v) => setForm({ ...form, category_id: v })}
                  options={[
                    { value: "", label: "— انتخاب کنید —" },
                    ...categories.map((c) => ({ value: c.id, label: c.name })),
                  ]}
                />
              </div>
            )}
            {form.scope === "product" && (
              <div className="col-span-2 space-y-1.5">
                <label className="text-[11px] font-medium text-muted-foreground">شناسه کالا (UUID)</label>
                <Input
                  value={form.product_id}
                  onChange={(e) => setForm({ ...form, product_id: e.target.value })}
                  className="font-mono"
                />
              </div>
            )}
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">از تاریخ اثر</label>
              <Input
                type="date"
                value={form.effective_from}
                onChange={(e) => setForm({ ...form, effective_from: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">تا تاریخ اثر</label>
              <Input
                type="date"
                value={form.effective_to}
                onChange={(e) => setForm({ ...form, effective_to: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[11px] font-medium text-muted-foreground">اولویت</label>
              <Input
                type="number"
                value={form.priority}
                onChange={(e) => setForm({ ...form, priority: e.target.value })}
              />
            </div>
            {form.rule_type === "exempt" && (
              <div className="col-span-2 space-y-1.5">
                <label className="text-[11px] font-medium text-muted-foreground">دلیل معافیت</label>
                <Input
                  value={form.exempt_reason}
                  onChange={(e) => setForm({ ...form, exempt_reason: e.target.value })}
                />
              </div>
            )}
          </div>
          {formError && <p className="text-sm text-destructive">{formError}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void submit()} disabled={saving}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}