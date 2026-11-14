"use client";

import React, { useEffect, useState } from "react";
import { Plus, Trash2, Loader2, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { apiClient } from "@/lib/api/client";
import { toPersianDigits } from "@/lib/utils";
import type { ApiCategoryCustomField } from "@/lib/api/services";

/**
 * Category-scoped order-field builder — full parity with the per-product
 * add-ons editor (ProductAddonsEditor): same RTL table, same edit mode, and
 * the WooCommerce field-type set on top of the legacy text/number/select
 * trio. No per-option pricing here: category fields are informational buyer
 * inputs, matching the reference plugin's global add-ons.
 */

const FIELD_TYPE_LABELS: Record<string, string> = {
  custom_text: "متن کوتاه",
  custom_textarea: "متن بلند",
  multiple_choice: "انتخاب چندگانه",
  checkbox: "چک‌باکس‌ها",
  custom_price: "قیمت دلخواه مشتری",
  input_multiplier: "تعداد (ضریب)",
  heading: "تیتر بخش",
  text: "متن",
  number: "عدد",
  select: "منوی انتخاب",
};

const NEEDS_OPTIONS = new Set(["select", "multiple_choice", "checkbox"]);
const NEEDS_RANGE = new Set([
  "custom_text",
  "custom_textarea",
  "custom_price",
  "input_multiplier",
]);

function rangeLabel(fieldType: string, which: "min" | "max"): string {
  if (fieldType === "custom_price")
    return which === "min" ? "حداقل مبلغ (تومان)" : "حداکثر مبلغ (تومان)";
  if (fieldType === "input_multiplier")
    return which === "min" ? "حداقل تعداد" : "حداکثر تعداد";
  return which === "min" ? "حداقل کاراکتر" : "حداکثر کاراکتر";
}

/* متن راهنمای درون‌کادر (placeholder) برای حداقل/حداکثر — به ازای هر نوع
   فیلد مثال مرتبط با خودش را نشان می‌دهد، مثل بقیهٔ فیلدهای فرم. */
function rangePlaceholder(fieldType: string, which: "min" | "max"): string {
  if (fieldType === "custom_price")
    return which === "min" ? "مثلاً ۱۰۰۰۰" : "مثلاً ۵۰۰۰۰۰";
  if (fieldType === "input_multiplier")
    return which === "min" ? "مثلاً ۱" : "مثلاً ۱۰";
  return which === "min" ? "مثلاً ۵" : "مثلاً ۲۰۰";
}

export function CategoryFieldsBuilder({ categoryId }: { categoryId: string | null }) {
  const [fields, setFields] = useState<ApiCategoryCustomField[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editingField, setEditingField] = useState<ApiCategoryCustomField | null>(null);
  const [form, setForm] = useState({
    field_key: "",
    label: "",
    description: "",
    // Same default as the product add-ons editor: the rich modern type —
    // so the min/max restrictions show immediately, never the bare legacy
    // "text" shape that hid half the form.
    field_type: "custom_text",
    display: "select",
    is_required: false,
    min_val: "",
    max_val: "",
  });
  const [options, setOptions] = useState<string[]>([""]);

  const load = async () => {
    if (!categoryId) return;
    setLoading(true);
    try {
      const res = await apiClient.get(`/catalog/categories/${categoryId}/custom-fields`);
      setFields(Array.isArray(res.data) ? res.data : []);
    } catch {
      setFields([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (categoryId) void load();
    resetForm();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [categoryId]);

  const resetForm = () => {
    setEditingField(null);
    setForm({
      field_key: "",
      label: "",
      description: "",
      field_type: "custom_text",
      display: "select",
      is_required: false,
      min_val: "",
      max_val: "",
    });
    setOptions([""]);
    setError(null);
  };

  const startEdit = (field: ApiCategoryCustomField) => {
    setEditingField(field);
    setForm({
      field_key: field.field_key,
      label: field.label,
      description: field.description || "",
      field_type: field.field_type,
      display: field.display || "select",
      is_required: field.is_required,
      min_val: field.min_val === null ? "" : String(field.min_val),
      max_val: field.max_val === null ? "" : String(field.max_val),
    });
    setOptions((field.options_json || []).length > 0 ? [...field.options_json!] : [""]);
    setError(null);
  };

  const handleSubmit = async () => {
    setError(null);
    if (!categoryId) {
      setError("ابتدا دسته‌بندی را انتخاب کنید.");
      return;
    }
    if (!editingField) {
      const cleanKey = form.field_key.trim().toLowerCase();
      if (!/^[a-z0-9_]+$/.test(cleanKey)) {
        setError("کلید فیلد فقط حروف انگلیسی، عدد و زیرخط (مثال: player_id)");
        return;
      }
    }
    if (!form.label.trim()) {
      setError("برچسب فیلد الزامی است.");
      return;
    }
    const minVal = form.min_val.trim() === "" ? null : Number(form.min_val);
    const maxVal = form.max_val.trim() === "" ? null : Number(form.max_val);
    const cleanOptions = NEEDS_OPTIONS.has(form.field_type)
      ? options.map((o) => o.trim()).filter(Boolean)
      : null;
    if (NEEDS_OPTIONS.has(form.field_type) && (cleanOptions?.length ?? 0) === 0) {
      setError("برای این نوع فیلد حداقل یک گزینه الزامی است.");
      return;
    }

    const sharedPayload = {
      label: form.label.trim(),
      description: form.description.trim() || null,
      field_type: form.field_type,
      display: form.field_type === "multiple_choice" ? form.display : null,
      options: cleanOptions,
      is_required: form.is_required && form.field_type !== "heading",
      min_val: minVal,
      max_val: maxVal,
    };

    setSaving(true);
    try {
      if (editingField) {
        await apiClient.put(`/catalog/custom-fields/${editingField.id}`, sharedPayload);
      } else {
        await apiClient.post(`/catalog/categories/${categoryId}/custom-fields`, {
          field_key: form.field_key.trim().toLowerCase(),
          ...sharedPayload,
          position: fields.length,
        });
      }
      resetForm();
      await load();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        (editingField ? "ذخیره تغییرات ناموفق بود." : "ایجاد فیلد ناموفق بود.");
      setError(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (fieldId: string) => {
    try {
      await apiClient.delete(`/catalog/custom-fields/${fieldId}`);
      if (editingField?.id === fieldId) resetForm();
      await load();
    } catch {
      // ignore
    }
  };

  if (!categoryId) return null;

  return (
    /* لیست (راست) + فرم افزودن/ویرایش (چپ) کنار هم از عرض ۱۳۸۰px؛ زیر آن
       روی هم با فاصلهٔ عادی. لیست ۵۵٪ و فرم بقیهٔ عرض را می‌گیرد. */
    <div className="flex flex-col items-stretch gap-3 min-[1380px]:flex-row min-[1380px]:items-start min-[1380px]:gap-4">
      {loading ? (
        <div className="flex justify-center py-6">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : fields.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
          برای این دسته فیلدی تعریف نشده است.
        </p>
      ) : (
        /* ردیف‌های انعطاف‌پذیر به‌جای جدول ۴ستونه: در کابل ۵۰-۵۰ این کارت
           ~۴۹۰px است و جدول چهارستونه با برچسب کامل + دو دکمهٔ متنی جا
           نمی‌شد (نتیجه: سه‌نقطه، هم‌پوشانی کلید روی نوع، دکمه‌های دو سطر).
           هر ردیف سه گروهِ nowrap دارد — نام+اجباری، نوع+کلید، ویرایش+حذف —
           که در عرض کافی همه روی یک سطر می‌نشینند و در عرض کم به‌صورت
           گروهی می‌شکنند؛ هیچ متنی بریده یا روی هم نمی‌افتد و ویرایش/حذف
           همیشه یک سطر هستند. */
        /* سقف عرض 768px (me-auto → در RTL چسبیده به راست): ردیف‌های
           تمام‌عرضِ ۱۳۴۰px گروه‌ها را با شکاف‌های بزرگ پراکنده می‌کرد؛
           با این سقف فاصلهٔ گروه‌ها طبیعی می‌شود و ستون‌ها همچنان زیر هم
           می‌مانند. در موبایل w-full است. */
        <div className="me-auto w-full overflow-hidden rounded-lg border border-border divide-y divide-border sm:max-w-3xl min-[1380px]:w-[55%] min-[1380px]:max-w-none min-[1380px]:shrink-0 min-[1380px]:me-0">
          {fields.map((f) => (
            /* گرید سه‌ستونه با ستون میانیِ عرض ثابت (۱۶۰px): ستون «نوع+کلید»
               در همهٔ ردیف‌ها دقیقاً زیر هم می‌نشیند (قبلاً justify-between
               جای این گروه را تابع عرضِ نامِ هر ردیف می‌کرد و سطرها نامرتب
               بودند). زیر sm هر گروه یک سطر می‌شود. */
            <div
              key={f.id}
              className="grid grid-cols-1 items-center gap-y-2 px-3 py-2.5 transition-colors hover:bg-muted/30 sm:grid-cols-[minmax(0,1fr)_185px_minmax(0,1fr)] sm:gap-x-3 sm:gap-y-0"
            >
              <div className="flex items-center gap-1.5 whitespace-nowrap">
                <span className="text-xs font-semibold text-foreground">
                  {f.label}
                </span>
                {f.is_required && (
                  <Badge variant="secondary" className="h-4 shrink-0 px-1 text-[9px]">
                    اجباری
                  </Badge>
                )}
              </div>
              <div className="flex items-center justify-start gap-2 whitespace-nowrap">
                {/* عرض ثابت نشان نوع + shrink-0: بدون این، فلکس هنگام سرریز
                    شدنِ (نشان+کلید) از ستون ۱۸۵px، نشان را می‌فشرد و عرض‌ها
                    در ردیف‌ها فرق می‌کرد و ستون به‌هم می‌ریخت. */}
                <Badge
                  variant="outline"
                  className="inline-flex w-24 shrink-0 items-center justify-center px-1 font-normal text-[10px]"
                >
                  {FIELD_TYPE_LABELS[f.field_type] ?? f.field_type}
                </Badge>
                <span
                  className="shrink-0 font-mono text-[11px] text-muted-foreground"
                  dir="ltr"
                >
                  {f.field_key}
                </span>
              </div>
              <div className="flex items-center gap-1 whitespace-nowrap sm:justify-self-end">
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 gap-1 px-2 text-xs text-muted-foreground hover:bg-primary/10 hover:text-primary"
                  onClick={() => startEdit(f)}
                >
                  <Pencil className="h-3.5 w-3.5" />
                  ویرایش
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 gap-1 px-2 text-xs text-destructive hover:bg-destructive/10"
                  onClick={() => void handleDelete(f.id)}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  حذف
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create / Edit form */}
      <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-3 min-[1380px]:min-w-0 min-[1380px]:flex-1">
        <div className="flex items-center justify-between">
          <p className="text-xs font-bold">
            {editingField ? `ویرایش فیلد: ${editingField.label}` : "افزودن فیلد جدید"}
          </p>
          {editingField && (
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 text-[11px] text-muted-foreground"
              onClick={resetForm}
            >
              لغو ویرایش
            </Button>
          )}
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-[11px]">کلید فیلد (انگلیسی)</Label>
            <Input
              value={form.field_key}
              onChange={(e) => setForm({ ...form, field_key: e.target.value })}
              placeholder="player_id"
              className="h-8 text-xs"
              dir="ltr"
              disabled={Boolean(editingField)}
            />
            {editingField && (
              <p className="text-[10px] text-muted-foreground">
                کلید پس از ساخت قابل تغییر نیست (پاس‌های ذخیره‌شده به آن وصل‌اند).
              </p>
            )}
          </div>
          <div className="space-y-1">
            <Label className="text-[11px]">برچسب (فارسی)</Label>
            <Input
              value={form.label}
              onChange={(e) => setForm({ ...form, label: e.target.value })}
              placeholder="شناسه بازیکن"
              className="h-8 text-xs"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-[11px]">نوع فیلد</Label>
            <Select
              value={form.field_type}
              onValueChange={(v) => setForm({ ...form, field_type: v })}
            >
              <SelectTrigger className="h-8 w-full text-xs">
                <SelectValue placeholder="نوع فیلد…" />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(FIELD_TYPE_LABELS).map(([k, v]) => (
                  <SelectItem key={k} value={k} className="text-xs">
                    {v}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          {/* Compact: required toggle always beside the type — no extra
              full-width row for multiple_choice. */}
          <label className="flex items-center gap-2 self-end pb-1 text-[11px] text-muted-foreground">
            <input
              type="checkbox"
              checked={form.is_required}
              onChange={(e) => setForm({ ...form, is_required: e.target.checked })}
              className="accent-primary"
            />
            پاسخ به این فیلد الزامی است
          </label>
        </div>

        {/* Compact: description + min/max share ONE row when the type has
            range limits — three side-by-side fields instead of stacked. */}
        {NEEDS_RANGE.has(form.field_type) ? (
          <div className="grid grid-cols-3 gap-2">
            <div className="space-y-1">
              <Label className="text-[11px]">توضیح (اختیاری)</Label>
              <Input
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="یک خط توضیح زیر برچسب"
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px]">{rangeLabel(form.field_type, "min")}</Label>
              <Input
                value={form.min_val}
                onChange={(e) => setForm({ ...form, min_val: e.target.value })}
                placeholder={rangePlaceholder(form.field_type, "min")}
                aria-label={rangeLabel(form.field_type, "min")}
                className="h-8 text-xs"
                inputMode="numeric"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px]">{rangeLabel(form.field_type, "max")}</Label>
              <Input
                value={form.max_val}
                onChange={(e) => setForm({ ...form, max_val: e.target.value })}
                placeholder={rangePlaceholder(form.field_type, "max")}
                aria-label={rangeLabel(form.field_type, "max")}
                className="h-8 text-xs"
                inputMode="numeric"
                dir="ltr"
              />
            </div>
          </div>
        ) : (
          <div className="space-y-1">
            <Label className="text-[11px]">توضیح (اختیاری)</Label>
            <Input
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="یک خط توضیح زیر برچسب"
              className="h-8 text-xs"
            />
          </div>
        )}

        {NEEDS_OPTIONS.has(form.field_type) && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label className="text-[11px]">گزینه‌ها</Label>
              {form.field_type === "multiple_choice" && (
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-muted-foreground">نمایش:</span>
                  <Select
                    value={form.display}
                    onValueChange={(v) => setForm({ ...form, display: v })}
                  >
                    <SelectTrigger className="h-7 w-[110px] text-[11px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="select" className="text-[11px]">منوی کشویی</SelectItem>
                      <SelectItem value="radio" className="text-[11px]">دکمه رادیویی</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}
            </div>
            {options.map((opt, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <Input
                  value={opt}
                  onChange={(e) =>
                    setOptions((prev) =>
                      prev.map((o, j) => (j === i ? e.target.value : o)),
                    )
                  }
                  placeholder={`گزینه ${toPersianDigits(i + 1)}`}
                  className="h-8 flex-1 text-xs"
                />
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-8 w-8 p-0 text-destructive"
                  onClick={() =>
                    setOptions((prev) => (prev.length > 1 ? prev.filter((_, j) => j !== i) : prev))
                  }
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              size="sm"
              variant="outline"
              className="h-7 gap-1 text-xs"
              onClick={() => setOptions((prev) => [...prev, ""])}
            >
              <Plus className="h-3 w-3" />
              گزینه بعدی
            </Button>
          </div>
        )}


        {error && (
          <p className="text-[11px] font-medium text-destructive" role="alert">
            {error}
          </p>
        )}

        <Button
          type="button"
          size="sm"
          disabled={saving}
          onClick={() => void handleSubmit()}
          /* w-full فقط در موبایل؛ در دسکتاپ دکمه به اندازهٔ متنش می‌آید
             و تمام‌عرضِ کارت را نمی‌گیرد. */
          className="w-full gap-2 rounded-xl sm:w-auto"
        >
          {saving ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : editingField ? (
            <Pencil className="h-4 w-4" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          {editingField ? "ذخیره تغییرات فیلد" : "افزودن فیلد به دسته‌بندی"}
        </Button>
      </div>
    </div>
  );
}
