"use client";

import React, { useState } from "react";
import { ArrowLeftRight, Plus, RefreshCw, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { redirectsApi, type RedirectRule } from "@/lib/api/cms-admin";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const REDIRECTS_QUERY_KEY = "admin-redirects" as const;

export default function AdminRedirectsPage() {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RedirectRule | null>(null);
  const [fromPath, setFromPath] = useState("");
  const [toPath, setToPath] = useState("");
  const [statusCode, setStatusCode] = useState("301");
  const [saving, setSaving] = useState(false);

  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [REDIRECTS_QUERY_KEY],
    queryFn: () => redirectsApi.list(),
    fallbackError: "بارگذاری ریدایرکت‌ها ناموفق بود",
    // This page reported load failures as a toast and left the table empty.
    toastOnError: true,
    toastDescription: "بارگذاری ریدایرکت‌ها ناموفق بود",
  });
  const rules: RedirectRule[] = data ?? [];
  const runMutation = useAdminMutation();

  const openCreate = () => {
    setEditingRule(null);
    setFromPath(""); setToPath(""); setStatusCode("301");
    setOpen(true);
  };

  const openEdit = (r: RedirectRule) => {
    setEditingRule(r);
    setFromPath(r.from_path);
    setToPath(r.to_path);
    setStatusCode(String(r.status_code));
    setOpen(true);
  };

  const toggleActive = async (r: RedirectRule) => {
    const result = await runMutation(
      () => redirectsApi.update(r.id, { is_active: r.is_active === false }),
      {
        fallbackError: "تغییر وضعیت ناموفق بود",
        invalidateKeys: [[REDIRECTS_QUERY_KEY]],
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  const create = async () => {
    if (!fromPath.trim() || !toPath.trim()) {
      toast({ title: "خطا", description: "مسیر مبدأ و مقصد الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    const wasEditing = editingRule !== null;
    const result = await runMutation(
      () => wasEditing
        ? redirectsApi.update(editingRule.id, {
            from_path: fromPath.trim(),
            to_path: toPath.trim(),
            status_code: Number(statusCode),
          })
        : redirectsApi.create({
            from_path: fromPath.trim(),
            to_path: toPath.trim(),
            status_code: Number(statusCode),
          }),
      {
        fallbackError: "ایجاد ناموفق بود",
        invalidateKeys: [[REDIRECTS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({
        title: "موفق",
        description: wasEditing
          ? "ریدایرکت به‌روزرسانی شد"
          : "ریدایرکت ایجاد شد — حداکثر تا یک دقیقه فعال می‌شود",
      });
      setOpen(false);
    } else {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
    setSaving(false);
  };

  const remove = async (id: string) => {
    if (!confirm("این ریدایرکت حذف شود؟")) return;
    const result = await runMutation(
      () => redirectsApi.remove(id),
      {
        fallbackError: "حذف ناموفق بود",
        invalidateKeys: [[REDIRECTS_QUERY_KEY]],
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-primary" />
            مدیریت ریدایرکت‌ها
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            قوانین 301/302 بدون دیپلوی اعمال می‌شوند (حداکثر تا ۱ دقیقه پس از ذخیره)
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 ms-1" />
            ریدایرکت جدید
          </Button>
        </div>
      </div>

      <Card className="p-6">
        {loading ? (
          <div className="flex justify-center py-8">
            <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : rules.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            هنوز ریدایرکتی تعریف نشده است
          </p>
        ) : (
          <div className="space-y-2">
            {rules.map((r) => (
              <div key={r.id} className="flex items-center justify-between rounded-lg border p-3">
                <div className="flex items-center gap-3">
                  <Badge variant={r.status_code === 301 ? "default" : "secondary"}>
                    {toPersianDigits(String(r.status_code))}
                  </Badge>
                  <div dir="ltr" className="text-sm font-mono">
                    {r.from_path} <span className="text-muted-foreground">→</span> {r.to_path}
                  </div>
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs text-muted-foreground">
                    {toPersianDigits(String(r.hit_count))} بازدید
                  </span>
                  <Button
                    size="sm"
                    variant={r.is_active === false ? "outline" : "default"}
                    onClick={() => toggleActive(r)}
                    title={r.is_active === false ? "فعال‌سازی" : "غیرفعال‌سازی"}
                  >
                    {r.is_active === false ? "غیرفعال" : "فعال"}
                  </Button>
                  <Button size="sm" variant="outline" onClick={() => openEdit(r)}>
                    ویرایش
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => remove(r.id)}
                    // Icon-only: names the control for screen readers and lets
                    // a test reach it by meaning rather than by position.
                    aria-label={`حذف ریدایرکت ${r.from_path}`}
                  >
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingRule ? "ویرایش ریدایرکت" : "ریدایرکت جدید"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="redirect-from">مسیر مبدأ (wildcard با /* پشتیبانی می‌شود)</Label>
              <Input id="redirect-from" dir="ltr" value={fromPath} onChange={(e) => setFromPath(e.target.value)} placeholder="/old-page یا /old-blog/*" />
            </div>
            <div className="space-y-2">
              <Label htmlFor="redirect-to">مسیر مقصد</Label>
              <Input id="redirect-to" dir="ltr" value={toPath} onChange={(e) => setToPath(e.target.value)} placeholder="/new-page" />
            </div>
            <div className="space-y-2">
              <Label>کد وضعیت</Label>
              <Select value={statusCode} onValueChange={setStatusCode}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="301">301 — دائمی (SEO منتقل می‌شود)</SelectItem>
                  <SelectItem value="302">302 — موقت</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>انصراف</Button>
            <Button onClick={create} disabled={saving}>
              {saving ? "در حال ذخیره..." : editingRule ? "به‌روزرسانی" : "ایجاد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
