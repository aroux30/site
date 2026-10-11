"use client";

import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import {
  ArrowLeftRight,
  Download,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
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
import { useConfirm } from "@/components/ui/confirm-dialog";
import { redirectsApi, type RedirectRule } from "@/lib/api/cms-admin";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const REDIRECTS_QUERY_KEY = "admin-redirects" as const;

export default function AdminRedirectsPage() {
  const { toast } = useToast();
  const confirm = useConfirm();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);
  const [editingRule, setEditingRule] = useState<RedirectRule | null>(null);
  const [fromPath, setFromPath] = useState("");
  const [toPath, setToPath] = useState("");
  const [statusCode, setStatusCode] = useState("301");
  const [isRegex, setIsRegex] = useState(false);
  const [note, setNote] = useState("");
  const [saving, setSaving] = useState(false);
  const importInputRef = useRef<HTMLInputElement | null>(null);

  // 410/451 are terminal: they carry no destination, so the target field is
  // hidden and its value cleared — a target with those codes is rejected by
  // the backend, and showing a field the server will reject is a trap.
  const targetless = statusCode === "410" || statusCode === "451";

  // The 404 monitor's "redirect" button links here with `?from=<dead path>`:
  // open the create dialog with the path pre-filled, so fixing a broken URL
  // is one click from the row that found it. Runs once — a writer who clears
  // the field must not have it re-filled on the next render.
  const presetFrom = searchParams.get("from");
  const presetApplied = React.useRef(false);
  useEffect(() => {
    if (!presetFrom || presetApplied.current) return;
    presetApplied.current = true;
    setEditingRule(null);
    setFromPath(presetFrom);
    setToPath("");
    setStatusCode("301");
    setOpen(true);
  }, [presetFrom]);

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
    setIsRegex(false); setNote("");
    setOpen(true);
  };

  const openEdit = (r: RedirectRule) => {
    setEditingRule(r);
    setFromPath(r.from_path);
    setToPath(r.to_path ?? "");
    setStatusCode(String(r.status_code));
    setIsRegex(Boolean(r.is_regex));
    setNote(r.note ?? "");
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
    if (!fromPath.trim()) {
      toast({ title: "خطا", description: "مسیر مبدأ الزامی است", variant: "destructive" });
      return;
    }
    if (!targetless && !toPath.trim()) {
      toast({ title: "خطا", description: "مسیر مقصد الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    const wasEditing = editingRule !== null;
    const payload = {
      from_path: fromPath.trim(),
      to_path: targetless ? null : toPath.trim(),
      status_code: Number(statusCode),
      is_regex: isRegex,
      note: note.trim() || null,
    };
    const result = await runMutation(
      () => wasEditing
        ? redirectsApi.update(editingRule.id, payload)
        : redirectsApi.create(payload),
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

  const exportCsv = async () => {
    try {
      const blob = await redirectsApi.exportCsv();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "redirects.csv";
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      toast({ title: "خروجی CSV ناموفق بود", variant: "destructive" });
    }
  };

  const importCsv = async (file: File) => {
    const content = await file.text();
    const result = await runMutation(
      () => redirectsApi.importCsv(content),
      {
        fallbackError: "ایمپورت CSV ناموفق بود",
        invalidateKeys: [[REDIRECTS_QUERY_KEY]],
      },
    );
    if (!result.ok) {
      toast({ title: "خطا", description: result.error, variant: "destructive" });
      return;
    }
    const data = result.data as { created: number; updated: number; errors: Array<{ line: number; error: string }> };
    const base = `${toPersianDigits(String(data.created))} ایجاد، ${toPersianDigits(String(data.updated))} به‌روزرسانی`;
    toast({
      title: "ایمپورت انجام شد",
      description:
        data.errors.length > 0
          ? `${base} — ${toPersianDigits(String(data.errors.length))} خطا (سطر ${data.errors.map((e) => toPersianDigits(String(e.line))).join("، ")})`
          : base,
      variant: data.errors.length > 0 ? "destructive" : undefined,
    });
  };

  const remove = async (id: string) => {
    const ok = await confirm({
      title: "حذف ریدایرکت",
      description: "این ریدایرکت حذف شود؟",
      confirmLabel: "حذف",
      destructive: true,
    });
    if (!ok) return;
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
          <h1 className="text-xl font-bold flex items-center gap-2">
            <ArrowLeftRight className="h-5 w-5 text-primary" />
            مدیریت ریدایرکت‌ها
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            قوانین 301/302/307/308/410/451 (با پشتیبانی Regex) بدون دیپلوی اعمال می‌شوند
            — حداکثر تا ۱ دقیقه پس از ذخیره
          </p>
        </div>
        <div className="flex gap-2">
          <input
            ref={importInputRef}
            type="file"
            accept=".csv,text/csv"
            className="hidden"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void importCsv(file);
              e.target.value = "";
            }}
          />
          <Button variant="outline" size="sm" onClick={exportCsv} title="خروجی CSV">
            <Download className="h-4 w-4 ms-2" />
            خروجی
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => importInputRef.current?.click()}
            title="ایمپورت CSV (source,target,status,regex,note)"
          >
            <Upload className="h-4 w-4 ms-2" />
            ایمپورت
          </Button>
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
                  {r.is_regex && (
                    <Badge variant="outline" title="الگوی Regex">
                      Regex
                    </Badge>
                  )}
                  <div dir="ltr" className="text-sm font-mono">
                    {r.from_path} <span className="text-muted-foreground">→</span>{" "}
                    {r.to_path ?? "—"}
                  </div>
                  {r.note && (
                    <span className="text-xs text-muted-foreground">{r.note}</span>
                  )}
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
              <Label htmlFor="redirect-from">
                مسیر مبدأ{" "}
                {isRegex
                  ? "(الگوی Regex، مثل ^/products/(\\d+)$)"
                  : "(wildcard با /* پشتیبانی می‌شود)"}
              </Label>
              <Input
                id="redirect-from"
                dir="ltr"
                value={fromPath}
                onChange={(e) => setFromPath(e.target.value)}
                placeholder={isRegex ? "^/products/(\\d+)$" : "/old-page یا /old-blog/*"}
              />
            </div>
            {!targetless && (
              <div className="space-y-2">
                <Label htmlFor="redirect-to">
                  مسیر مقصد{isRegex ? " (از $1 برای گروه‌های گرفته‌شده استفاده کنید)" : ""}
                </Label>
                <Input
                  id="redirect-to"
                  dir="ltr"
                  value={toPath}
                  onChange={(e) => setToPath(e.target.value)}
                  placeholder={isRegex ? "/new/$1" : "/new-page"}
                />
              </div>
            )}
            <div className="space-y-2">
              <Label>کد وضعیت</Label>
              <Select value={statusCode} onValueChange={setStatusCode}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="301">301 — دائمی (SEO منتقل می‌شود)</SelectItem>
                  <SelectItem value="302">302 — موقت</SelectItem>
                  <SelectItem value="307">307 — موقت با حفظ متد</SelectItem>
                  <SelectItem value="308">308 — دائمی با حفظ متد</SelectItem>
                  <SelectItem value="410">410 — حذف شده (بدون مقصد)</SelectItem>
                  <SelectItem value="451">451 — به دلایل قانونی (بدون مقصد)</SelectItem>
                </SelectContent>
              </Select>
              {targetless && (
                <p className="text-[11px] text-muted-foreground">
                  این کد مقصد ندارد — به بازدیدکننده و گوگل می‌گوید صفحه برنمی‌گردد.
                </p>
              )}
            </div>
            <div className="flex items-center gap-2">
              <input
                id="redirect-regex"
                type="checkbox"
                checked={isRegex}
                onChange={(e) => setIsRegex(e.target.checked)}
                className="h-4 w-4 rounded border-input"
              />
              <Label htmlFor="redirect-regex" className="cursor-pointer">
                الگوی Regex (پیشرفته)
              </Label>
            </div>
            <div className="space-y-2">
              <Label htmlFor="redirect-note">یادداشت (اختیاری)</Label>
              <Input
                id="redirect-note"
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="مثلاً: آدرس قدیمی کمپین"
              />
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
