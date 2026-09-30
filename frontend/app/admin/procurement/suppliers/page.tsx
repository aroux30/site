"use client";

import { useState } from "react";
import { Factory, Plus, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toPersianDigits } from "@/lib/utils";
import { procurementApi, type Supplier } from "@/lib/api/procurement";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const SUPPLIERS_QUERY_KEY = "admin-procurement-suppliers" as const;

export default function SuppliersPage() {
  const [saving, setSaving] = useState(false);
  // Form-level failures stay in the form; the table's own `error` comes from
  // the query. Sharing one message would blank or mislabel whichever surface
  // did not cause the failure.
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [phone, setPhone] = useState("");
  const [terms, setTerms] = useState("0");

  const {
    data,
    loading,
    error,
    reload: load,
  } = useAdminQuery({
    queryKey: [SUPPLIERS_QUERY_KEY, search.trim()],
    queryFn: () => procurementApi.listSuppliers({ search: search.trim() || undefined }),
    fallbackError: "دریافت تامین‌کننده‌ها ناموفق بود",
  });
  const items: Supplier[] = data?.items ?? [];
  const runMutation = useAdminMutation();

  const create = async () => {
    const parsedTerms = Number(terms);
    if (!name.trim() || !code.trim()) { setFormError("نام و کد تامین‌کننده الزامی است"); return; }
    if (!Number.isInteger(parsedTerms) || parsedTerms < 0) { setFormError("شرط پرداخت باید عدد صحیح غیرمنفی باشد"); return; }
    setSaving(true);
    setFormError(null);
    const result = await runMutation(
      () =>
        procurementApi.createSupplier({
          name: name.trim(),
          code: code.trim(),
          contact_info: phone.trim() ? { phone: phone.trim() } : {},
          payment_terms_days: parsedTerms,
        }),
      {
        fallbackError: "ایجاد تامین‌کننده ناموفق بود",
        invalidateKeys: [[SUPPLIERS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      setName(""); setCode(""); setPhone(""); setTerms("0");
    } else {
      setFormError(result.error);
    }
    setSaving(false);
  };

  const toggleActive = async (supplier: Supplier) => {
    setSaving(true);
    const result = await runMutation(
      () => procurementApi.updateSupplier(supplier.id, { is_active: !supplier.is_active }),
      {
        fallbackError: "به‌روزرسانی تامین‌کننده ناموفق بود",
        invalidateKeys: [[SUPPLIERS_QUERY_KEY]],
      },
    );
    if (!result.ok) setFormError(result.error);
    setSaving(false);
  };

  const columns: DataTableColumn<Supplier>[] = [
    { key: "name", header: "نام", render: (item) => <span className="font-medium">{item.name}</span> },
    { key: "code", header: "کد", render: (item) => <span className="font-mono text-xs" dir="ltr">{item.code}</span> },
    { key: "phone", header: "تماس", hideOnMobile: true, render: (item) => toPersianDigits(String(item.contact_info?.phone ?? "—")) },
    { key: "terms", header: "شرط پرداخت", hideOnMobile: true, render: (item) => toPersianDigits(`${item.payment_terms_days} روز`) },
    { key: "status", header: "وضعیت", render: (item) => item.is_active ? <Badge>فعال</Badge> : <Badge variant="secondary">غیرفعال</Badge> },
    { key: "action", header: "عملیات", render: (item) => (
      <Button size="sm" variant="outline" disabled={saving} onClick={() => void toggleActive(item)}>
        {item.is_active ? "غیرفعال‌سازی" : "فعال‌سازی"}
      </Button>
    ) },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <section className="flex flex-col justify-between gap-4 border-b border-border pb-5 sm:flex-row sm:items-start">
        <div className="max-w-2xl">
          <h2 className="flex items-center gap-2 text-xl font-bold"><Factory className="h-5 w-5 text-primary" /> تامین‌کننده‌ها</h2>
          <p className="mt-1 text-sm leading-6 text-muted-foreground">طرف‌های خرید کالا. این موجودی از فروشندگان مارکت‌پلیس جداست و برای چرخه سفارش خرید استفاده می‌شود.</p>
        </div>
        <Button variant="outline" onClick={() => void load()}><RefreshCw className="ms-1 h-4 w-4" /> تازه‌سازی</Button>
      </section>

      <Card className="border-s-4 border-s-primary p-5">
        <h3 className="mb-4 text-sm font-semibold">ایجاد تامین‌کننده</h3>
        <div className="grid gap-3 md:grid-cols-4">
          <div className="space-y-1.5"><Label htmlFor="supplierName">نام</Label><Input id="supplierName" value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="supplierCode">کد یکتا</Label><Input id="supplierCode" dir="ltr" value={code} onChange={(e) => setCode(e.target.value)} placeholder="SUP-001" /></div>
          <div className="space-y-1.5"><Label htmlFor="supplierPhone">تلفن تماس</Label><Input id="supplierPhone" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)} /></div>
          <div className="space-y-1.5"><Label htmlFor="supplierTerms">شرط پرداخت (روز)</Label><Input id="supplierTerms" dir="ltr" type="number" min="0" inputMode="numeric" value={terms} onChange={(e) => setTerms(e.target.value)} /></div>
        </div>
        <div className="mt-3 flex items-center gap-3">
          <Button disabled={saving} onClick={() => void create()}><Plus className="ms-1 h-4 w-4" /> ایجاد</Button>
          {formError && <span role="alert" className="text-sm text-destructive">{formError}</span>}
        </div>
      </Card>

      <div className="max-w-sm space-y-1.5">
        <Label htmlFor="supplierSearch">جستجو</Label>
        <Input id="supplierSearch" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="نام یا کد تامین‌کننده" />
      </div>

      <DataTable columns={columns} rows={items} rowKey={(item) => item.id} loading={loading} error={error} emptyMessage="تامین‌کننده‌ای ثبت نشده است" emptyDescription="برای شروع چرخه خرید، نخستین تامین‌کننده را بسازید." />
    </div>
  );
}
