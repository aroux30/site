"use client";

import { Fragment, useCallback, useEffect, useState } from "react";
import {
  Loader2,
  Package,
  Plus,
  Settings2,
  Tags,
  Trash2,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
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
import { toPersianDigits } from "@/lib/utils";
import {
  createAttribute,
  createAttributeValue,
  createTag,
  deleteAttribute,
  deleteAttributeValue,
  fetchAttributes,
  fetchTags,
  type ApiAttribute,
  type ApiAttributeType,
  type ApiTag,
} from "@/lib/api/catalog-attributes";
import { apiErrorMessage } from "@/lib/api/error-message";

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

/** Attribute ids minted locally for values the operator typed in the form. */
const INLINE_PREFIX = "new:";

const ATTRIBUTE_TYPE_LABELS: Record<ApiAttributeType, string> = {
  text: "متنی",
  number: "عددی",
  color: "رنگ",
  size: "سایز",
  image: "تصویری",
  label: "برچسبی",
};

/**
 * The specification sheet editor.
 *
 * Both tables behind the storefront's "مشخصات فنی کالا" tab and its faceted
 * filters were already built and had no way to be written: the product form
 * sent neither `attributes` nor `tag_ids`, so the spec tab always showed its
 * empty state.  The product form only PICKS from the catalogue; all catalogue
 * management — create attribute, create value, delete value, delete attribute
 * — happens in one «مدیریت مشخصه‌ها» dialog, so the form stays two pickers and
 * the chosen rows and nothing more.
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

  // Catalogue-management inputs (rendered inside the manage dialog). Only one
  // value input is armed at a time, and both clear themselves once created.
  const [newAttrName, setNewAttrName] = useState("");
  const [newAttrValue, setNewAttrValue] = useState("");
  const [newAttrType, setNewAttrType] = useState<ApiAttributeType>("text");
  const [newValueFor, setNewValueFor] = useState<string | null>(null);
  const [newValueText, setNewValueText] = useState("");
  const [newTagName, setNewTagName] = useState("");

  // ── Global catalogue management («مدیریت مشخصه‌ها») ────────────────────
  // Adding was always possible; until now nothing could delete a value or an
  // attribute once it was in the list, so a typo lived in every storefront
  // filter forever. The dialog below exposes the DELETE endpoints that were
  // already wired in `catalog-attributes.ts` but never rendered anywhere.
  const [manageOpen, setManageOpen] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const confirm = useConfirm();

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
    const firstValue = newAttrValue.trim();
    // The first value is required in this flow: a value-less attribute never
    // appears in the product form's «انتخاب مقدار» picker (it is built from
    // values), so creating one bare would only add a dead card to the
    // catalogue and to this dialog. More values can be added afterwards via
    // the per-attribute + button.
    if (!name || !firstValue) return;
    setBusy(true);
    try {
      const created = await createAttribute({
        name,
        type: newAttrType,
        values: [{ value: firstValue }],
      });
      await load();
      // The value typed alongside the definition is chosen straight away, so
      // the operator does not have to re-pick what they just typed.
      if (created.values[0]) {
        addRow(created.id, created.values[0].id, created.values[0].value);
      }
      setNewAttrName("");
      setNewAttrValue("");
      setNewAttrType("text");
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

  /**
   * Delete one value from the global catalogue.  First attempt is a plain
   * delete; the backend answers 409 naming how many products use it, and the
   * operator is offered the force path (detach those products, delete
   * anyway) — WooCommerce term-delete parity.  Spec rows in THIS form that
   * pointed at the deleted value are pruned so the payload never ships a
   * dead value id.
   */
  const handleDeleteValue = async (attr: ApiAttribute, valueId: string) => {
    const val = attr.values.find((v) => v.id === valueId);
    const ok = await confirm({
      title: `حذف مقدار «${val?.value ?? ""}» از مشخصه «${attr.name}»`,
      description:
        "این مقدار از فهرست مشخصات و از فیلترهای فروشگاه برای همیشه حذف می‌شود.",
      confirmLabel: "حذف",
      destructive: true,
    });
    if (!ok) return;

    setDeletingId(valueId);
    try {
      await deleteAttributeValue(attr.id, valueId);
    } catch (err) {
      const msg = apiErrorMessage(err, "");
      const productsUsed = msg.match(/(\d+)\s+product/);
      if (err && typeof err === "object" && "response" in err && productsUsed) {
        const count = toPersianDigits(productsUsed[1] ?? "");
        const forceOk = await confirm({
          title: "این مقدار در حال استفاده است",
          description: `${count} محصول از این مقدار استفاده می‌کنند. با حذف کامل، مقدار از مشخصات آن محصولات هم برداشته می‌شود (بقیه‌ی مشخصاتشان حفظ می‌شود).`,
          confirmLabel: "حذف کامل",
          destructive: true,
        });
        if (!forceOk) {
          setDeletingId(null);
          return;
        }
        try {
          await deleteAttributeValue(attr.id, valueId, true);
        } catch (forceErr) {
          toast({
            title: "حذف کامل ناموفق بود",
            description: apiErrorMessage(
              forceErr,
              "عملیات با خطا مواجه شد.",
            ),
            variant: "destructive",
          });
          setDeletingId(null);
          return;
        }
      } else {
        toast({
          title: "حذف مقدار ناموفق بود",
          description: apiErrorMessage(err, "عملیات با خطا مواجه شد."),
          variant: "destructive",
        });
        setDeletingId(null);
        return;
      }
    }

    await load();
    // Prune this form's rows that referenced the deleted value (by value id,
    // or as an inline row bound to this attribute with the same label).
    onChange(
      value.filter(
        (row) =>
          !(row.attributeId === attr.id && row.value === valueId) &&
          !(
            row.attributeId === attr.id &&
            row.valueLabel === (val?.value ?? "")
          ),
      ),
    );
    setDeletingId(null);
    toast({ title: "مقدار حذف شد", description: `«${val?.value ?? ""}» از کاتالوگ پاک شد.` });
  };

  /**
   * Delete a whole attribute.  Same two-step 409 → force flow; force strips
   * the specification rows of every product that uses the attribute.
   */
  const handleDeleteAttribute = async (attr: ApiAttribute) => {
    const ok = await confirm({
      title: `حذف مشخصه «${attr.name}»`,
      description:
        "این مشخصه با تمام مقادیرش از فهرست مشخصات و از فیلترهای فروشگاه حذف می‌شود. این عمل برگشت‌پذیر نیست.",
      confirmLabel: "حذف",
      destructive: true,
    });
    if (!ok) return;

    setDeletingId(attr.id);
    try {
      await deleteAttribute(attr.id);
    } catch (err) {
      const msg = apiErrorMessage(err, "");
      const productsUsed = msg.match(/(\d+)\s+product/);
      if (err && typeof err === "object" && "response" in err && productsUsed) {
        const count = toPersianDigits(productsUsed[1] ?? "");
        const forceOk = await confirm({
          title: "این مشخصه در حال استفاده است",
          description: `${count} محصول از این مشخصه استفاده می‌کنند. با حذف کامل، مشخصه و مقادیرش از مشخصات آن محصولات هم برداشته می‌شود.`,
          confirmLabel: "حذف کامل",
          destructive: true,
        });
        if (!forceOk) {
          setDeletingId(null);
          return;
        }
        try {
          await deleteAttribute(attr.id, true);
        } catch (forceErr) {
          toast({
            title: "حذف کامل ناموفق بود",
            description: apiErrorMessage(
              forceErr,
              "عملیات با خطا مواجه شد.",
            ),
            variant: "destructive",
          });
          setDeletingId(null);
          return;
        }
      } else {
        toast({
          title: "حذف مشخصه ناموفق بود",
          description: apiErrorMessage(err, "عملیات با خطا مواجه شد."),
          variant: "destructive",
        });
        setDeletingId(null);
        return;
      }
    }

    await load();
    // Drop this form's rows bound to the deleted attribute, inline ones too.
    onChange(value.filter((row) => row.attributeId !== attr.id));
    setDeletingId(null);
    toast({ title: "مشخصه حذف شد", description: `«${attr.name}» از کاتالوگ پاک شد.` });
  };

  const handleCreateTag = async () => {    const name = newTagName.trim();
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
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
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
            </div>

            {/* Catalogue management — the ONE place attributes and values are
                created or deleted; the form above only picks. */}
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="text-xs text-muted-foreground"
              onClick={() => setManageOpen(true)}
              disabled={loading}
            >
              <Settings2 className="h-3.5 w-3.5 ms-1" />
              مدیریت مشخصه‌ها
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

      {/* ── Manage the catalogue: add & delete attributes and values ────── */}
      <Dialog open={manageOpen} onOpenChange={setManageOpen}>
        <DialogContent className="max-w-3xl rounded-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle className="text-sm font-bold">مدیریت مشخصه‌ها</DialogTitle>
            <DialogDescription className="text-[11px] text-muted-foreground">
              افزودن و حذف مشخصه‌ها و مقادیر کاتالوگ. حذف‌ها از فیلترهای فروشگاه
              هم برداشته می‌شوند؛ اگر محصولی در حال استفاده باشد، جداگانه تأیید
              می‌گیریم.
            </DialogDescription>
          </DialogHeader>

          {/* Add an attribute: name + first value (required) + type */}
          <div className="flex flex-col gap-1.5 sm:flex-row sm:items-center">
            <Input
              value={newAttrName}
              onChange={(e) => setNewAttrName(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  newAttrName.trim() &&
                  newAttrValue.trim()
                ) {
                  handleCreateAttribute();
                }
              }}
              placeholder="نام مشخصه جدید، مثلاً: رنگ"
              className="h-8 flex-1 text-xs"
            />
            <Input
              value={newAttrValue}
              onChange={(e) => setNewAttrValue(e.target.value)}
              onKeyDown={(e) => {
                if (
                  e.key === "Enter" &&
                  newAttrName.trim() &&
                  newAttrValue.trim()
                ) {
                  handleCreateAttribute();
                }
              }}
              placeholder="مقدار اولیه، مثلاً: قرمز"
              className="h-8 flex-1 text-xs"
            />
            <Select
              value={newAttrType}
              onValueChange={(v) => setNewAttrType(v as ApiAttributeType)}
            >
              <SelectTrigger className="h-8 w-full text-xs sm:w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(ATTRIBUTE_TYPE_LABELS) as ApiAttributeType[]).map(
                  (t) => (
                    <SelectItem key={t} value={t} className="text-xs">
                      {ATTRIBUTE_TYPE_LABELS[t]}
                    </SelectItem>
                  ),
                )}
              </SelectContent>
            </Select>
            <Button
              type="button"
              size="sm"
              className="h-8 shrink-0"
              onClick={handleCreateAttribute}
              disabled={busy || !newAttrName.trim() || !newAttrValue.trim()}
              title={
                newAttrName.trim() && newAttrValue.trim()
                  ? undefined
                  : "نام مشخصه و یک مقدار را وارد کنید"
              }
            >
              {busy ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Plus className="h-3.5 w-3.5 ms-1" />
              )}
              افزودن مشخصه
            </Button>
          </div>

          {/* Formal catalogue table — mirrors the orders list view's row
              rhythm, right-aligned for Persian. Uses the arbitrary
              [text-align:right] property rather than the `text-right`
              utility, which globals.css intentionally flips to LEFT in RTL
              (logical-alignment hack) — that flip would re-align this table
              to the left edge. */}
          <div className="max-h-[55vh] overflow-y-auto rounded-lg border border-border">
            <table className="w-full text-sm [text-align:right] [&_td]:align-middle [&_th]:align-middle">
              <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
                <tr>
                  <th scope="col" className="px-4 py-3">مشخصه</th>
                  <th scope="col" className="hidden w-20 px-4 py-3 sm:table-cell">نوع</th>
                  <th scope="col" className="px-4 py-3">مقادیر</th>
                  <th scope="col" className="w-28 px-4 py-3">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {attributes.map((attr) => (
                  <Fragment key={attr.id}>
                    <tr className="transition-colors hover:bg-muted/30">
                      <td className="px-4 py-3">
                        <span className="font-semibold text-foreground">
                          {attr.name}
                        </span>
                      </td>
                      <td className="hidden px-4 py-3 text-xs text-muted-foreground sm:table-cell">
                        {ATTRIBUTE_TYPE_LABELS[attr.type] ?? attr.type}
                      </td>
                      <td className="px-4 py-3">
                        {attr.values.length > 0 ? (
                          <div className="space-y-1.5">
                            {attr.values.map((v) => (
                              <div
                                key={v.id}
                                className="flex items-center justify-start gap-2"
                              >
                                <span className="text-xs text-foreground">
                                  {v.value}
                                </span>
                                <button
                                  type="button"
                                  onClick={() => handleDeleteValue(attr, v.id)}
                                  disabled={deletingId === v.id}
                                  className="text-muted-foreground/50 transition-colors hover:text-destructive disabled:opacity-50"
                                  aria-label={`حذف مقدار ${v.value} از ${attr.name}`}
                                  title="حذف این مقدار"
                                >
                                  {deletingId === v.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                  ) : (
                                    <Trash2 className="h-3 w-3" />
                                  )}
                                </button>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}

                        {newValueFor === attr.id && (
                          <div className="mt-2 flex items-center justify-start gap-1.5">
                            <Input
                              autoFocus
                              value={newValueText}
                              onChange={(e) => setNewValueText(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter" && newValueText.trim()) {
                                  handleCreateValue(attr.id);
                                }
                                if (e.key === "Escape") setNewValueFor(null);
                              }}
                              placeholder="مقدار جدید"
                              className="h-7 w-40 text-xs"
                            />
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              className="h-7 shrink-0 px-2 text-xs"
                              onClick={() => handleCreateValue(attr.id)}
                              disabled={busy || !newValueText.trim()}
                            >
                              ثبت
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="h-7 shrink-0 px-2 text-xs text-muted-foreground"
                              onClick={() => setNewValueFor(null)}
                            >
                              لغو
                            </Button>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-start gap-1">
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-muted-foreground hover:bg-primary/10 hover:text-primary"
                            onClick={() => {
                              setNewValueFor(attr.id);
                              setNewValueText("");
                            }}
                            disabled={newValueFor === attr.id}
                            aria-label={`افزودن مقدار به ${attr.name}`}
                            title="افزودن مقدار"
                          >
                            <Plus className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="h-7 w-7 p-0 text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
                            onClick={() => handleDeleteAttribute(attr)}
                            disabled={deletingId === attr.id}
                            aria-label={`حذف مشخصه ${attr.name}`}
                            title="حذف مشخصه"
                          >
                            {deletingId === attr.id ? (
                              <Loader2 className="h-3.5 w-3.5 animate-spin" />
                            ) : (
                              <Trash2 className="h-3.5 w-3.5" />
                            )}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  </Fragment>
                ))}
                {attributes.length === 0 && (
                  <tr>
                    <td colSpan={4} className="p-0">
                      <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
                        <Package className="mb-2 h-8 w-8 opacity-40" />
                        <p className="text-sm">
                          هنوز مشخصه‌ای ثبت نشده است — از ردیف بالا اولین
                          مشخصه را بسازید.
                        </p>
                      </div>
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <Button
            type="button"
            variant="outline"
            className="h-8 w-full rounded-xl text-xs"
            onClick={() => setManageOpen(false)}
          >
            بستن
          </Button>
        </DialogContent>
      </Dialog>
    </div>
  );
}
