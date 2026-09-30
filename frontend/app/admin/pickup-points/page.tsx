"use client";

import React, { useCallback, useEffect, useState } from "react";
import { MapPin, RefreshCw, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { DataTable, type DataTableColumn } from "@/components/admin/data-table";
import { useToast } from "@/components/ui/use-toast";
import { shippingAdminApi, shippingApiExtra, type PickupPoint } from "@/lib/api/shipping";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const EMPTY_FORM = {
  provider: "tipax",
  external_id: "",
  name: "",
  city: "",
  address: "",
  province: "",
  postal_code: "",
  phone: "",
};

export default function AdminPickupPointsPage() {
  const { toast } = useToast();
  const [cityFilter, setCityFilter] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);

  // The city filter is part of the cache key, so changing it refetches and
  // switching back serves the earlier result from cache instead of hitting
  // the server again.
  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: ["admin-pickup-points", cityFilter.trim()],
    queryFn: () =>
      shippingApiExtra.listPickupPoints({
        city: cityFilter.trim() || undefined,
      }),
    fallbackError: "خطا در دریافت نقاط تحویل",
    // This page reported load failures as a toast and left the table empty;
    // keep that behaviour instead of inventing a new one mid-migration.
    toastOnError: true,
  });
  const points: PickupPoint[] = data ?? [];

  const save = async () => {
    if (!form.provider.trim() || !form.external_id.trim() || !form.name.trim()) {
      toast({
        title: "حامل، کد شعبه و نام الزامی است",
        variant: "destructive",
      });
      return;
    }
    if (!form.city.trim() || form.address.trim().length < 5) {
      toast({
        title: "شهر و آدرس کامل (حداقل ۵ نویسه) الزامی است",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      await shippingAdminApi.upsertPickupPoint({
        provider: form.provider.trim(),
        external_id: form.external_id.trim(),
        name: form.name.trim(),
        city: form.city.trim(),
        address: form.address.trim(),
        province: form.province.trim() || null,
        postal_code: form.postal_code.trim() || null,
        phone: form.phone.trim() || null,
      });
      toast({
        title: "نقطه تحویل ثبت شد",
        description: "در صورت وجود، رکورد قبلی همین شعبه بروزرسانی شد.",
        variant: "success",
      });
      setDialogOpen(false);
      setForm(EMPTY_FORM);
      await load();
    } catch {
      toast({ title: "ثبت نقطه تحویل ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const columns: DataTableColumn<PickupPoint>[] = [
    {
      key: "name",
      header: "نام شعبه",
      render: (p) => (
        <div>
          <p className="font-medium">{p.name}</p>
          <p className="font-mono text-[10px] text-muted-foreground" dir="ltr">
            {p.external_id}
          </p>
        </div>
      ),
    },
    {
      key: "provider",
      header: "حامل",
      render: (p) => <Badge variant="outline">{p.provider}</Badge>,
    },
    {
      key: "city",
      header: "شهر",
      render: (p) => `${p.city}${p.province ? ` — ${p.province}` : ""}`,
    },
    {
      key: "address",
      header: "آدرس",
      render: (p) => (
        <span className="line-clamp-1 max-w-xs text-xs text-muted-foreground">
          {p.address}
        </span>
      ),
    },
    {
      key: "phone",
      header: "تلفن",
      render: (p) =>
        p.phone ? (
          <span dir="ltr" className="font-mono text-xs">
            {toPersianDigits(p.phone)}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        ),
    },
    {
      key: "status",
      header: "وضعیت",
      render: (p) => (
        <Badge variant={p.is_active ? "default" : "secondary"}>
          {p.is_active ? "فعال" : "غیرفعال"}
        </Badge>
      ),
    },
  ];

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <MapPin className="h-5 w-5 text-primary" />
            نقاط تحویل حضوری
          </h2>
          <p className="mt-1 text-sm text-muted-foreground">
            شبکه نمایندگی‌های حامل‌ها که در مرحله پرداخت به‌عنوان گزینه
            «تحویل حضوری» به مشتری نمایش داده می‌شود.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="ms-2 h-4 w-4" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setDialogOpen(true)}>
            <Plus className="ms-2 h-4 w-4" />
            نقطه تحویل جدید
          </Button>
        </div>
      </div>

      <Card className="p-4">
        <div className="relative max-w-sm">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={cityFilter}
            onChange={(e) => setCityFilter(e.target.value)}
            placeholder="فیلتر شهر (مثلاً تهران)"
            className="ps-9"
          />
        </div>
      </Card>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <Card className="p-1">
          <DataTable
            columns={columns}
            rows={points}
            rowKey={(p) => p.id}
            loading={loading}
            emptyMessage="نقطه تحویلی ثبت نشده است"
            emptyDescription="با دکمه «نقطه تحویل جدید» اولین شعبه را اضافه کنید."
          />
        </Card>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>نقطه تحویل جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="pp-provider">حامل</Label>
                <select
                  id="pp-provider"
                  value={form.provider}
                  onChange={(e) => setForm((f) => ({ ...f, provider: e.target.value }))}
                  className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="tipax">تیپاکس</option>
                  <option value="post">پست</option>
                  <option value="internal">داخلی</option>
                </select>
              </div>
              <div>
                <Label htmlFor="pp-external">کد شعبه نزد حامل</Label>
                <Input
                  id="pp-external"
                  value={form.external_id}
                  onChange={(e) => setForm((f) => ({ ...f, external_id: e.target.value }))}
                  dir="ltr"
                  className="mt-1"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="pp-name">نام شعبه</Label>
              <Input
                id="pp-name"
                value={form.name}
                onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
                className="mt-1"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="pp-city">شهر</Label>
                <Input
                  id="pp-city"
                  value={form.city}
                  onChange={(e) => setForm((f) => ({ ...f, city: e.target.value }))}
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="pp-province">استان (اختیاری)</Label>
                <Input
                  id="pp-province"
                  value={form.province}
                  onChange={(e) => setForm((f) => ({ ...f, province: e.target.value }))}
                  className="mt-1"
                />
              </div>
            </div>
            <div>
              <Label htmlFor="pp-address">آدرس کامل</Label>
              <Input
                id="pp-address"
                value={form.address}
                onChange={(e) => setForm((f) => ({ ...f, address: e.target.value }))}
                className="mt-1"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="pp-phone">تلفن (اختیاری)</Label>
                <Input
                  id="pp-phone"
                  value={form.phone}
                  onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
                  dir="ltr"
                  className="mt-1"
                />
              </div>
              <div>
                <Label htmlFor="pp-postal">کد پستی (اختیاری)</Label>
                <Input
                  id="pp-postal"
                  value={form.postal_code}
                  onChange={(e) => setForm((f) => ({ ...f, postal_code: e.target.value }))}
                  dir="ltr"
                  className="mt-1"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={save} disabled={saving}>
              {saving ? "در حال ذخیره..." : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
