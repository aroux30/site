"use client";

/**
 * Widget areas (WordPress parity).
 *
 * Widget areas are the configurable zones of the storefront (sidebar, footer
 * columns, header bar). Each area holds an ordered list of widgets; each
 * widget has a type and a JSON config object.
 */

import { useCallback, useEffect, useState } from "react";
import { LayoutGrid, Plus, RefreshCw, Save, Trash2, GripVertical } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  widgetsApi,
  type Widget,
  type WidgetArea,
  type WidgetConfigField,
} from "@/lib/api/wp-parity";

function newWidgetId() {
  return `w_${Math.random().toString(36).slice(2, 10)}`;
}

/** A widget's config starts empty; the schema-driven form fills it in. */
function emptyConfig(): Record<string, unknown> {
  return {};
}

/** Render one schema-driven config control. */
function ConfigField({
  field,
  value,
  onChange,
}: {
  field: WidgetConfigField;
  value: unknown;
  onChange: (value: unknown) => void;
}) {
  const strVal = value === undefined || value === null ? "" : String(value);
  const inputClass =
    "h-9 w-full rounded-md border border-input bg-background px-2 text-xs";
  switch (field.kind) {
    case "textarea":
      return (
        <textarea
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          rows={3}
          className="w-full rounded-md border border-input bg-background p-2 text-xs"
        />
      );
    case "number":
      return (
        <Input
          type="number"
          min={field.min}
          max={field.max}
          value={strVal}
          onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
          className="h-9 text-xs"
        />
      );
    case "bool":
      return (
        <input
          type="checkbox"
          checked={value === true || value === "1"}
          onChange={(e) => onChange(e.target.checked)}
          className="h-4 w-4"
        />
      );
    case "select":
      return (
        <select
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          className={inputClass}
        >
          {(field.options ?? []).map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      );
    case "links": {
      // A list of {url,label} pairs, stored as an array in config.items.
      const items = Array.isArray(value) ? (value as Array<{ url?: string; label?: string }>) : [];
      return (
        <div className="space-y-1.5">
          {items.map((item, i) => (
            <div key={i} className="flex gap-1.5">
              <Input
                value={item.label ?? ""}
                placeholder="عنوان"
                onChange={(e) => {
                  const next = [...items];
                  next[i] = { ...next[i], label: e.target.value };
                  onChange(next);
                }}
                className="h-8 text-xs"
              />
              <Input
                value={item.url ?? ""}
                placeholder="https://…"
                dir="ltr"
                onChange={(e) => {
                  const next = [...items];
                  next[i] = { ...next[i], url: e.target.value };
                  onChange(next);
                }}
                className="h-8 text-xs"
              />
              <Button
                variant="ghost"
                size="sm"
                type="button"
                onClick={() => onChange(items.filter((_, j) => j !== i))}
                aria-label="حذف پیوند"
              >
                <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
              </Button>
            </div>
          ))}
          <Button
            variant="outline"
            size="sm"
            type="button"
            onClick={() => onChange([...items, { url: "", label: "" }])}
          >
            <Plus className="h-3.5 w-3.5" /> افزودن پیوند
          </Button>
        </div>
      );
    }
    default:
      return (
        <Input
          value={strVal}
          onChange={(e) => onChange(e.target.value)}
          className="h-9 text-xs"
        />
      );
  }
}

export default function WidgetsPage() {
  const { toast } = useToast();
  const [areas, setAreas] = useState<Record<string, WidgetArea>>({});
  const [types, setTypes] = useState<Record<string, { name: string; description: string }>>({});
  const [configSchema, setConfigSchema] = useState<Record<string, WidgetConfigField[]>>({});
  const [loading, setLoading] = useState(true);
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const [draft, setDraft] = useState<Widget[]>([]);
  const [saving, setSaving] = useState(false);
  const [addingType, setAddingType] = useState("text");
  const [addingTitle, setAddingTitle] = useState("");
  const [addingConfig, setAddingConfig] = useState<Record<string, unknown>>(emptyConfig());
  // Drag-and-drop reorder: the index being dragged, and the row it is over.
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [dragOverIndex, setDragOverIndex] = useState<number | null>(null);
  // New-area form.
  const [newAreaId, setNewAreaId] = useState("");
  const [newAreaName, setNewAreaName] = useState("");
  const [creatingArea, setCreatingArea] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await widgetsApi.list();
      setAreas(res.areas);
      setTypes(res.widget_types);
      setConfigSchema(res.config_schema ?? {});
      const first = Object.keys(res.areas)[0];
      if (first && !selectedArea) {
        setSelectedArea(first);
        setDraft(res.areas[first]?.widgets ?? []);
      }
    } catch {
      toast({ title: "بارگذاری نواحی ویجت ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast, selectedArea]);

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectArea = (id: string) => {
    setSelectedArea(id);
    setDraft(areas[id]?.widgets ?? []);
  };

  const addWidget = () => {
    const widget: Widget = {
      id: newWidgetId(),
      type: addingType,
      title: addingTitle.trim() || undefined,
      config: Object.fromEntries(
        Object.entries(addingConfig).filter(([, v]) => v !== "" && v !== undefined),
      ),
    };
    setDraft((prev) => [...prev, widget]);
    setAddingTitle("");
    setAddingConfig(emptyConfig());
  };

  const removeWidget = (id: string) => {
    setDraft((prev) => prev.filter((w) => w.id !== id));
  };

  /** Edit one field of one draft widget's config. */
  const setWidgetConfig = (id: string, key: string, value: unknown) => {
    setDraft((prev) =>
      prev.map((w) =>
        w.id === id ? { ...w, config: { ...w.config, [key]: value } } : w,
      ),
    );
  };

  const setWidgetTitle = (id: string, value: string) => {
    setDraft((prev) =>
      prev.map((w) => (w.id === id ? { ...w, title: value || undefined } : w)),
    );
  };

  const moveWidget = (index: number, dir: -1 | 1) => {
    setDraft((prev) => {
      const next = [...prev];
      const target = index + dir;
      const a = next[index];
      const b = next[target];
      if (target < 0 || target >= next.length || !a || !b) return prev;
      next[index] = b;
      next[target] = a;
      return next;
    });
  };

  /** Reorder by dropping `from` onto `to` (drag & drop). */
  const reorderWidget = (from: number, to: number) => {
    if (from === to) return;
    setDraft((prev) => {
      const next = [...prev];
      const [moved] = next.splice(from, 1);
      if (!moved) return prev;
      next.splice(to, 0, moved);
      return next;
    });
  };

  const createArea = async () => {
    const id = newAreaId.trim();
    if (!id || !/^[a-z0-9][a-z0-9_-]*$/.test(id)) {
      toast({
        title: "شناسه باید با حرف/رقم شروع شود و فقط شامل حروف کوچک، رقم، - و _ باشد",
        variant: "destructive",
      });
      return;
    }
    setCreatingArea(true);
    try {
      await widgetsApi.createArea({
        id,
        name: newAreaName.trim() || id,
        description: "",
      });
      setNewAreaId("");
      setNewAreaName("");
      toast({ title: "ناحیهٔ جدید ساخته شد" });
      await load();
      setSelectedArea(id);
      setDraft([]);
    } catch {
      toast({ title: "ساخت ناحیه ناموفق بود", variant: "destructive" });
    } finally {
      setCreatingArea(false);
    }
  };

  const deleteArea = async (id: string) => {
    if (!window.confirm(`ناحیهٔ «${areas[id]?.name ?? id}» حذف شود؟`)) return;
    try {
      await widgetsApi.deleteArea(id);
      toast({ title: "ناحیه حذف شد" });
      if (selectedArea === id) {
        setSelectedArea(null);
        setDraft([]);
      }
      await load();
    } catch {
      toast({
        title: "حذف ناحیه ناموفق بود (ناحیه‌های پیش‌فرض قابل حذف نیستند)",
        variant: "destructive",
      });
    }
  };

  const handleSave = async () => {
    if (!selectedArea) return;
    setSaving(true);
    try {
      await widgetsApi.updateArea(selectedArea, draft);
      const current = areas[selectedArea];
      if (current) {
        setAreas((prev) => ({
          ...prev,
          [selectedArea]: { ...current, widgets: draft },
        }));
      }
      toast({ title: "ناحیه ویجت ذخیره شد" });
    } catch {
      toast({ title: "ذخیره ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">نواحی ویجت</h1>
          <p className="text-xs text-muted-foreground">
            نوار کناری و ستون‌های فوتر فروشگاه را بدون تغییر کد بچینید
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}>
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} /> بارگذاری مجدد
        </Button>
      </div>

      <div className="grid gap-4 lg:grid-cols-[240px_1fr]">
        {/* Area list */}
        <div className="space-y-3">
          <Card className="space-y-2 p-3">
            <h3 className="flex items-center gap-2 px-1 text-xs font-semibold">
              <LayoutGrid className="h-3.5 w-3.5" /> نواحی
            </h3>
            {loading ? (
              <p className="py-6 text-center text-[11px] text-muted-foreground">در حال بارگذاری…</p>
            ) : (
              Object.entries(areas).map(([id, area]) => (
                <div key={id} className="group flex items-center gap-1">
                  <button
                    type="button"
                    onClick={() => selectArea(id)}
                    className={`flex flex-1 items-center justify-between rounded-md border p-2.5 text-start text-xs transition-colors ${
                      selectedArea === id
                        ? "border-primary bg-primary/5"
                        : "border-transparent hover:bg-muted/50"
                    }`}
                  >
                    <span>{area.name}</span>
                    <Badge variant="secondary" className="text-[10px]">
                      {area.widgets?.length ?? 0}
                    </Badge>
                  </button>
                  {/* Delete is offered only for operator-created areas; the
                      built-ins are refused server-side, so the button would be
                      a dead end on them. */}
                  {!["sidebar", "footer_1", "footer_2", "footer_3", "header_top"].includes(id) && (
                    <button
                      type="button"
                      onClick={() => void deleteArea(id)}
                      className="rounded-md p-1.5 text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
                      aria-label="حذف ناحیه"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))
            )}
          </Card>

          {/* New area — WordPress registers widget areas from a screen, not
              only in theme code; this is that screen. */}
          <Card className="space-y-2 p-3">
            <h3 className="px-1 text-xs font-semibold">ناحیهٔ جدید</h3>
            <Input
              value={newAreaName}
              onChange={(e) => setNewAreaName(e.target.value)}
              placeholder="نام ناحیه"
              className="h-8 text-xs"
            />
            <Input
              value={newAreaId}
              onChange={(e) => setNewAreaId(e.target.value)}
              placeholder="شناسه (مثلاً sidebar_2)"
              dir="ltr"
              className="h-8 text-xs"
            />
            <Button
              variant="outline"
              size="sm"
              onClick={() => void createArea()}
              disabled={creatingArea}
              className="w-full"
            >
              <Plus className="h-4 w-4" /> {creatingArea ? "در حال ساخت…" : "ساخت ناحیه"}
            </Button>
          </Card>
        </div>

        {/* Area editor */}
        <div className="space-y-4">
          {selectedArea && areas[selectedArea] && (
            <>
              <Card className="space-y-3 p-4">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-sm font-semibold">{areas[selectedArea].name}</div>
                    <div className="text-[11px] text-muted-foreground">
                      {areas[selectedArea].description}
                    </div>
                  </div>
                  <Button size="sm" onClick={() => void handleSave()} disabled={saving}>
                    <Save className="h-4 w-4" /> {saving ? "در حال ذخیره…" : "ذخیره"}
                  </Button>
                </div>
              </Card>

              {/* Add widget — the config form is driven by the per-type
                  schema from the API, so each type gets its own fields. */}
              <Card className="space-y-3 p-4">
                <Label className="text-xs">افزودن ویجت</Label>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={addingType}
                    onChange={(e) => {
                      setAddingType(e.target.value);
                      setAddingConfig(emptyConfig());
                    }}
                    className="h-9 rounded-md border border-input bg-background px-2 text-xs"
                  >
                    {Object.entries(types).map(([key, meta]) => (
                      <option key={key} value={key}>
                        {meta.name}
                      </option>
                    ))}
                  </select>
                  <Input
                    value={addingTitle}
                    onChange={(e) => setAddingTitle(e.target.value)}
                    placeholder="عنوان (اختیاری)"
                    className="min-w-[140px] flex-1 text-xs"
                  />
                </div>
                {(configSchema[addingType] ?? []).length > 0 && (
                  <div className="grid gap-2 sm:grid-cols-2">
                    {(configSchema[addingType] ?? []).map((field) => (
                      <div key={field.key} className="space-y-1">
                        <Label className="text-[11px] text-muted-foreground">{field.label}</Label>
                        <ConfigField
                          field={field}
                          value={addingConfig[field.key]}
                          onChange={(v) => setAddingConfig((prev) => ({ ...prev, [field.key]: v }))}
                        />
                      </div>
                    ))}
                  </div>
                )}
                <div className="flex justify-end">
                  <Button size="sm" variant="outline" onClick={addWidget}>
                    <Plus className="h-4 w-4" /> افزودن
                  </Button>
                </div>
              </Card>

              {/* Widget list — drag & drop to reorder; each row exposes its
                  own schema-driven config form. */}
              {draft.length === 0 ? (
                <Card className="p-8 text-center text-xs text-muted-foreground">
                  این ناحیه هنوز ویجتی ندارد.
                </Card>
              ) : (
                <div className="space-y-2">
                  {draft.map((widget, index) => {
                    const fields = configSchema[widget.type] ?? [];
                    return (
                      <Card
                        key={widget.id}
                        draggable
                        onDragStart={() => setDragIndex(index)}
                        onDragOver={(e) => {
                          e.preventDefault();
                          setDragOverIndex(index);
                        }}
                        onDrop={(e) => {
                          e.preventDefault();
                          if (dragIndex !== null) reorderWidget(dragIndex, index);
                          setDragIndex(null);
                          setDragOverIndex(null);
                        }}
                        onDragEnd={() => {
                          setDragIndex(null);
                          setDragOverIndex(null);
                        }}
                        className={`space-y-3 p-3 transition-colors ${
                          dragOverIndex === index && dragIndex !== index
                            ? "border-primary/60"
                            : ""
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <span
                            className="cursor-grab text-muted-foreground"
                            title="برای جابه‌جایی بکشید"
                            aria-hidden
                          >
                            <GripVertical className="h-4 w-4" />
                          </span>
                          <div className="flex flex-1 items-center gap-2">
                            <Input
                              value={widget.title ?? ""}
                              onChange={(e) => setWidgetTitle(widget.id, e.target.value)}
                              placeholder={types[widget.type]?.name ?? widget.type}
                              className="h-8 max-w-[220px] text-xs"
                            />
                            <Badge variant="outline" className="text-[10px]" dir="ltr">
                              {widget.type}
                            </Badge>
                          </div>
                          <div className="flex flex-col gap-0.5">
                            <button
                              type="button"
                              onClick={() => moveWidget(index, -1)}
                              className="text-[10px] text-muted-foreground hover:text-foreground"
                              aria-label="بالا"
                            >
                              ▲
                            </button>
                            <button
                              type="button"
                              onClick={() => moveWidget(index, 1)}
                              className="text-[10px] text-muted-foreground hover:text-foreground"
                              aria-label="پایین"
                            >
                              ▼
                            </button>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeWidget(widget.id)}
                            aria-label="حذف"
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground" />
                          </Button>
                        </div>
                        {fields.length > 0 && (
                          <div className="grid gap-2 border-t border-border pt-2 sm:grid-cols-2">
                            {fields.map((field) => (
                              <div key={field.key} className="space-y-1">
                                <Label className="text-[11px] text-muted-foreground">
                                  {field.label}
                                </Label>
                                <ConfigField
                                  field={field}
                                  value={widget.config?.[field.key]}
                                  onChange={(v) => setWidgetConfig(widget.id, field.key, v)}
                                />
                              </div>
                            ))}
                          </div>
                        )}
                      </Card>
                    );
                  })}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
