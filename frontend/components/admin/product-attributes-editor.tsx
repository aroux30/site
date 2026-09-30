"use client";

import { useCallback, useEffect, useState } from "react";
import { Loader2, Plus, Tags, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits } from "@/lib/utils";
import {
  createAttribute,
  createAttributeValue,
  createTag,
  fetchAttributes,
  fetchTags,
  type ApiAttribute,
  type ApiAttributeType,
  type ApiTag,
} from "@/lib/api/catalog-attributes";

/** One row of the specification sheet: an attribute and the value chosen for it. */
export interface ProductAttributeDraft {
  /** ``new:<name>`` for an attribute created inline in this form. */
  attributeId: string;
  value: string;
  valueLabel: string;
}

interface AttributesEditorProps {
  value: ProductAttributeDraft[];
  onChange: (next: ProductAttributeDraft[]) => void;
  tagIds: string[];
  onTagIdsChange: (next: string[]) => void;
}

const ATTRIBUTE_TYPE_LABELS: Record<ApiAttributeType, string> = {
  text: "متنی",
  number: "عددی",
  color: "رنگ",
  size: "سایز",
};

/** Attribute ids minted locally for values the operator typed in the form. */
const INLINE_PREFIX = "new:";

/**
 * The specification sheet editor.
 *
 * Both tables behind the storefront's "مشخصات فنی کالا" tab and its faceted
 * filters were already built and had no way to be written: the product form
 * sent neither `attributes` nor `tag_ids`, so the spec tab always showed its
 * empty state.  An operator can pick from the existing catalogue or define a new
 * attribute/value/tag in place, without leaving the form.
 */
export function AttributesEditor({
  value,
  onChange,
  tagIds,
  onTagIdsChange,
}: AttributesEditorProps) {
  const { toast } = useToast();
  const [attributes, setAttributes] = useState<ApiAttribute[]>([]);
  const [tags, setTags] = useState<ApiTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState(false);

  // Inline creation inputs. Only one is armed at a time so the form stays
  // readable, and both clear themselves once the object is created.
  const [newAttrOpen, setNewAttrOpen] = useState(false);
  const [newAttrName, setNewAttrName] = useState("");
  const [newAttrValue, setNewAttrValue] = useState("");
  const [newValueFor, setNewValueFor] = useState<string | null>(null);
  const [newValueText, setNewValueText] = useState("");
  const [newTagName, setNewTagName] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(false);
    try {
      const [attrs, tagList] = await Promise.all([fetchAttributes(), fetchTags()]);
      setAttributes(attrs);
      setTags(tagList);
    } catch {
      // A failed load must not read as "there are no attributes" — that
      // would push an operator to create a duplicate definition.
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  /** Resolve an id that may be an inline placeholder back to a real attribute. */
  const attributeById = useCallback(
    (id: string) => attributes.find((a) => a.id === id),
    [attributes],
  );

  const addRow = (attributeId: string, valueId: string, label: string) => {
    if (value.some((r) => r.attributeId === attributeId)) {
      toast({
        title: "این مشخصه ثبت شده است",
        description: "برای هر مشخصه فقط یک مقدار می‌توانید انتخاب کنید.",
        variant: "default",
      });
      return;
    }
    onChange([...value, { attributeId, value: valueId, valueLabel: label }]);
  };

  const removeRow = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleCreateAttribute = async () => {
    const name = newAttrName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const created = await createAttribute({
        name,
        type: "text",
        values: newAttrValue.trim() ? [{ value: newAttrValue.trim() }] : [],
      });
      await load();
      // A value typed alongside the definition is chosen straight away, so the
      // operator does not have to re-pick what they just typed.
      if (created.values[0]) {
        addRow(created.id, created.values[0].id, created.values[0].value);
      } else {
        onChange([...value, { attributeId: created.id, value: "", valueLabel: "" }]);
      }
      setNewAttrName("");
      setNewAttrValue("");
      setNewAttrOpen(false);
      toast({ title: "مشخصه ایجاد شد", description: `«${name}» به کاتالوگ مشخصات اضافه شد.` });
    } catch (err: any) {
      toast({
        title: "ایجاد مشخصه ناموفق بود",
        description: err?.message || "عملیات با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleCreateValue = async (attributeId: string) => {
    const text = newValueText.trim();
    if (!text) return;
    setBusy(true);
    try {
      await createAttributeValue(attributeId, { value: text });
      await load();
      setNewValueText("");
      setNewValueFor(null);
      toast({ title: "مقدار جدید ثبت شد", description: `«${text}» افزوده شد.` });
    } catch (err: any) {
      toast({
        title: "افزودن مقدار ناموفق بود",
        description: err?.message || "عملیات با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const handleCreateTag = async () => {
    const name = newTagName.trim();
    if (!name) return;
    setBusy(true);
    try {
      const created = await createTag({ name });
      setTags((prev) => [...prev, created]);
      onTagIdsChange([...tagIds, created.id]);
      setNewTagName("");
      toast({ title: "برچسب ایجاد شد", description: `«${name}» ساخته و انتخاب شد.` });
    } catch (err: any) {
      toast({
        title: "ایجاد برچسب ناموفق بود",
        description: err?.message || "عملیات با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const toggleTag = (id: string) => {
    onTagIdsChange(
      tagIds.includes(id) ? tagIds.filter((t) => t !== id) : [...tagIds, id],
    );
  };

  return (
    <div className="space-y-4 border-t border-border pt-4">
      {/* ── Specification sheet ─────────────────────────────────────── */}
      <div className="space-y-2">
        <Label>جدول مشخصات فنی</Label>
        <p className="text-xs text-muted-foreground">
          همین مقادیر در تب «مشخصات فنی کالا» صفحه محصول و در فیلترهای فروشگاه
          نمایش داده می‌شوند.
        </p>

        {loadError ? (
          <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
            <p className="text-xs text-destructive">
              دریافت فهرست مشخصات با خطا مواجه شد — ممکن است این بخش خالی نباشد.
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={load}
            >
              تلاش دوباره
            </Button>
          </div>
        ) : loading ? (
          <div className="flex items-center gap-2 rounded-lg border border-border p-3 text-xs text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            در حال بارگذاری مشخصات...
          </div>
        ) : (
          <>
            {/* Currently set */}
            {value.length > 0 ? (
              <div className="space-y-1 rounded-lg border border-border p-2">
                {value.map((row, i) => {
                  const attr = attributeById(row.attributeId);
                  const label = attr?.name ?? (row.attributeId.startsWith(INLINE_PREFIX) ? row.attributeId.slice(INLINE_PREFIX.length) : row.attributeId);
                  return (
                    <div
                      key={`${row.attributeId}-${i}`}
                      className="flex items-center gap-2 rounded px-2 py-1.5 text-sm"
                    >
                      <span className="flex-1 truncate">
                        <span className="font-semibold text-foreground">{label}</span>
                        <span className="text-muted-foreground">: </span>
                        <span className="text-muted-foreground">
                          {row.valueLabel || "—"}
                        </span>
                      </span>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 p-0"
                        onClick={() => removeRow(i)}
                        aria-label={`حذف ${label}`}
                      >
                        <X className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="rounded-lg border border-dashed border-border p-3 text-center text-xs text-muted-foreground">
                هنوز مشخصه‌ای انتخاب نشده است.
              </p>
            )}

            {/* Add a row from the catalogue */}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
              <Select
                onValueChange={(id) => {
                  const attr = attributeById(id);
                  const first = attr?.values[0];
                  if (attr && first) addRow(id, first.id, first.value);
                }}
                disabled={attributes.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="افزودن مشخصه از فهرست" />
                </SelectTrigger>
                <SelectContent>
                  {attributes.map((attr) => (
                    <SelectItem key={attr.id} value={attr.id} disabled={value.some((r) => r.attributeId === attr.id)}>
                      {attr.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                onValueChange={(id) => {
                  const sep = id.indexOf("::");
                  if (sep === -1) return;
                  const attrId = id.slice(0, sep);
                  const valueId = id.slice(sep + 2);
                  const v = attributeById(attrId)?.values.find((x) => x.id === valueId);
                  if (v) addRow(attrId, v.id, v.value);
                }}
                disabled={attributes.length === 0}
              >
                <SelectTrigger>
                  <SelectValue placeholder="انتخاب مقدار" />
                </SelectTrigger>
                <SelectContent>
                  {attributes.flatMap((attr) =>
                    attr.values.map((v) => (
                      <SelectItem key={v.id} value={`${attr.id}::${v.id}`}>
                        {attr.name} — {v.value}
                      </SelectItem>
                    )),
                  )}
                </SelectContent>
              </Select>

              <Button
                type="button"
                variant="outline"
                onClick={() => setNewAttrOpen((o) => !o)}
              >
                <Plus className="h-4 w-4 ms-1" />
                مشخصه جدید
              </Button>
            </div>

            {/* Inline attribute creation */}
            {newAttrOpen && (
              <div className="space-y-2 rounded-lg border border-primary/40 bg-muted/30 p-3">
                <Input
                  value={newAttrName}
                  onChange={(e) => setNewAttrName(e.target.value)}
                  placeholder="نام مشخصه، مثلاً: رنگ"
                  className="text-sm"
                />
                <Input
                  value={newAttrValue}
                  onChange={(e) => setNewAttrValue(e.target.value)}
                  placeholder="مقدار اولیه (اختیاری)، مثلاً: قرمز"
                  className="text-sm"
                />
                <div className="flex gap-2">
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleCreateAttribute}
                    disabled={busy || !newAttrName.trim()}
                  >
                    ایجاد و انتخاب
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setNewAttrOpen(false)}
                  >
                    انصراف
                  </Button>
                </div>
              </div>
            )}

            {/* Inline value creation for the attribute just added a row for */}
            {newValueFor && (
              <div className="flex gap-2 rounded-lg border border-border p-3">
                <Input
                  value={newValueText}
                  onChange={(e) => setNewValueText(e.target.value)}
                  placeholder={`مقدار جدید برای «${attributeById(newValueFor)?.name ?? ""}»`}
                  className="text-sm"
                />
                <Button
                  type="button"
                  size="sm"
                  onClick={() => handleCreateValue(newValueFor)}
                  disabled={busy || !newValueText.trim()}
                >
                  افزودن
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={() => setNewValueFor(null)}
                >
                  انصراف
                </Button>
              </div>
            )}

            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground"
              onClick={() => {
                const firstUnused = attributes.find((a) => !value.some((r) => r.attributeId === a.id));
                if (firstUnused) setNewValueFor(firstUnused.id);
              }}
              disabled={!attributes.some((a) => !value.some((r) => r.attributeId === a.id))}
            >
              <Plus className="h-3.5 w-3.5 ms-1" />
              افزودن مقدار جدید به یکی از مشخصات
            </Button>
          </>
        )}
      </div>

      {/* ── Tags ────────────────────────────────────────────────────── */}
      <div className="space-y-2">
        <Label className="flex items-center gap-1.5">
          <Tags className="h-3.5 w-3.5" />
          برچسب‌ها
        </Label>
        <p className="text-xs text-muted-foreground">
          برچسب‌ها برای گروه‌بندی و نمایش محصول در فروشگاه استفاده می‌شوند.
        </p>
        <div className="flex flex-wrap gap-1.5">
          {tags.map((tag) => {
            const active = tagIds.includes(tag.id);
            return (
              <button
                key={tag.id}
                type="button"
                onClick={() => toggleTag(tag.id)}
                aria-pressed={active}
              >
                <Badge variant={active ? "default" : "outline"} className="cursor-pointer gap-1">
                  {tag.name}
                  {active && <X className="h-3 w-3" />}
                </Badge>
              </button>
            );
          })}
          {tags.length === 0 && !loading && (
            <p className="text-xs text-muted-foreground">برچسبی تعریف نشده است.</p>
          )}
        </div>
        {tagIds.length > 0 && (
          <p className="text-xs text-primary">
            {toPersianDigits(tagIds.length)} برچسب انتخاب شده
          </p>
        )}
        <div className="flex gap-2">
          <Input
            value={newTagName}
            onChange={(e) => setNewTagName(e.target.value)}
            placeholder="برچسب جدید"
            className="text-sm"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleCreateTag}
            disabled={busy || !newTagName.trim()}
          >
            <Plus className="h-4 w-4 ms-1" />
            ایجاد
          </Button>
        </div>
      </div>
    </div>
  );
}
