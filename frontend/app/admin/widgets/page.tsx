"use client";

/**
 * Widget areas (WordPress parity).
 *
 * Widget areas are the configurable zones of the storefront (sidebar, footer
 * columns, header bar). Each area holds an ordered list of widgets; each
 * widget has a type and a JSON config object.
 */

import { useCallback, useEffect, useState } from "react";
import { LayoutGrid, Plus, RefreshCw, Save, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { widgetsApi, type Widget, type WidgetArea } from "@/lib/api/wp-parity";

function newWidgetId() {
  return `w_${Math.random().toString(36).slice(2, 10)}`;
}

export default function WidgetsPage() {
  const { toast } = useToast();
  const [areas, setAreas] = useState<Record<string, WidgetArea>>({});
  const [types, setTypes] = useState<Record<string, { name: string; description: string }>>({});
  const [loading, setLoading] = useState(true);
  const [selectedArea, setSelectedArea] = useState<string | null>(null);
  const [draft, setDraft] = useState<Widget[]>([]);
  const [saving, setSaving] = useState(false);
  const [addingType, setAddingType] = useState("text");
  const [addingTitle, setAddingTitle] = useState("");
  const [addingContent, setAddingContent] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await widgetsApi.list();
      setAreas(res.areas);
      setTypes(res.widget_types);
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
      config: addingContent.trim() ? { content: addingContent.trim() } : {},
    };
    setDraft((prev) => [...prev, widget]);
    setAddingTitle("");
    setAddingContent("");
  };

  const removeWidget = (id: string) => {
    setDraft((prev) => prev.filter((w) => w.id !== id));
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
        <Card className="space-y-2 p-3">
          <h3 className="flex items-center gap-2 px-1 text-xs font-semibold">
            <LayoutGrid className="h-3.5 w-3.5" /> نواحی
          </h3>
          {loading ? (
            <p className="py-6 text-center text-[11px] text-muted-foreground">در حال بارگذاری…</p>
          ) : (
            Object.entries(areas).map(([id, area]) => (
              <button
                key={id}
                type="button"
                onClick={() => selectArea(id)}
                className={`flex w-full items-center justify-between rounded-md border p-2.5 text-start text-xs transition-colors ${
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
            ))
          )}
        </Card>

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

              {/* Add widget */}
              <Card className="space-y-3 p-4">
                <Label className="text-xs">افزودن ویجت</Label>
                <div className="flex flex-wrap gap-2">
                  <select
                    value={addingType}
                    onChange={(e) => setAddingType(e.target.value)}
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
                  <Input
                    value={addingContent}
                    onChange={(e) => setAddingContent(e.target.value)}
                    placeholder="محتوا (برای ویجت متنی)"
                    className="min-w-[160px] flex-1 text-xs"
                  />
                  <Button size="sm" variant="outline" onClick={addWidget}>
                    <Plus className="h-4 w-4" /> افزودن
                  </Button>
                </div>
              </Card>

              {/* Widget list */}
              {draft.length === 0 ? (
                <Card className="p-8 text-center text-xs text-muted-foreground">
                  این ناحیه هنوز ویجتی ندارد.
                </Card>
              ) : (
                <div className="space-y-2">
                  {draft.map((widget, index) => (
                    <Card key={widget.id} className="flex items-center gap-3 p-3">
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
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium">
                            {widget.title || types[widget.type]?.name || widget.type}
                          </span>
                          <Badge variant="outline" className="text-[10px]" dir="ltr">
                            {widget.type}
                          </Badge>
                        </div>
                        {typeof widget.config?.content === "string" && (
                          <div className="mt-0.5 line-clamp-1 text-[11px] text-muted-foreground">
                            {widget.config.content}
                          </div>
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeWidget(widget.id)}
                        aria-label="حذف"
                      >
                        <Trash2 className="h-4 w-4 text-muted-foreground" />
                      </Button>
                    </Card>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
