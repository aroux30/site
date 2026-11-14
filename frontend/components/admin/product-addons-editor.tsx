"use client";

import React, { useEffect, useState } from "react";
import { Plus, Trash2, Loader2, Pencil } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
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
import type { ApiProductAddonField } from "@/lib/api/services";

/**
 * Admin editor for per-product add-on fields — WooCommerce Product Add-ons
 * parity. Field types mirror the reference plugin's panel (file_upload
 * excluded: no public customer-upload endpoint in this stack yet). Prices
 * entered here are TOMAN; the API converts to Rial on storage.
 */

const FIELD_TYPE_LABELS: Record<string, string> = {
  multiple_choice: "انتخاب چندگانه",
  checkbox: "چک‌باکس‌ها",
  custom_text: "متن کوتاه",
  custom_textarea: "متن بلند",
  custom_price: "قیمت دلخواه مشتری",
  input_multiplier: "تعداد (ضریب)",
  heading: "تیتر بخش",
};

type OptionDraft = { label: string; price: string; price_type: string };

const emptyForm = {
  field_key: "",
  label: "",
  description: "",
  field_type: "custom_text",
  display: "select",
  is_required: false,
  min_val: "",
  max_val: "",
  price: "",
  price_type: "quantity_based",
};

export function ProductAddonsEditor({
  productId,
  productName,
  open,
  onOpenChange,
}: {
  productId: string | null;
  productName: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [fields, setFields] = useState<ApiProductAddonField[]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({ ...emptyForm });
  const [options, setOptions] = useState<OptionDraft[]>([
    { label: "", price: "", price_type: "flat_fee" },
  ]);
  // Edit mode: the form above becomes an editor for this field (key locked).
  const [editingField, setEditingField] = useState<ApiProductAddonField | null>(null);

  const needsOptions = form.field_type === "multiple_choice" || form.field_type === "checkbox";
  const needsRange = ["custom_text", "custom_textarea", "custom_price", "input_multiplier"].includes(
    form.field_type,
  );

  const load = async () => {
    if (!productId) return;
    setLoading(true);
    try {
      const res = await apiClient.get(`/catalog/products/${productId}/addon-fields`);
      setFields(Array.isArray(res.data) ? res.data : []);
    } catch {
      setFields([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open && productId) void load();
    if (open) {
      setForm({ ...emptyForm });
      setOptions([{ label: "", price: "", price_type: "flat_fee" }]);
      setError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, productId]);

  const startEdit = (field: ApiProductAddonField) => {
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
      price: field.price === null ? "" : String(field.price),
      price_type: field.price_type || "quantity_based",
    });
    setOptions(
      (field.options_json || []).length > 0
        ? field.options_json!.map((o) => ({
            label: o.label,
            price: o.price === null || o.price === undefined ? "" : String(o.price),
            price_type: o.price_type || "flat_fee",
          }))
        : [{ label: "", price: "", price_type: "flat_fee" }],
    );
    setError(null);
  };

  const cancelEdit = () => {
    setEditingField(null);
    setForm({ ...emptyForm });
    setOptions([{ label: "", price: "", price_type: "flat_fee" }]);
    setError(null);
  };

  const handleSubmit = async () => {
    setError(null);
    if (!productId) return;
    const minVal = form.min_val.trim() === "" ? null : Number(form.min_val);
    const maxVal = form.max_val.trim() === "" ? null : Number(form.max_val);
    const price = form.price.trim() === "" ? null : Number(form.price);

    if (!editingField) {
      const cleanKey = form.field_key.trim().toLowerCase();
      if (!/^[a-z0-9_]+$/.test(cleanKey)) {
        setError("کلید فیلد فقط حروف انگلیسی، عدد و زیرخط (مثال: gift_wrap)");
        return;
      }
    }
    if (!form.label.trim()) {
      setError("برچسب فیلد الزامی است.");
      return;
    }

    if (needsOptions && options.filter((o) => o.label.trim()).length === 0) {
      setError("برای این نوع فیلد حداقل یک گزینه (برچسب) الزامی است.");
      return;
    }

    const sharedPayload = {
      label: form.label.trim(),
      description: form.description.trim() || null,
      field_type: form.field_type,
      display: form.field_type === "multiple_choice" ? form.display : null,
      options: needsOptions
        ? options
            .filter((o) => o.label.trim())
            .map((o) => ({
              label: o.label.trim(),
              price: o.price.trim() === "" ? null : Number(o.price),
              price_type: o.price_type,
            }))
        : null,
      is_required: form.is_required && form.field_type !== "heading",
      min_val: minVal,
      max_val: maxVal,
      price: form.field_type === "input_multiplier" ? price : null,
      price_type: form.field_type === "input_multiplier" ? form.price_type : null,
    };

    setSaving(true);
    try {
      if (editingField) {
        await apiClient.put(`/catalog/addon-fields/${editingField.id}`, sharedPayload);
      } else {
        await apiClient.post(`/catalog/products/${productId}/addon-fields`, {
          field_key: form.field_key.trim().toLowerCase(),
          ...sharedPayload,
          position: fields.length,
        });
      }
      cancelEdit();
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
      await apiClient.delete(`/catalog/addon-fields/${fieldId}`);
      await load();
    } catch {
      // ignore
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle>فیلدهای سفارشی محصول (Product Add-ons)</DialogTitle>
          <DialogDescription>
            برای «{productName}» فیلدهای ورودی مشتری را تعریف کنید؛ روی صفحه‌ی کالا نمایش،
            هنگام ثبت سفارش اعتبارسنجی و همراه فاکتور ذخیره می‌شوند.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          {loading ? (
            <div className="flex justify-center py-6">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : fields.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              هنوز فیلدی برای این محصول تعریف نشده است.
            </p>
          ) : (
            /* Table layout — same ordering discipline as the orders table:
               RTL columns right→left = فیلد، نوع، کلید، عملیات. No flex-wrap
               floaters: every cell owns a fixed column so the Latin field key
               can never drift into the middle of a Persian row. */
            <div className="overflow-hidden rounded-lg border border-border">
              <table className="w-full table-fixed text-center text-sm" dir="rtl">
                <thead className="bg-muted/50">
                  <tr>
                    {/* textAlign inline: the global [dir=rtl] .text-right rule
                        flips utility classes to left — inline wins it back so
                        headers sit exactly over their right-aligned cells
                        (orders/categories table parity). */}
                    <th className="px-4 py-3 font-semibold">فیلد</th>
                    <th className="w-[22%] px-4 py-3 font-semibold">نوع</th>
                    <th className="w-[18%] px-4 py-3 font-semibold">کلید</th>
                    <th className="w-[20%] px-4 py-3 px-3 py-2 text-center font-semibold" style={{ textAlign: "center" }}>عملیات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {fields.map((f) => (
                    <tr key={f.id} className="transition-colors hover:bg-muted/30">
                      <td className="px-4 py-3">
                        {/* One guaranteed line: nowrap row + truncated label
                            (title keeps the full text on hover). */}
                        <div className="flex w-full min-w-0 items-center justify-center gap-1.5 whitespace-nowrap">
                          <span
                            className="truncate text-sm font-semibold text-foreground"
                            title={f.label}
                          >
                            {f.label}
                          </span>
                          {f.is_required && (
                            <Badge
                              variant="secondary"
                              className="h-4 shrink-0 px-1 text-[10px]"
                            >
                              اجباری
                            </Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="outline" className="whitespace-nowrap font-normal">
                          {FIELD_TYPE_LABELS[f.field_type] ?? f.field_type}
                        </Badge>
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-center font-mono text-muted-foreground" dir="ltr">
                        {f.field_key}
                      </td>
                      <td className="px-4 py-3 text-center">
                        <div className="flex items-center justify-center gap-0.5 whitespace-nowrap">
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 gap-1 text-muted-foreground hover:bg-primary/10 hover:text-primary"
                            onClick={() => startEdit(f)}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                            ویرایش
                          </Button>
                          <Button
                            size="sm"
                            variant="ghost"
                            className="h-7 gap-1 text-destructive hover:bg-destructive/10"
                            onClick={() => void handleDelete(f.id)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                            حذف
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Create form */}
          <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-3">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold">
                {editingField
                  ? `ویرایش فیلد: ${editingField.label}`
                  : "افزودن فیلد جدید"}
              </p>
              {editingField && (
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  className="h-7 text-[11px] text-muted-foreground"
                  onClick={cancelEdit}
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
                  placeholder="gift_wrap"
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
                  placeholder="بسته‌بندی کادویی"
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
                    <SelectValue placeholder="نوع فیلد را انتخاب کنید…" />
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
              {/* Stable two-slot row: right slot is always the type, left slot
                  is the display mode (multiple_choice) or the required toggle —
                  no conditional jump-around. */}
              {/* Compact: required toggle always beside the type; the display
                  selector moved into the options header below. */}
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
            {form.field_type === "multiple_choice" && (
              <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
                <input
                  type="checkbox"
                  checked={form.is_required}
                  onChange={(e) => setForm({ ...form, is_required: e.target.checked })}
                  className="accent-primary"
                />
                پاسخ به این فیلد الزامی است
              </label>
            )}

            {needsOptions && (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-[11px]">گزینه‌ها (برچسب، قیمت تومانی اختیاری، نوع قیمت)</Label>
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
                      value={opt.label}
                      onChange={(e) =>
                        setOptions((prev) =>
                          prev.map((o, j) => (j === i ? { ...o, label: e.target.value } : o)),
                        )
                      }
                      placeholder="برچسب"
                      className="h-8 flex-1 text-xs"
                    />
                    <Input
                      value={opt.price}
                      onChange={(e) =>
                        setOptions((prev) =>
                          prev.map((o, j) => (j === i ? { ...o, price: e.target.value } : o)),
                        )
                      }
                      placeholder="قیمت (تومان)"
                      className="h-8 w-28 text-xs"
                      dir="ltr"
                      inputMode="numeric"
                    />
                    <Select
                      value={opt.price_type}
                      onValueChange={(v) =>
                        setOptions((prev) =>
                          prev.map((o, j) => (j === i ? { ...o, price_type: v } : o)),
                        )
                      }
                    >
                      <SelectTrigger className="h-8 w-[110px] shrink-0 text-[11px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="flat_fee" className="text-[11px]">مبلغ ثابت</SelectItem>
                        <SelectItem value="quantity_based" className="text-[11px]">به ازای تعداد</SelectItem>
                        <SelectItem value="percentage_based" className="text-[11px]">درصدی</SelectItem>
                      </SelectContent>
                    </Select>
                    <Button
                      type="button"
                      size="sm"
                      variant="ghost"
                      className="h-8 w-8 p-0 text-destructive"
                      onClick={() =>
                        setOptions((prev) =>
                          prev.length > 1 ? prev.filter((_, j) => j !== i) : prev,
                        )
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
                  onClick={() =>
                    setOptions((prev) => [...prev, { label: "", price: "", price_type: "flat_fee" }])
                  }
                >
                  <Plus className="h-3 w-3" />
                  گزینه بعدی
                </Button>
              </div>
            )}

            {/* Compact: description + min/max share ONE three-column row. */}
            {needsRange && (
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
                  <Label className="text-[11px]">
                    {form.field_type === "custom_price"
                      ? "حداقل مبلغ (تومان)"
                      : form.field_type === "input_multiplier"
                      ? "حداقل تعداد"
                      : "حداقل کاراکتر"}
                  </Label>
                  <Input
                    value={form.min_val}
                    onChange={(e) => setForm({ ...form, min_val: e.target.value })}
                    className="h-8 text-xs"
                    inputMode="numeric"
                    dir="ltr"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[11px]">
                    {form.field_type === "custom_price"
                      ? "حداکثر مبلغ (تومان)"
                      : form.field_type === "input_multiplier"
                      ? "حداکثر تعداد"
                      : "حداکثر کاراکتر"}
                  </Label>
                  <Input
                    value={form.max_val}
                    onChange={(e) => setForm({ ...form, max_val: e.target.value })}
                    className="h-8 text-xs"
                    inputMode="numeric"
                    dir="ltr"
                  />
                </div>
              </div>
            )}

            {form.field_type === "input_multiplier" && (
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-[11px]">قیمت هر عدد (تومان)</Label>
                  <Input
                    value={form.price}
                    onChange={(e) => setForm({ ...form, price: e.target.value })}
                    className="h-8 text-xs"
                    inputMode="numeric"
                    dir="ltr"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[11px]">نوع محاسبه</Label>
                  <Select
                    value={form.price_type}
                    onValueChange={(v) => setForm({ ...form, price_type: v })}
                  >
                    <SelectTrigger className="h-8 w-full text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="quantity_based" className="text-xs">به ازای تعداد</SelectItem>
                      <SelectItem value="flat_fee" className="text-xs">مبلغ ثابت</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
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
              className="w-full gap-2 rounded-xl"
            >
              {saving ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : editingField ? (
                <Pencil className="h-4 w-4" />
              ) : (
                <Plus className="h-4 w-4" />
              )}
              {editingField ? "ذخیره تغییرات فیلد" : "افزودن فیلد به محصول"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
