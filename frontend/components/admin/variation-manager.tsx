"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronDown,
  GripVertical,
  Loader2,
  Pencil,
  Plus,
  Trash2,
  Unlink,
} from "lucide-react";
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Checkbox } from "@/components/ui/checkbox";
import { Switch } from "@/components/ui/switch";
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
  deleteAttributeValue,
  fetchAttributes,
  updateAttributeValue,
  type ApiAttribute,
  type ApiAttributeType,
} from "@/lib/api/catalog-attributes";
import { apiErrorMessage } from "@/lib/api/error-message";

/* -------------------------------------------------------------------------- */
/*        Variation Manager (woo-variation-swatches parity, admin side)       */
/*                                                                            */
/* Turns ONE product into N purchasable options on the SAME page — the        */
/* «60 / 325 / 660 یوسی» case — instead of N duplicate product links.         */
/* Each option row is WooCommerce-variation-row parity: USD-managed prices    */
/* (Nobitex sweep), stock + low-stock threshold + backorders, SKU, and an     */
/* active switch — the same knobs a simple product's editor offers.          */
/* -------------------------------------------------------------------------- */

/** Swatch-capable attribute types (text/number are spec-sheet only). */
const VARIATION_TYPES: ApiAttributeType[] = ["label", "color", "image", "size"];

export interface VariationDraft {
  /** Existing variant id (edit mode) — present rows PATCH, absent ones CREATE. */
  id?: string;
  /** The owning product's type at draft time: physical rows carry SKU/
   *  barcode/weight, digital rows never do. */
  productType: "digital" | "physical";
  attributeId: string;
  attributeName: string;
  attributeSlug: string;
  attributeType: ApiAttributeType;
  valueId: string;
  valueLabel: string;
  valueSlug: string;
  /** Toman as typed; empty string = untouched/invalid. */
  price: string;
  compareAtPrice: string;
  /** USD source prices (Nobitex sweep). Empty = untouched; 0 = clear. */
  usdPrice: string;
  usdSalePrice: string;
  /** Typed sellable count; empty = leave untracked/unchanged. */
  stock: string;
  lowStockThreshold: string;
  backorderAllowed: boolean;
  /** «مدیریت موجودی» per option (simple-product editor parity): counted vs
   *  untracked/unlimited — how a digital product offers 100 licenses. */
  manageStock: boolean;
  /** Physical-only knobs — hidden for digital rows. */
  barcode: string;
  weight: string;
  /** Per-option gallery image (Woo variation-image parity): prefilled from
   *  the variant-scoped image; empty string on an existing row = clear. */
  imageURL: string;
  sku: string;
  isActive: boolean;
}

export interface VariationManagerValue {
  drafts: VariationDraft[];
  attributeId: string | null;
}

interface VariationManagerProps {
  value: VariationManagerValue;
  onChange: (next: VariationManagerValue) => void;
  /** Drives which row fields make sense: digital rows have no SKU/barcode/
   *  weight (the store sells licenses/codes), physical rows do. */
  productType: "digital" | "physical";
}

const digits = (s: string) => s.replace(/[^0-9]/g, "");

/** Physical-only fields ride along only for physical rows; digital rows
 *  never send SKU/barcode/weight (the product type owns that decision). */
function isPhysicalVariant(d: VariationDraft): boolean {
  return d.productType === "physical";
}

export function VariationManager({
  value,
  onChange,
  productType,
}: VariationManagerProps) {
  const isPhysical = productType === "physical";
  const { toast } = useToast();
  const confirm = useConfirm();
  // Drag-to-reorder the option rows (woo-variation-swatches parity: the row
  // order IS the storefront swatch order, persisted via variant positions).
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = value.drafts.findIndex((d) => d.valueId === active.id);
    const newIndex = value.drafts.findIndex((d) => d.valueId === over.id);
    if (oldIndex < 0 || newIndex < 0) return;
    onChange({
      ...value,
      drafts: arrayMove(value.drafts, oldIndex, newIndex),
    });
  };
  const [attributes, setAttributes] = useState<ApiAttribute[]>([]);
  const [loading, setLoading] = useState(true);
  // «فهرست خالی» و «شکست شبکه» دو پیام متفاوت می‌خواهند: خالی = راهنمای ساخت،
  // خطا = تلاش مجدد. ادغامشان اپراتور را گمراه می‌کرد (تصور حذف اشتباهی).
  const [loadError, setLoadError] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [inlineOpen, setInlineOpen] = useState(false);
  const [inlineName, setInlineName] = useState("");
  const [inlineType, setInlineType] = useState<ApiAttributeType>("label");
  const [inlineValues, setInlineValues] = useState(""); // "60 یوسی، 325 یوسی"
  const [inlineColor, setInlineColor] = useState("");
  const [creating, setCreating] = useState(false);
  // Swatch-value editor: per-value color/image/tooltip editing (the payloads
  // the storefront swatches render). Keyed by value id.
  const [valueEditorOpen, setValueEditorOpen] = useState(false);
  const [valueEdits, setValueEdits] = useState<
    Record<string, { color: string; image_url: string; tooltip: string }>
  >({});
  const [savingValueId, setSavingValueId] = useState<string | null>(null);

  const swatchAttributes = useMemo(
    () => attributes.filter((a) => VARIATION_TYPES.includes(a.type)),
    [attributes],
  );
  const selectedAttr = useMemo(
    () => swatchAttributes.find((a) => a.id === value.attributeId) ?? null,
    [swatchAttributes, value.attributeId],
  );

  const reload = async () => {
    setLoading(true);
    try {
      setAttributes(await fetchAttributes());
      setLoadError(false);
    } catch {
      setAttributes([]);
      setLoadError(true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    reload();
  }, []);

  // Type switch inside the open form (digital ⇄ physical): existing drafts
  // must follow, or the payload builder would keep sending/hiding the wrong
  // field set for rows drafted under the previous type.
  useEffect(() => {
    if (value.drafts.some((d) => d.productType !== productType)) {
      onChange({
        ...value,
        drafts: value.drafts.map((d) => ({ ...d, productType })),
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [productType]);

  const checkedValueIds = new Set(value.drafts.map((d) => d.valueId));

  const toggleValue = (
    attr: ApiAttribute,
    val: ApiAttribute["values"][number],
  ) => {
    if (checkedValueIds.has(val.id)) {
      onChange({
        ...value,
        drafts: value.drafts.filter((d) => d.valueId !== val.id),
      });
      return;
    }
    onChange({
      ...value,
      attributeId: attr.id,
      drafts: [
        ...value.drafts,
        {
          productType,
          attributeId: attr.id,
          attributeName: attr.name,
          attributeSlug: attr.slug,
          attributeType: attr.type,
          valueId: val.id,
          valueLabel: val.value,
          valueSlug: val.slug,
          price: "",
          compareAtPrice: "",
          usdPrice: "",
          usdSalePrice: "",
          stock: "",
          lowStockThreshold: "",
          backorderAllowed: false,
          manageStock: false,
          barcode: "",
          weight: "",
          imageURL: "",
          sku: "",
          isActive: true,
        },
      ],
    });
  };

  const patchDraft = (valueId: string, patch: Partial<VariationDraft>) => {
    onChange({
      ...value,
      drafts: value.drafts.map((d) =>
        d.valueId === valueId ? { ...d, ...patch } : d,
      ),
    });
  };

  const beginValueEdit = (attr: ApiAttribute) => {
    const edits: typeof valueEdits = {};
    for (const v of attr.values) {
      edits[v.id] = {
        color: v.color ?? "",
        image_url: v.image_url ?? "",
        tooltip: v.tooltip ?? "",
      };
    }
    setValueEdits(edits);
    setValueEditorOpen(true);
  };

  const saveValueEdit = async (
    attr: ApiAttribute,
    val: ApiAttribute["values"][number],
  ) => {
    const edit = valueEdits[val.id];
    if (!edit) return;
    setSavingValueId(val.id);
    try {
      await updateAttributeValue(attr.id, val.id, {
        color: edit.color || null,
        image_url: edit.image_url || null,
        tooltip: edit.tooltip || null,
      });
      await reload();
      toast({ title: `گزینهِ «${val.value}» به‌روز شد` });
    } catch (e) {
      toast({
        title: "ثبت تغییرات گزینه ناموفق بود",
        description: apiErrorMessage(e, "عملیات با خطا مواجر شد."),
        variant: "destructive",
      });
    } finally {
      setSavingValueId(null);
    }
  };

  /** Remove the draft row from this product only (the value stays in the
   *  attribute catalogue for other products). */
  const removeDraft = (draft: VariationDraft) => {
    onChange({
      ...value,
      drafts: value.drafts.filter((d) => d.valueId !== draft.valueId),
    });
  };

  /** WooCommerce term-delete parity: remove the VALUE from the attribute
   *  catalogue entirely, detaching it from every product that uses it. */
  const deleteValueEverywhere = async (draft: VariationDraft) => {
    const ok = await confirm({
      title: `حذف کامل «${draft.valueLabel}»`,
      description:
        "این گزینه از خود ویژگی حذف می‌شود و از مشخصات همه‌ی محصولاتی که استفاده‌اش کرده‌اند برداشته خواهد شد. مطمئنید؟",
      confirmLabel: "حذف کامل",
      destructive: true,
    });
    if (!ok) return;
    try {
      await deleteAttributeValue(draft.attributeId, draft.valueId, true);
      await reload();
      onChange({
        ...value,
        drafts: value.drafts.filter((d) => d.valueId !== draft.valueId),
      });
      toast({ title: `گزینه‌ی «${draft.valueLabel}» کاملاً حذف شد` });
    } catch (e) {
      toast({
        title: "حذف کامل ناموفق بود",
        description: apiErrorMessage(e, "عملیات با خطا مواجه شد."),
        variant: "destructive",
      });
    }
  };

  const handleInlineCreate = async () => {
    const name = inlineName.trim();
    if (!name) return;
    const values = inlineValues
      .split(/[,،\n]/)
      .map((v) => v.trim())
      .filter(Boolean);
    if (values.length === 0) {
      toast({
        title: "مقداری وارد نشده",
        description: "حداقل یک گزینه (مثلاً 60 یوسی) لازم است.",
        variant: "destructive",
      });
      return;
    }
    // Reuse-on-duplicate: a same-named attribute is a real one; selecting it
    // beats erroring — the operator almost certainly means THAT attribute.
    const existing = swatchAttributes.find(
      (a) => a.name.trim().toLowerCase() === name.toLowerCase(),
    );
    if (existing) {
      onChange({
        ...value,
        attributeId: existing.id,
        drafts: value.drafts.filter((d) => d.attributeId === existing.id),
      });
      setInlineOpen(false);
      setInlineName("");
      setInlineValues("");
      toast({
        title: "ویژگی موجود انتخاب شد",
        description: `«${existing.name}» از قبل وجود داشت؛ همان باز شد تا دوباره ساخته نشود.`,
      });
      return;
    }
    setCreating(true);
    try {
      const created = await createAttribute({
        name,
        type: inlineType,
        filterable: inlineType === "color",
        values: values.map((v, i) => ({
          value: v,
          position: i + 1,
          color: inlineType === "color" && inlineColor ? inlineColor : undefined,
        })),
      });
      await reload();
      onChange({ ...value, attributeId: created.id, drafts: [] });
      setInlineOpen(false);
      setInlineName("");
      setInlineValues("");
      setInlineColor("");
      toast({ title: `ویژگی «${name}» ساخته شد` });
    } catch (e) {
      toast({
        title: "ساخت ویژگی ناموفق بود",
        description: apiErrorMessage(e, "ساخت ویژگی ناموفق بود."),
        variant: "destructive",
      });
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-3 rounded-2xl border border-primary/25 bg-primary/[0.03] p-4">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-bold text-foreground">
            گزینه‌های قابل‌خرید (واریانت‌ها)
          </p>
          <p className="text-[11px] text-muted-foreground mt-0.5">
            یک محصول، چند گزینه با قیمت و موجودی مستقل — مثل ۶۰/۳۲۵/۶۶۰ یوسی؛
            بدون ساخت محصولات تکراری. برای فیلدهای کامل روی هر ردیف بزنید.
          </p>
        </div>
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-1.5"
          onClick={() => setInlineOpen((o) => !o)}
        >
          <Plus className="h-3.5 w-3.5" />
          ویژگی جدید
        </Button>
      </div>

      {inlineOpen && (
        <div className="space-y-2 rounded-xl border border-border bg-card p-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-xs">نام ویژگی</Label>
              <Input
                value={inlineName}
                onChange={(e) => setInlineName(e.target.value)}
                placeholder="مثلاً: ظرفیت شارژ یوسی"
                className="h-9 text-xs"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-xs">نوع نمایش (سواچ)</Label>
              <Select
                value={inlineType}
                onValueChange={(v) => setInlineType(v as ApiAttributeType)}
              >
                <SelectTrigger className="h-9 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="label">برچسبی (دکمه‌ای)</SelectItem>
                  <SelectItem value="color">رنگی</SelectItem>
                  <SelectItem value="image">تصویری</SelectItem>
                  <SelectItem value="size">سایز</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">گزینه‌ها (با ویرگول جدا کنید)</Label>
            <Input
              value={inlineValues}
              onChange={(e) => setInlineValues(e.target.value)}
              placeholder="60 یوسی، 325 یوسی، 660 یوسی"
              className="h-9 text-xs"
            />
          </div>
          {inlineType === "color" && (
            <div className="space-y-1">
              <Label className="text-xs">رنگ مشترک گزینه‌ها (اختیاری)</Label>
              <Input
                type="color"
                value={inlineColor || "#22c55e"}
                onChange={(e) => setInlineColor(e.target.value)}
                className="h-9 w-20 p-1"
              />
            </div>
          )}
          <Button
            type="button"
            size="sm"
            onClick={handleInlineCreate}
            disabled={creating || !inlineName.trim()}
            className="gap-1.5"
          >
            {creating && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            ساخت ویژگی و گزینه‌ها
          </Button>
        </div>
      )}

      {loading ? (
        <div className="flex items-center gap-2 py-3 text-xs text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          در حال دریافت ویژگی‌ها…
        </div>
      ) : loadError ? (
        <div className="flex items-center justify-between gap-2 py-2 text-xs">
          <span className="text-destructive">
            دریافت فهرست ویژگی‌ها ناموفق بود.
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="h-7 gap-1 text-[11px]"
            onClick={() => reload()}
          >
            تلاش مجدد
          </Button>
        </div>
      ) : swatchAttributes.length === 0 ? (
        <p className="py-2 text-xs text-muted-foreground">
          هنوز ویژگی سواچی وجود ندارد — با دکمه‌ی «ویژگی جدید» یکی بسازید.
        </p>
      ) : (
        <>
          <div className="space-y-1">
            <Label className="text-xs">انتخاب ویژگی</Label>
            <Select
              value={value.attributeId ?? undefined}
              onValueChange={(v) =>
                onChange({ ...value, attributeId: v, drafts: [] })
              }
            >
              <SelectTrigger className="h-9 text-xs">
                <SelectValue placeholder="ویژگی گزینه‌ها…" />
              </SelectTrigger>
              <SelectContent>
                {swatchAttributes.map((a) => (
                  <SelectItem key={a.id} value={a.id} className="text-xs">
                    {a.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {selectedAttr && (
            <div className="space-y-2">
              <div className="flex items-center justify-between gap-2">
                <Label className="text-xs">گزینه‌ها</Label>
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="h-7 gap-1 px-2 text-[11px] text-muted-foreground"
                  onClick={() =>
                    valueEditorOpen
                      ? setValueEditorOpen(false)
                      : beginValueEdit(selectedAttr)
                  }
                >
                  <Pencil className="h-3 w-3" />
                  سواچ مقادیر (رنگ/تصویر/تولتیپ)
                </Button>
              </div>
              {valueEditorOpen && (
                <div className="space-y-2 rounded-xl border border-border bg-card p-3">
                  <p className="text-[11px] text-muted-foreground">
                    ظاهر هر گزینه در صفحهِ محصول از اینجا می‌آید.
                  </p>
                  {selectedAttr.values.map((val) => {
                    const edit = valueEdits[val.id];
                    if (!edit) return null;
                    return (
                      <div
                        key={val.id}
                        className="grid grid-cols-1 sm:grid-cols-[auto_1fr_1fr_auto] items-center gap-2 rounded-lg border border-border/60 p-2"
                      >
                        <span className="text-xs font-semibold text-foreground w-24 truncate">
                          {val.value}
                        </span>
                        {selectedAttr.type === "color" && (
                          <div className="flex items-center gap-1.5">
                            <Input
                              type="color"
                              value={edit.color || "#22c55e"}
                              onChange={(e) =>
                                setValueEdits((prev) => ({
                                  ...prev,
                                  [val.id]: { ...(prev[val.id] ?? { color: "", image_url: "", tooltip: "" }), color: e.target.value },
                                }))
                              }
                              className="h-8 w-12 p-1"
                            />
                            <Input
                              dir="ltr"
                              value={edit.color}
                              onChange={(e) =>
                                setValueEdits((prev) => ({
                                  ...prev,
                                  [val.id]: { ...(prev[val.id] ?? { color: "", image_url: "", tooltip: "" }), color: e.target.value },
                                }))
                              }
                              placeholder="#22c55e"
                              className="h-8 text-xs"
                            />
                          </div>
                        )}
                        {selectedAttr.type === "image" && (
                          <Input
                            dir="ltr"
                            value={edit.image_url}
                            onChange={(e) =>
                              setValueEdits((prev) => ({
                                ...prev,
                                [val.id]: { ...(prev[val.id] ?? { color: "", image_url: "", tooltip: "" }), image_url: e.target.value },
                              }))
                            }
                            placeholder="URL تصویر سواچ"
                            className="h-8 text-xs"
                          />
                        )}
                        <Input
                          value={edit.tooltip}
                          onChange={(e) =>
                            setValueEdits((prev) => ({
                              ...prev,
                              [val.id]: { ...(prev[val.id] ?? { color: "", image_url: "", tooltip: "" }), tooltip: e.target.value },
                            }))
                          }
                          placeholder="تولتیپ (موس مندر روی سواچ)"
                          className="h-8 text-xs"
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="h-8 gap-1 text-[11px]"
                          disabled={savingValueId === val.id}
                          onClick={() => saveValueEdit(selectedAttr, val)}
                        >
                          {savingValueId === val.id && (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          )}
                          ذخیره
                        </Button>
                      </div>
                    );
                  })}
                </div>
              )}
              <div className="flex flex-wrap gap-2">
                {selectedAttr.values.map((val) => {
                  const checked = checkedValueIds.has(val.id);
                  return (
                    <label
                      key={val.id}
                      className={`flex cursor-pointer items-center gap-2 rounded-lg border px-2.5 py-1.5 text-xs transition-colors ${
                        checked
                          ? "border-primary bg-primary/10 font-semibold text-primary"
                          : "border-border bg-card hover:border-muted-foreground/50"
                      }`}
                    >
                      <Checkbox
                        checked={checked}
                        onCheckedChange={() => toggleValue(selectedAttr, val)}
                        className="h-3.5 w-3.5"
                      />
                      {selectedAttr.type === "color" && val.color && (
                        <span
                          className="h-3.5 w-3.5 rounded-full border border-black/10"
                          style={{ backgroundColor: val.color }}
                        />
                      )}
                      {val.value}
                    </label>
                  );
                })}
              </div>

              {value.drafts.length > 0 && (
                <div className="space-y-1.5">
                  <p className="text-[11px] font-semibold text-muted-foreground">
                    قیمت و تنظیمات هر گزینه (تومان) — برای فیلدهای کامل روی
                    ردیف بزنید؛ با دستگیرهٔ کنار ردیف ترتیب را جابه‌جا کنید:
                  </p>
                  <DndContext
                    sensors={sensors}
                    collisionDetection={closestCenter}
                    onDragEnd={handleDragEnd}
                  >
                    <SortableContext
                      items={value.drafts.map((d) => d.valueId)}
                      strategy={verticalListSortingStrategy}
                    >
                  {value.drafts.map((d) => {
                    const isExpanded = expandedId === d.valueId;
                    return (
                      <SortableVariantRow
                        key={d.valueId}
                        draft={d}
                        isExpanded={isExpanded}
                        onToggleExpand={() =>
                          setExpandedId(isExpanded ? null : d.valueId)
                        }
                      >
                      
                        {/* Row header: drag handle + identity + summary */}
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedId(isExpanded ? null : d.valueId)
                          }
                          className="flex w-full items-center gap-2 px-2.5 py-2 text-start transition-colors hover:bg-muted/40"
                        >
                          <DragHandle valueId={d.valueId} />
                          <ChevronDown
                            className={`h-3.5 w-3.5 shrink-0 text-muted-foreground transition-transform ${isExpanded ? "" : "-rotate-90"}`}
                          />
                          {d.attributeType === "color" && (
                            <span
                              className="h-3.5 w-3.5 shrink-0 rounded-full border border-black/10 bg-muted"
                              aria-hidden
                            />
                          )}
                          <span className="text-xs font-bold text-foreground flex-1 truncate">
                            {d.valueLabel}
                          </span>
                          {d.price && (
                            <Badge
                              variant="secondary"
                              className="rounded-md px-1.5 py-0 text-[10px] font-medium"
                            >
                              {toPersianDigits(d.price)} تومان
                            </Badge>
                          )}
                          {d.manageStock && d.stock !== "" && (
                            <Badge
                              variant="secondary"
                              className="rounded-md px-1.5 py-0 text-[10px] font-medium"
                            >
                              موجودی {toPersianDigits(d.stock)}
                            </Badge>
                          )}
                          {!d.isActive && (
                            <Badge
                              variant="destructive"
                              className="rounded-md px-1.5 py-0 text-[10px]"
                            >
                              غیرفعال
                            </Badge>
                          )}
                        </button>

                        {isExpanded && (
                          <div className="space-y-2.5 border-t border-border bg-muted/20 p-3">
                            <label className="flex items-center gap-2 text-xs font-medium text-foreground cursor-pointer">
                              <Switch
                                checked={d.manageStock}
                                onCheckedChange={(v) =>
                                  patchDraft(d.valueId, { manageStock: v })
                                }
                              />
                              مدیریت موجودی این گزینه
                              <span className="text-[10px] text-muted-foreground">
                                {d.manageStock
                                  ? "— شمارش می‌شود"
                                  : "— بی‌نهایت/بدون شمارش"}
                              </span>
                            </label>
                            <div className="space-y-1">
                              <Label className="text-[10px] text-muted-foreground">
                                تصویر این گزینه (در گالری و سواچ)
                              </Label>
                              <div className="flex items-center gap-2">
                                {d.imageURL ? (
                                  /* eslint-disable-next-line @next/next/no-img-element */
                                  <img
                                    src={d.imageURL}
                                    alt=""
                                    className="h-9 w-9 shrink-0 rounded-lg border border-border object-cover"
                                  />
                                ) : (
                                  <span className="h-9 w-9 shrink-0 rounded-lg border border-dashed border-border bg-muted/30" />
                                )}
                                <Input
                                  dir="ltr"
                                  value={d.imageURL}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      imageURL: e.target.value,
                                    })
                                  }
                                  placeholder="URL تصویر اختیاری — خالی = بدون تصویر"
                                  className="h-8 text-xs"
                                />
                              </div>
                            </div>
                            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  قیمت (تومان)
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="numeric"
                                  value={d.price}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      price: digits(e.target.value),
                                    })
                                  }
                                  placeholder="150000"
                                  className="h-8 text-xs"
                                />
                              </div>
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  قبل از تخفیف (تومان)
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="numeric"
                                  value={d.compareAtPrice}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      compareAtPrice: digits(e.target.value),
                                    })
                                  }
                                  placeholder="اختیاری"
                                  className="h-8 text-xs"
                                />
                              </div>
                              {isPhysical && (
                                <div className="space-y-0.5">
                                  <Label className="text-[10px] text-muted-foreground">
                                    شناسه (SKU)
                                  </Label>
                                  <Input
                                    dir="ltr"
                                    value={d.sku}
                                    onChange={(e) =>
                                      patchDraft(d.valueId, {
                                        sku: e.target.value,
                                      })
                                    }
                                    placeholder="اختیاری"
                                    className="h-8 text-xs"
                                  />
                                </div>
                              )}
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  تعداد موجودی
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="numeric"
                                  value={d.stock}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      stock: digits(e.target.value),
                                    })
                                  }
                                  disabled={!d.manageStock}
                                  placeholder={
                                    d.manageStock ? "مثلاً ۱۰۰" : "غیرفعال"
                                  }
                                  className="h-8 text-xs"
                                />
                              </div>
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  آستانه هشدار کمبود
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="numeric"
                                  value={d.lowStockThreshold}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      lowStockThreshold: digits(e.target.value),
                                    })
                                  }
                                  disabled={!d.manageStock}
                                  placeholder="پیش‌فرض ۵"
                                  className="h-8 text-xs"
                                />
                              </div>
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  قیمت پایه (دلار)
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="decimal"
                                  value={d.usdPrice}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      usdPrice: e.target.value.replace(
                                        /[^0-9.]/g,
                                        "",
                                      ),
                                    })
                                  }
                                  placeholder="خالی = مدیریت نشده"
                                  className="h-8 text-xs"
                                />
                              </div>
                              <div className="space-y-0.5">
                                <Label className="text-[10px] text-muted-foreground">
                                  قیمت ویژه (دلار)
                                </Label>
                                <Input
                                  dir="ltr"
                                  inputMode="decimal"
                                  value={d.usdSalePrice}
                                  onChange={(e) =>
                                    patchDraft(d.valueId, {
                                      usdSalePrice: e.target.value.replace(
                                        /[^0-9.]/g,
                                        "",
                                      ),
                                    })
                                  }
                                  placeholder="خالی = بدون ویژه"
                                  className="h-8 text-xs"
                                />
                              </div>
                              {d.manageStock && (
                                <div className="flex items-end pb-1">
                                  <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
                                    <Checkbox
                                      checked={d.backorderAllowed}
                                      onCheckedChange={(v) =>
                                        patchDraft(d.valueId, {
                                          backorderAllowed: v === true,
                                        })
                                      }
                                      className="h-3.5 w-3.5"
                                    />
                                    اجازه پیش‌خرید
                                  </label>
                                </div>
                              )}
                              {isPhysical && (
                                <>
                                  <div className="space-y-0.5">
                                    <Label className="text-[10px] text-muted-foreground">
                                      بارکد (GTIN/EAN)
                                    </Label>
                                    <Input
                                      dir="ltr"
                                      value={d.barcode}
                                      onChange={(e) =>
                                        patchDraft(d.valueId, {
                                          barcode: e.target.value,
                                        })
                                      }
                                      placeholder="اختیاری"
                                      className="h-8 text-xs"
                                    />
                                  </div>
                                  <div className="space-y-0.5">
                                    <Label className="text-[10px] text-muted-foreground">
                                      وزن (گرم)
                                    </Label>
                                    <Input
                                      dir="ltr"
                                      inputMode="numeric"
                                      value={d.weight}
                                      onChange={(e) =>
                                        patchDraft(d.valueId, {
                                          weight: digits(e.target.value),
                                        })
                                      }
                                      placeholder="اختیاری"
                                      className="h-8 text-xs"
                                    />
                                  </div>
                                </>
                              )}
                            </div>
                            <div className="flex items-center justify-between gap-2 pt-1 border-t border-border/60">
                              <label className="flex items-center gap-1.5 text-[11px] text-muted-foreground cursor-pointer">
                                <Switch
                                  checked={d.isActive}
                                  onCheckedChange={(v) =>
                                    patchDraft(d.valueId, { isActive: v })
                                  }
                                />
                                {d.isActive ? "فعال" : "غیرفعال"}
                              </label>
                              <div className="flex items-center gap-1.5">
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 gap-1 px-2 text-[11px] text-muted-foreground"
                                  onClick={() => removeDraft(d)}
                                  title="حذف گزینه فقط از این محصول (مقدار در ویژگی می‌ماند)"
                                >
                                  <Unlink className="h-3 w-3" />
                                  حذف از محصول
                                </Button>
                                <Button
                                  type="button"
                                  variant="ghost"
                                  size="sm"
                                  className="h-7 gap-1 px-2 text-[11px] text-destructive"
                                  onClick={() => deleteValueEverywhere(d)}
                                  title="حذف کامل گزینه از خود ویژگی"
                                >
                                  <Trash2 className="h-3 w-3" />
                                  حذف کامل
                                </Button>
                              </div>
                            </div>
                          </div>
                        )}
                      </SortableVariantRow>
                    );
                  })}
                    </SortableContext>
                  </DndContext>
                </div>
              )}
            </div>
          )}
        </>
      )}
    </div>
  );
}

/** Drag handle: the sortable activator (pointer + keyboard). */
function DragHandle({ valueId }: { valueId: string }) {
  const { attributes, listeners } = useSortable({ id: valueId });
  // A div, NOT a <button>: this handle renders inside the row-header <button>
  // (button-in-button is invalid HTML and hydrates as an error). dnd-kit's
  // own `attributes` already contribute role="button" + tabIndex, so keyboard
  // and a11y semantics stay intact.
  return (
    <div
      {...attributes}
      {...listeners}
      onClick={(e) => e.stopPropagation()}
      onKeyDown={(e) => e.stopPropagation()}
      aria-label={"جابه‌جایی ترتیب گزینه"}
      className="cursor-grab touch-none rounded-md p-1 text-muted-foreground/70 transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring active:cursor-grabbing"
    >
      <GripVertical className="h-3.5 w-3.5" />
    </div>
  );
}

/** One sortable option row: dnd-kit transform wrapper around the row card. */
function SortableVariantRow({
  draft,
  isExpanded,
  onToggleExpand,
  children,
}: {
  draft: VariationDraft;
  isExpanded: boolean;
  onToggleExpand: () => void;
  children: React.ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: draft.valueId });

  return (
    <div
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        zIndex: isDragging ? 20 : undefined,
        opacity: isDragging ? 0.85 : undefined,
      }}
      className={`rounded-xl border bg-card overflow-hidden ${
        isDragging
          ? "border-primary shadow-lg ring-2 ring-primary/20"
          : "border-border"
      } ${isExpanded ? "border-primary/40" : ""}`}
    >
      {children}
    </div>
  );
}

/** Build the payload pieces the product form sends for the drafts. */
export function variationDraftsToPayload(
  drafts: VariationDraft[],
  existingAssociations: Array<{
    attribute_id: string;
    attribute_value_id: string;
  }>,
): {
  associations: Array<{ attribute_id: string; attribute_value_id: string }>;
  variants: Array<{
    id?: string;
    price?: number;
    compare_at_price?: number | null;
    stock?: number;
    sku?: string;
    is_active: boolean;
    position: number;
    attributes: Record<string, string>;
    usd_price?: number | null;
    usd_sale_price?: number | null;
    low_stock_threshold?: number;
    backorder_allowed?: boolean;
  }>;
} {
  const assoc = [...existingAssociations];
  const assocKeys = new Set(assoc.map((a) => a.attribute_value_id));
  const variants = drafts
    .filter((d) => Number(d.price) > 0)
    .map((d, idx) => {
      if (!assocKeys.has(d.valueId)) {
        assoc.push({
          attribute_id: d.attributeId,
          attribute_value_id: d.valueId,
        });
        assocKeys.add(d.valueId);
      }
      return {
        ...(d.id ? { id: d.id } : {}),
        price: Number(d.price),
        compare_at_price: d.compareAtPrice ? Number(d.compareAtPrice) : null,
        // Stock semantics (simple-product editor parity): the manageStock
        // switch decides — ON sends the counted number, OFF sends
        // manage_stock=false (untracked/unlimited) and no count.
        ...(d.manageStock && d.stock !== "" ? { stock: Number(d.stock) } : {}),
        manage_stock: d.manageStock,
        ...(isPhysicalVariant(d) && d.barcode.trim()
          ? { barcode: d.barcode.trim() }
          : {}),
        ...(isPhysicalVariant(d) && d.weight !== ""
          ? { weight: Number(d.weight) }
          : {}),
        // Per-option image: always sent — a URL upserts, an empty string
        // clears, so removing an image in the UI actually persists.
        image_url: d.imageURL,
        ...(isPhysicalVariant(d) && d.sku.trim()
          ? { sku: d.sku.trim() }
          : {}),
        is_active: d.isActive,
        position: idx + 1,
        attributes: { [d.attributeSlug]: d.valueSlug },
        // USD: typed → number (empty on any row = untouched, backend merge
        // keeps it); explicit 0 clears per the backend's clear convention.
        ...(d.usdPrice !== "" ? { usd_price: Number(d.usdPrice) } : {}),
        ...(d.usdSalePrice !== ""
          ? { usd_sale_price: Number(d.usdSalePrice) }
          : {}),
        ...(d.manageStock && d.lowStockThreshold !== ""
          ? { low_stock_threshold: Number(d.lowStockThreshold) }
          : {}),
        ...(d.manageStock ? { backorder_allowed: d.backorderAllowed } : {}),
      };
    });
  return { associations: assoc, variants };
}

/** Prefill drafts on the EDIT path from the product detail payload. */
export function draftsFromDetail(
  groups: Array<{
    attribute_id: string;
    name: string;
    slug: string;
    type: ApiAttributeType;
    options: Array<{ value_id: string; value: string; slug: string }>;
  }>,
  variants: Array<{
    id: string;
    sku: string | null;
    price: number;
    compare_at_price?: number | null;
    is_active: boolean;
    attributes?: Record<string, unknown> | null;
    usd_price?: string | null;
    usd_sale_price?: string | null;
    available?: number | null;
    track_inventory?: boolean | null;
    low_stock_threshold?: number | null;
    backorder_allowed?: boolean | null;
    barcode?: string | null;
    weight?: number | null;
  }>,
  productType: "digital" | "physical",
  images: Array<{ variant_id?: string | null; url: string }> = [],
): VariationManagerValue {
  if (groups.length === 0) return { attributeId: null, drafts: [] };
  // Variant-scoped gallery image per option (Woo variation-image parity).
  const variantImageByVariantId = new Map(
    images
      .filter((i) => i.variant_id)
      .map((i) => [String(i.variant_id), i.url] as const),
  );
  // Single-group scope (deliberate): manage the group that actually DRIVES
  // the purchasable options — the one with the most options (the «60/325/660
  // یوسی» row), not whichever group sorted first (a 1-option color tag would
  // otherwise hijack the manager and its save would soft-retire the real
  // option variants).
  const group = groups.reduce((best, g) =>
    g.options.length > best.options.length ? g : best,
  );
  if (!group) return { attributeId: null, drafts: [] };
  const drafts: VariationDraft[] = [];
  for (const opt of group.options) {
    // Tolerant matching: prefer the group's own key, but fall back to ANY
    // key whose value equals the option slug — variants keyed by a
    // since-deleted attribute's slug (the orphan-key case) still resolve to
    // their price/stock instead of prefiling empty rows.
    const variant = variants.find(
      (v) => String(v.attributes?.[group.slug] ?? "") === opt.slug,
    ) ?? variants.find((v) =>
      Object.values(v.attributes || {}).some(
        (val) => String(val) === opt.slug,
      ),
    );
    drafts.push({
      id: variant?.id,
      productType,
      attributeId: group.attribute_id,
      attributeName: group.name,
      attributeSlug: group.slug,
      attributeType: group.type,
      valueId: opt.value_id,
      valueLabel: opt.value,
      valueSlug: opt.slug,
      price: String(variant?.price ?? ""),
      compareAtPrice:
        variant?.compare_at_price != null
          ? String(variant.compare_at_price)
          : "",
      usdPrice: variant?.usd_price != null ? String(variant.usd_price) : "",
      usdSalePrice:
        variant?.usd_sale_price != null ? String(variant.usd_sale_price) : "",
      stock:
        variant?.track_inventory === true &&
        typeof variant?.available === "number"
          ? String(variant.available)
          : "",
      lowStockThreshold:
        variant?.low_stock_threshold != null
          ? String(variant.low_stock_threshold)
          : "",
      backorderAllowed: variant?.backorder_allowed === true,
      manageStock: variant?.track_inventory === true,
      barcode: variant?.barcode ?? "",
      weight:
        variant?.weight != null && Number(variant.weight) > 0
          ? String(variant.weight)
          : "",
      imageURL: variantImageByVariantId.get(variant?.id ?? "") ?? "",
      sku: variant?.sku ?? "",
      isActive: variant?.is_active ?? true,
    });
  }
  return { attributeId: group.attribute_id, drafts };
}
