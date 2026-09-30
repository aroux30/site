"use client";

import React, { useMemo, useState } from "react";
import {
  BookOpen,
  ChevronDown,
  ChevronLeft,
  Plus,
  RefreshCw,
  Sprout,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { FilterSelect } from "@/components/admin/filter-select";
import { toPersianDigits } from "@/lib/utils";
import {
  accountingApi,
  type Account,
  type AccountType,
} from "@/lib/api/accounting";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const ACCOUNT_QUERY_KEY = "admin-accounts" as const;

const TYPE_LABELS: Record<AccountType, string> = {
  asset: "دارایی",
  liability: "بدهی",
  equity: "حقوق صاحبان سهام",
  revenue: "درآمد",
  expense: "هزینه",
};

const TYPE_VARIANTS: Record<
  AccountType,
  "default" | "secondary" | "destructive" | "outline"
> = {
  asset: "default",
  liability: "secondary",
  equity: "outline",
  revenue: "default",
  expense: "destructive",
};

interface AccountNode extends Account {
  depth: number;
}

/** Flatten the chart into tree order (parents before their children). */
function buildTree(accounts: Account[]): AccountNode[] {
  const byParent = new Map<string | null, Account[]>();
  for (const account of accounts) {
    const key = account.parent_id ?? null;
    const bucket = byParent.get(key) ?? [];
    bucket.push(account);
    byParent.set(key, bucket);
  }
  for (const bucket of byParent.values()) {
    bucket.sort((a, b) => a.code.localeCompare(b.code));
  }

  const out: AccountNode[] = [];
  const seen = new Set<string>();
  const walk = (parentId: string | null, depth: number): void => {
    for (const account of byParent.get(parentId) ?? []) {
      if (seen.has(account.id)) continue;
      seen.add(account.id);
      out.push({ ...account, depth });
      walk(account.id, depth + 1);
    }
  };
  walk(null, 0);

  // Orphans (a parent that was filtered out or is missing) still render.
  for (const account of accounts) {
    if (!seen.has(account.id)) out.push({ ...account, depth: 0 });
  }
  return out;
}

export default function AdminAccountingAccountsPage() {
  const { toast } = useToast();
  const [typeFilter, setTypeFilter] = useState("");
  const [activeFilter, setActiveFilter] = useState("");
  const [seeding, setSeeding] = useState(false);
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({
    code: "",
    name_fa: "",
    type: "asset" as AccountType,
    parent_id: "",
    description: "",
  });
  const [saving, setSaving] = useState(false);

  // The filters are part of the cache key, so changing one refetches and
  // switching back serves the earlier result from cache.
  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [ACCOUNT_QUERY_KEY, typeFilter, activeFilter],
    queryFn: () =>
      accountingApi.listAccounts({
        type: (typeFilter || undefined) as AccountType | undefined,
        is_active: activeFilter === "" ? undefined : activeFilter === "true",
      }),
    fallbackError: "دریافت کدینگ حساب‌ها ناموفق بود",
  });
  const accounts: Account[] = data?.items ?? [];

  const tree = useMemo(() => buildTree(accounts), [accounts]);

  const runMutation = useAdminMutation();

  const doSeed = async () => {
    setSeeding(true);
    const result = await runMutation(() => accountingApi.seedAccounts(), {
      fallbackError: "ایجاد کدینگ ناموفق بود",
      invalidateKeys: [[ACCOUNT_QUERY_KEY]],
      onSuccess: (data) =>
        toast({
          title: "کدینگ استاندارد ایجاد شد",
          description: `${toPersianDigits(data.total)} حساب فعال است`,
        }),
    });
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setSeeding(false);
  };

  const doCreate = async () => {
    if (!form.code.trim() || !form.name_fa.trim()) {
      toast({ title: "کد و نام حساب الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    const result = await runMutation(
      () =>
        accountingApi.createAccount({
          code: form.code.trim(),
          name_fa: form.name_fa.trim(),
          type: form.type,
          parent_id: form.parent_id || null,
          description: form.description.trim() || null,
        }),
      {
        fallbackError: "ایجاد حساب ناموفق بود",
        invalidateKeys: [[ACCOUNT_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({ title: "حساب ایجاد شد" });
      setShowCreate(false);
      setForm({ code: "", name_fa: "", type: "asset", parent_id: "", description: "" });
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setSaving(false);
  };

  const toggleActive = async (account: Account) => {
    const result = await runMutation(
      () => accountingApi.updateAccount(account.id, { is_active: !account.is_active }),
      {
        fallbackError: "تغییر وضعیت ناموفق بود",
        invalidateKeys: [[ACCOUNT_QUERY_KEY]],
        onSuccess: () =>
          toast({
            title: account.is_active ? "حساب غیرفعال شد" : "حساب فعال شد",
            description: account.name_fa,
          }),
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const columns: DataTableColumn<AccountNode>[] = [
    {
      key: "code",
      header: "کد حساب",
      render: (a) => (
        <span className="flex items-center gap-2 font-mono">
          {a.depth > 0 && (
            <span
              className="inline-block"
              style={{ width: `${a.depth * 14}px` }}
              aria-hidden="true"
            />
          )}
          {a.depth > 0 && <ChevronLeft className="h-3 w-3 text-muted-foreground" />}
          {toPersianDigits(a.code)}
        </span>
      ),
    },
    {
      key: "name",
      header: "نام حساب",
      render: (a) => (
        <span className={a.depth === 0 ? "font-bold" : ""}>{a.name_fa}</span>
      ),
    },
    {
      key: "type",
      header: "نوع",
      render: (a) => <Badge variant={TYPE_VARIANTS[a.type]}>{TYPE_LABELS[a.type]}</Badge>,
    },
    {
      key: "status",
      header: "وضعیت",
      render: (a) =>
        a.is_active ? (
          <Badge variant="secondary">فعال</Badge>
        ) : (
          <Badge variant="outline">غیرفعال</Badge>
        ),
    },
    {
      key: "description",
      header: "توضیح",
      hideOnMobile: true,
      render: (a) => (
        <span className="text-xs text-muted-foreground">{a.description ?? "—"}</span>
      ),
    },
    {
      key: "actions",
      header: "",
      render: (a) => (
        <Button variant="ghost" size="sm" onClick={() => void toggleActive(a)}>
          {a.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}
        </Button>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <BookOpen className="h-5 w-5 text-primary" />
            کدینگ حساب‌ها
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            ساختار درختی حساب‌ها بر اساس استاندارد حسابداری ایران — کد حساب در قواعد ثبت
            خودکار اسناد استفاده می‌شود، بنابراین قابل تغییر نیست.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-1" />
            تازه‌سازی
          </Button>
          <Button variant="outline" onClick={() => void doSeed()} disabled={seeding}>
            <Sprout className="h-4 w-4 ms-1" />
            {seeding ? "در حال ایجاد..." : "ایجاد کدینگ استاندارد"}
          </Button>
          <Button onClick={() => setShowCreate((v) => !v)}>
            <Plus className="h-4 w-4 ms-1" />
            حساب جدید
          </Button>
        </div>
      </div>

      {showCreate && (
        <Card className="p-4">
          <h3 className="mb-3 flex items-center gap-2 text-sm font-bold">
            <ChevronDown className="h-4 w-4" />
            افزودن حساب
          </h3>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-1.5">
              <label htmlFor="acc-code" className="block text-[11px] font-medium text-muted-foreground">
                کد حساب
              </label>
              <input
                id="acc-code"
                value={form.code}
                onChange={(e) => setForm({ ...form, code: e.target.value })}
                placeholder="مثلاً 1006"
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="acc-name" className="block text-[11px] font-medium text-muted-foreground">
                نام حساب (فارسی)
              </label>
              <input
                id="acc-name"
                value={form.name_fa}
                onChange={(e) => setForm({ ...form, name_fa: e.target.value })}
                placeholder="مثلاً تنخواه گردان"
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-xs"
              />
            </div>
            <FilterSelect
              id="acc-type"
              label="نوع حساب"
              value={form.type}
              onChange={(v) => setForm({ ...form, type: v as AccountType })}
              options={[
                { value: "asset", label: "دارایی" },
                { value: "liability", label: "بدهی" },
                { value: "equity", label: "حقوق صاحبان سهام" },
                { value: "revenue", label: "درآمد" },
                { value: "expense", label: "هزینه" },
              ]}
            />
            <FilterSelect
              id="acc-parent"
              label="حساب والد"
              value={form.parent_id}
              onChange={(v) => setForm({ ...form, parent_id: v })}
              options={[
                { value: "", label: "بدون والد (گروه اصلی)" },
                ...accounts.map((a) => ({
                  value: a.id,
                  label: `${a.code} — ${a.name_fa}`,
                })),
              ]}
            />
            <div className="space-y-1.5 sm:col-span-2">
              <label htmlFor="acc-desc" className="block text-[11px] font-medium text-muted-foreground">
                توضیح
              </label>
              <input
                id="acc-desc"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                className="h-10 w-full rounded-md border border-input bg-background px-3 text-xs"
              />
            </div>
          </div>
          <div className="mt-4 flex items-center gap-2">
            <Button onClick={() => void doCreate()} disabled={saving}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
            <Button variant="outline" onClick={() => setShowCreate(false)}>
              انصراف
            </Button>
          </div>
        </Card>
      )}

      <Card className="p-4">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <FilterSelect
            id="acc-type-filter"
            label="نوع حساب"
            value={typeFilter}
            onChange={setTypeFilter}
            options={[
              { value: "", label: "همه انواع" },
              { value: "asset", label: "دارایی" },
              { value: "liability", label: "بدهی" },
              { value: "equity", label: "حقوق صاحبان سهام" },
              { value: "revenue", label: "درآمد" },
              { value: "expense", label: "هزینه" },
            ]}
          />
          <FilterSelect
            id="acc-active-filter"
            label="وضعیت"
            value={activeFilter}
            onChange={setActiveFilter}
            options={[
              { value: "", label: "همه حساب‌ها" },
              { value: "true", label: "فعال" },
              { value: "false", label: "غیرفعال" },
            ]}
          />
        </div>
      </Card>

      <DataTable
        columns={columns}
        rows={tree}
        rowKey={(a) => a.id}
        loading={loading}
        error={error}
        emptyMessage="هنوز حسابی تعریف نشده است"
        emptyDescription="برای شروع، کدینگ استاندارد را ایجاد کنید"
      />
    </div>
  );
}
