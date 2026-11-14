"use client";

import { GripVertical, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { PrechatField } from "@/lib/api/chat";

/**
 * Pre-chat form builder — the WordPress plugin's field-row editor, ported.
 *
 * Each row is label / key / type / required. If no row is defined, the widget
 * skips the form and opens the chat directly (plugin parity). The key is what
 * the value is stored under and sent to n8n; an empty key is auto-derived.
 */
const TYPES: { value: string; label: string }[] = [
  { value: "text", label: "متن" },
  { value: "email", label: "ایمیل" },
  { value: "tel", label: "تلفن" },
  { value: "number", label: "عدد" },
  { value: "textarea", label: "متن بلند" },
];

function autoKey(label: string, index: number): string {
  const base = label.trim().replace(/\s+/g, "_").replace(/[^A-Za-z0-9_]/g, "");
  return base || `field_${index + 1}`;
}

export function PrechatFieldsEditor({
  value,
  onChange,
}: {
  value: PrechatField[];
  onChange: (fields: PrechatField[]) => void;
}) {
  const update = (i: number, patch: Partial<PrechatField>) => {
    const next = value.map((f, idx) => (idx === i ? { ...f, ...patch } : f));
    onChange(next);
  };

  return (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground">
        اگر هیچ فیلدی تعریف نشود، گفتگو بدون فرم شروع می‌شود.
      </p>
      {value.map((f, i) => (
        <div key={i} className="flex flex-wrap items-center gap-2 rounded-lg border bg-background p-3">
          <GripVertical className="h-4 w-4 shrink-0 text-muted-foreground" />
          <Input
            value={f.label}
            onChange={(e) => update(i, { label: e.target.value })}
            placeholder="عنوان (مثلاً: موبایل)"
            className="h-9 min-w-[120px] flex-1 text-sm"
          />
          <Input
            value={f.key}
            onChange={(e) => update(i, { key: e.target.value })}
            placeholder="کلید"
            dir="ltr"
            className="h-9 w-28 text-sm"
          />
          <select
            value={f.type || "text"}
            onChange={(e) => update(i, { type: e.target.value })}
            className="h-9 rounded-md border bg-background px-2 text-sm"
          >
            {TYPES.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label}
              </option>
            ))}
          </select>
          <label className="flex items-center gap-1 text-xs">
            <input
              type="checkbox"
              checked={f.required}
              onChange={(e) => update(i, { required: e.target.checked })}
              className="h-4 w-4 rounded accent-primary"
            />
            اجباری
          </label>
          <button
            type="button"
            onClick={() => onChange(value.filter((_, idx) => idx !== i))}
            className="text-destructive hover:opacity-80"
            aria-label="حذف فیلد"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}
      <Button
        type="button"
        size="sm"
        variant="outline"
        className="h-8 text-xs"
        onClick={() =>
          onChange([
            ...value,
            { label: "", key: "", type: "text", required: false },
          ])
        }
      >
        <Plus className="me-1 h-3 w-3" /> افزودن فیلد
      </Button>
      {value.some((f) => !f.key && f.label) && (
        <p className="text-xs text-amber-600">
          برخی فیلدها کلید ندارند؛ هنگام ذخیره به‌صورت خودکار ساخته می‌شوند.
        </p>
      )}
    </div>
  );
}

/** Fill empty keys from labels before saving (server also does this). */
export function normalizePrechatKeys(fields: PrechatField[]): PrechatField[] {
  return fields.map((f, i) => ({ ...f, key: f.key || autoKey(f.label, i) }));
}
