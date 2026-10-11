"use client";

/**
 * Schema builder — Rank Math's Schema tab, inside the post editor's SEO panel.
 *
 * The operator picks a type from the catalog (fetched from the API, not
 * hardcoded here — a type the backend cannot build is never offered), fills
 * the type's fields, and sees the assembled JSON-LD live. Applying stores it
 * in `seo_metadata.schema_markup`, which the storefront now renders (it used
 * to save without rendering).
 *
 * The server assembles and validates; this component never builds JSON-LD
 * itself. A client-side approximation would drift from what the storefront
 * emits, and the preview would start lying — the exact failure mode the
 * live-preview pattern exists to prevent.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Code2, Loader2, Trash2, Wand2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import {
  applySchema,
  buildSchema,
  fetchSchemaTypes,
  type SchemaTypeEntry,
} from "@/lib/api/seo";

export function SchemaBuilder({
  resourceType,
  resourceId,
}: {
  resourceType: string;
  resourceId: string | null;
}) {
  const { toast } = useToast();
  const [types, setTypes] = useState<SchemaTypeEntry[]>([]);
  const [selectedType, setSelectedType] = useState<string>("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [preview, setPreview] = useState<Record<string, unknown> | null>(null);
  const [problems, setProblems] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [applying, setApplying] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const catalog = await fetchSchemaTypes();
        setTypes(catalog);
      } catch {
        toast({ title: "دریافت فهرست اسکیما ناموفق بود", variant: "destructive" });
      } finally {
        setLoading(false);
      }
    })();
  }, [toast]);

  const entry = useMemo(
    () => types.find((t) => t.type === selectedType) ?? null,
    [types, selectedType],
  );

  // Live preview, debounced — server-side assembly so the preview is exactly
  // what apply would store and the storefront would render.
  const refreshPreview = useCallback(
    async (schemaType: string, fields: Record<string, string>) => {
      if (!schemaType) {
        setPreview(null);
        setProblems([]);
        return;
      }
      try {
        const result = await buildSchema({
          schema_type: schemaType,
          fields,
          resource_type: resourceId ? resourceType : undefined,
          resource_id: resourceId ?? undefined,
        });
        setPreview(result.node);
        setProblems(result.problems);
      } catch {
        // A failed preview leaves the last one; applying still validates.
      }
    },
    [resourceType, resourceId],
  );

  useEffect(() => {
    if (!selectedType) return;
    const t = setTimeout(() => void refreshPreview(selectedType, values), 500);
    return () => clearTimeout(t);
  }, [selectedType, values, refreshPreview]);

  const apply = async () => {
    if (!resourceId || !selectedType) return;
    setApplying(true);
    try {
      const result = await applySchema({
        schema_type: selectedType,
        fields: values,
        resource_type: resourceType,
        resource_id: resourceId,
      });
      setPreview(result.node);
      setProblems([]);
      toast({ title: "اسکیما ذخیره شد و در صفحه اعمال می‌شود" });
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        "ذخیره اسکیما ناموفق بود";
      toast({ title: String(detail), variant: "destructive" });
    } finally {
      setApplying(false);
    }
  };

  const clear = async () => {
    if (!resourceId) return;
    setApplying(true);
    try {
      // An empty node clears the override; the storefront falls back to its
      // built-in schema for this resource type.
      await applySchema({
        schema_type: selectedType || "Article",
        fields: {},
        resource_type: resourceType,
        resource_id: resourceId,
      });
      toast({
        title: "برای حذف کامل، فیلدها را پاک و ذخیره کنید",
        variant: "destructive",
      });
    } catch {
      toast({ title: "عملیات ناموفق بود", variant: "destructive" });
    } finally {
      setApplying(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال خواندن فهرست اسکیما...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {!resourceId && (
        <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
          برای ساخت اسکیما، ابتدا نوشته را ذخیره کنید.
        </p>
      )}

      <div className="grid gap-2">
        <Label htmlFor="schema-type">نوع اسکیما</Label>
        <select
          id="schema-type"
          value={selectedType}
          onChange={(e) => {
            setSelectedType(e.target.value);
            setValues({});
          }}
          className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
        >
          <option value="">— انتخاب نوع —</option>
          {types.map((t) => (
            <option key={t.type} value={t.type}>
              {t.label}
            </option>
          ))}
        </select>
        {entry && (
          <p className="text-[11px] text-muted-foreground">{entry.description}</p>
        )}
      </div>

      {entry && (
        <>
          {entry.fields.map((field) => (
            <div key={field.key} className="grid gap-2">
              <Label htmlFor={`schema-${field.key}`}>
                {field.label}
                {field.required && <span className="text-red-500 ms-1">*</span>}
              </Label>
              {field.kind === "textarea" ? (
                <Textarea
                  id={`schema-${field.key}`}
                  value={values[field.key] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  rows={4}
                  placeholder={field.placeholder}
                />
              ) : field.kind === "select" && field.options ? (
                <select
                  id={`schema-${field.key}`}
                  value={values[field.key] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                >
                  <option value="">—</option>
                  {field.options.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              ) : (
                <Input
                  id={`schema-${field.key}`}
                  type={field.kind === "number" ? "number" : field.kind === "date" ? "date" : "text"}
                  dir={field.kind === "url" || field.kind === "date" ? "ltr" : "auto"}
                  value={values[field.key] ?? ""}
                  onChange={(e) =>
                    setValues((prev) => ({ ...prev, [field.key]: e.target.value }))
                  }
                  placeholder={field.placeholder}
                />
              )}
            </div>
          ))}

          {problems.length > 0 && (
            <ul className="space-y-1 rounded-lg bg-red-500/10 p-3 text-[11px] text-red-700">
              {problems.map((p, i) => (
                <li key={i}>{p}</li>
              ))}
            </ul>
          )}

          {preview && (
            <div className="rounded-lg border border-border bg-muted/30 p-3">
              <div className="mb-1 flex items-center gap-1.5 text-[11px] text-muted-foreground">
                <Code2 className="h-3 w-3" />
                پیش‌نمایش JSON-LD (همان چیزی که در صفحه منتشر می‌شود)
              </div>
              <pre
                dir="ltr"
                className="max-h-48 overflow-auto whitespace-pre-wrap break-all text-[10px] leading-relaxed"
              >
                {JSON.stringify(preview, null, 2)}
              </pre>
            </div>
          )}

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void apply()}
              disabled={applying || !resourceId || problems.length > 0}
              className="flex items-center gap-1.5 rounded-md border border-input px-3 py-1.5 text-xs font-medium disabled:opacity-60"
            >
              {applying ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Wand2 className="h-3.5 w-3.5" />
              )}
              ذخیره اسکیما
            </button>
            <button
              type="button"
              onClick={() => void clear()}
              disabled={applying || !resourceId}
              className="flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-60"
            >
              <Trash2 className="h-3.5 w-3.5" />
              پاک کردن فرم
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export default SchemaBuilder;
