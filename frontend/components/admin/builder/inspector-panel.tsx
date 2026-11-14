"use client";

import React, { useCallback } from "react";
import {
  Sliders,
  Type,
  Maximize,
  Paintbrush,
  Shield,
  Smartphone,
  Tablet,
  Monitor,
  Link2,
  Unlink,
} from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { useBuilderStore, findElementById, type InspectorTab } from "@/stores/builder-store";
import type { DeviceStyle, SpacingBox, UnitType } from "@/types/builder";

export function InspectorPanel() {
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const ast = useBuilderStore((s) => s.ast);
  const activeBreakpoint = useBuilderStore((s) => s.activeBreakpoint);
  const setBreakpoint = useBuilderStore((s) => s.setBreakpoint);
  const activeInspectorTab = useBuilderStore((s) => s.activeInspectorTab);
  const setInspectorTab = useBuilderStore((s) => s.setInspectorTab);

  const updateElementProps = useBuilderStore((s) => s.updateElementProps);
  const updateDeviceStyles = useBuilderStore((s) => s.updateDeviceStyles);
  const updateElementStyles = useBuilderStore((s) => s.updateElementStyles);

  const selectedElement = selectedElementId
    ? findElementById(ast.rootElements, selectedElementId)
    : null;

  if (!selectedElement) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-6 text-center text-muted-foreground select-none">
        <Sliders className="w-8 h-8 opacity-40 mb-3" />
        <h4 className="text-sm font-semibold text-foreground">عنصری انتخاب نشده است</h4>
        <p className="text-xs text-muted-foreground mt-1 max-w-[200px]">
          روی یکی از عناصر داخل صفحه کلیک کنید تا تنظیمات آن نمایش داده شود.
        </p>
      </div>
    );
  }

  const props = selectedElement.widgetProps || {};
  const currentStyles = selectedElement.styles || { mobile: {} };
  const currentDeviceStyle: DeviceStyle = currentStyles[activeBreakpoint] || {};

  // ── Helper handlers ───────────────────────────────────────────────────────

  const handlePropChange = (key: string, value: unknown) => {
    updateElementProps(selectedElement.id, { [key]: value });
  };

  const handleDeviceStyleChange = (patch: Partial<DeviceStyle>) => {
    updateDeviceStyles(selectedElement.id, activeBreakpoint, patch);
  };

  const handleSpacingChange = (
    kind: "padding" | "margin",
    side: "top" | "right" | "bottom" | "left",
    val: number
  ) => {
    const currentBox: SpacingBox = currentDeviceStyle[kind] || {
      top: { value: 0, unit: "px" },
      right: { value: 0, unit: "px" },
      bottom: { value: 0, unit: "px" },
      left: { value: 0, unit: "px" },
      isLinked: true,
    };

    let updatedBox: SpacingBox;
    if (currentBox.isLinked) {
      updatedBox = {
        ...currentBox,
        top: { ...currentBox.top, value: val },
        right: { ...currentBox.right, value: val },
        bottom: { ...currentBox.bottom, value: val },
        left: { ...currentBox.left, value: val },
      };
    } else {
      updatedBox = {
        ...currentBox,
        [side]: { ...currentBox[side], value: val },
      };
    }

    handleDeviceStyleChange({ [kind]: updatedBox });
  };

  const toggleSpacingLink = (kind: "padding" | "margin") => {
    const currentBox: SpacingBox = currentDeviceStyle[kind] || {
      top: { value: 0, unit: "px" },
      right: { value: 0, unit: "px" },
      bottom: { value: 0, unit: "px" },
      left: { value: 0, unit: "px" },
      isLinked: true,
    };
    handleDeviceStyleChange({
      [kind]: { ...currentBox, isLinked: !currentBox.isLinked },
    });
  };

  // ── Render Content Tab Controls ───────────────────────────────────────────

  const renderContentControls = () => {
    if (selectedElement.type === "container") {
      const layout = selectedElement.layout || {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 3,
      };

      return (
        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label className="text-xs">نوع چیدمان کانتینر</Label>
            <Select
              value={layout.kind}
              onValueChange={(val: "flex" | "grid") => {
                const updatedRoots = ast.rootElements;
                // update layout
                useBuilderStore.setState((s) => ({
                  ast: {
                    ...s.ast,
                    rootElements: s.ast.rootElements.map((el) =>
                      el.id === selectedElement.id
                        ? { ...el, layout: { ...layout, kind: val } }
                        : el
                    ),
                  },
                  isDirty: true,
                }));
              }}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="flex">فلکس‌باکس (Flexbox)</SelectItem>
                <SelectItem value="grid">شبکه چندستونه (CSS Grid)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {layout.kind === "flex" && (
            <div className="space-y-1.5">
              <Label className="text-xs">جهت چینش (Direction)</Label>
              <Select
                value={layout.direction}
                onValueChange={(val: "column" | "row") => {
                  useBuilderStore.setState((s) => ({
                    ast: {
                      ...s.ast,
                      rootElements: s.ast.rootElements.map((el) =>
                        el.id === selectedElement.id
                          ? { ...el, layout: { ...layout, direction: val } }
                          : el
                      ),
                    },
                    isDirty: true,
                  }));
                }}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="column">عمودی (ستون)</SelectItem>
                  <SelectItem value="row">افقی (سطر)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          )}

          {layout.kind === "grid" && (
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد ستون‌ها در دسکتاپ</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={layout.gridColumns}
                onChange={(e) => {
                  const num = parseInt(e.target.value, 10) || 1;
                  useBuilderStore.setState((s) => ({
                    ast: {
                      ...s.ast,
                      rootElements: s.ast.rootElements.map((el) =>
                        el.id === selectedElement.id
                          ? { ...el, layout: { ...layout, gridColumns: num } }
                          : el
                      ),
                    },
                    isDirty: true,
                  }));
                }}
                className="h-8 text-xs"
              />
            </div>
          )}

          <div className="space-y-1.5">
            <Label className="text-xs">فاصله بین آیتم‌ها (Gap)</Label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={0}
                max={128}
                value={layout.gap.value}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  useBuilderStore.setState((s) => ({
                    ast: {
                      ...s.ast,
                      rootElements: s.ast.rootElements.map((el) =>
                        el.id === selectedElement.id
                          ? { ...el, layout: { ...layout, gap: { ...layout.gap, value: val } } }
                          : el
                      ),
                    },
                    isDirty: true,
                  }));
                }}
                className="h-8 text-xs"
              />
              <span className="text-xs text-muted-foreground">px</span>
            </div>
          </div>
        </div>
      );
    }

    switch (selectedElement.widgetType) {
      case "heading":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن عنوان</Label>
              <Input
                value={String(props.text || "")}
                onChange={(e) => handlePropChange("text", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">سطح تگ HTML</Label>
              <Select
                value={String(props.tag || "h2")}
                onValueChange={(val) => handlePropChange("tag", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="h1">H1 (عنوان اصلی)</SelectItem>
                  <SelectItem value="h2">H2 (عنوان بخش)</SelectItem>
                  <SelectItem value="h3">H3 (عنوان زیرمجموعه)</SelectItem>
                  <SelectItem value="h4">H4</SelectItem>
                  <SelectItem value="h5">H5</SelectItem>
                  <SelectItem value="h6">H6</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        );

      case "text_editor":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">محتوای متنی (HTML)</Label>
              <textarea
                rows={6}
                value={String(props.content || "")}
                onChange={(e) => handlePropChange("content", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
          </div>
        );

      case "button":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن دکمه</Label>
              <Input
                value={String(props.label || "")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیوند مقصد (URL)</Label>
              <Input
                value={String(props.url || "")}
                onChange={(e) => handlePropChange("url", e.target.value)}
                className="h-8 text-xs"
                placeholder="https://..."
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">باز شدن در تب جدید</Label>
              <Switch
                checked={Boolean(props.newTab)}
                onCheckedChange={(val) => handlePropChange("newTab", val)}
              />
            </div>
          </div>
        );

      case "image":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس تصویر (URL)</Label>
              <Input
                value={String(props.url || "")}
                onChange={(e) => handlePropChange("url", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن جایگزین (Alt Text برای سئو)</Label>
              <Input
                value={String(props.alt || "")}
                onChange={(e) => handlePropChange("alt", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "spacer":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">ارتفاع فاصله (پیکسل)</Label>
              <Input
                type="number"
                min={8}
                max={300}
                value={Number(props.height || 32)}
                onChange={(e) => handlePropChange("height", parseInt(e.target.value, 10) || 32)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      default:
        return (
          <div className="text-xs text-muted-foreground py-2">
            تنظیمات اختصاصی محتوایی برای این نوع ویجت تعریف نشده است.
          </div>
        );
    }
  };

  // ── Render Style Tab Controls (Mobile-First) ──────────────────────────────

  const renderStyleControls = () => {
    const pad = currentDeviceStyle.padding || {
      top: { value: 0, unit: "px" },
      right: { value: 0, unit: "px" },
      bottom: { value: 0, unit: "px" },
      left: { value: 0, unit: "px" },
      isLinked: true,
    };
    const mar = currentDeviceStyle.margin || {
      top: { value: 0, unit: "px" },
      right: { value: 0, unit: "px" },
      bottom: { value: 0, unit: "px" },
      left: { value: 0, unit: "px" },
      isLinked: true,
    };

    return (
      <div className="space-y-5">
        {/* Device Switcher Indicator */}
        <div className="flex items-center justify-between p-2 rounded-lg bg-muted/60 border border-border/80">
          <span className="text-[11px] font-semibold text-foreground">
            ویرایش استایل:{" "}
            {activeBreakpoint === "mobile"
              ? "موبایل (پایه)"
              : activeBreakpoint === "tablet"
              ? "تبلت (md:)"
              : "دسکتاپ (lg:)"}
          </span>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setBreakpoint("mobile")}
              className={`p-1 rounded ${activeBreakpoint === "mobile" ? "bg-primary text-white" : "text-muted-foreground"}`}
              title="موبایل"
            >
              <Smartphone className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setBreakpoint("tablet")}
              className={`p-1 rounded ${activeBreakpoint === "tablet" ? "bg-primary text-white" : "text-muted-foreground"}`}
              title="تبلت"
            >
              <Tablet className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setBreakpoint("desktop")}
              className={`p-1 rounded ${activeBreakpoint === "desktop" ? "bg-primary text-white" : "text-muted-foreground"}`}
              title="دسکتاپ"
            >
              <Monitor className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Padding Box */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">فاصله داخلی (Padding)</Label>
            <button
              type="button"
              onClick={() => toggleSpacingLink("padding")}
              className="text-muted-foreground hover:text-foreground"
            >
              {pad.isLinked ? <Link2 className="w-3.5 h-3.5 text-primary" /> : <Unlink className="w-3.5 h-3.5" />}
            </button>
          </div>
          <div className="grid grid-cols-4 gap-1.5 text-center">
            <div>
              <Input
                type="number"
                value={pad.top.value}
                onChange={(e) => handleSpacingChange("padding", "top", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">بالا</span>
            </div>
            <div>
              <Input
                type="number"
                value={pad.right.value}
                onChange={(e) => handleSpacingChange("padding", "right", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">راست</span>
            </div>
            <div>
              <Input
                type="number"
                value={pad.bottom.value}
                onChange={(e) => handleSpacingChange("padding", "bottom", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">پایین</span>
            </div>
            <div>
              <Input
                type="number"
                value={pad.left.value}
                onChange={(e) => handleSpacingChange("padding", "left", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">چپ</span>
            </div>
          </div>
        </div>

        {/* Margin Box */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">فاصله خارجی (Margin)</Label>
            <button
              type="button"
              onClick={() => toggleSpacingLink("margin")}
              className="text-muted-foreground hover:text-foreground"
            >
              {mar.isLinked ? <Link2 className="w-3.5 h-3.5 text-primary" /> : <Unlink className="w-3.5 h-3.5" />}
            </button>
          </div>
          <div className="grid grid-cols-4 gap-1.5 text-center">
            <div>
              <Input
                type="number"
                value={mar.top.value}
                onChange={(e) => handleSpacingChange("margin", "top", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">بالا</span>
            </div>
            <div>
              <Input
                type="number"
                value={mar.right.value}
                onChange={(e) => handleSpacingChange("margin", "right", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">راست</span>
            </div>
            <div>
              <Input
                type="number"
                value={mar.bottom.value}
                onChange={(e) => handleSpacingChange("margin", "bottom", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">پایین</span>
            </div>
            <div>
              <Input
                type="number"
                value={mar.left.value}
                onChange={(e) => handleSpacingChange("margin", "left", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs text-center p-1"
              />
              <span className="text-[10px] text-muted-foreground">چپ</span>
            </div>
          </div>
        </div>

        {/* Background Color */}
        <div className="space-y-1.5">
          <Label className="text-xs font-bold text-foreground">رنگ پس‌زمینه</Label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={currentDeviceStyle.background?.color || "#ffffff"}
              onChange={(e) =>
                handleDeviceStyleChange({
                  background: {
                    type: "color",
                    color: e.target.value,
                  },
                })
              }
              className="w-8 h-8 rounded border border-input cursor-pointer p-0.5"
            />
            <Input
              value={currentDeviceStyle.background?.color || ""}
              placeholder="#ffffff یا hsl(var(--card))"
              onChange={(e) =>
                handleDeviceStyleChange({
                  background: {
                    type: "color",
                    color: e.target.value,
                  },
                })
              }
              className="h-8 text-xs flex-1"
            />
          </div>
        </div>
      </div>
    );
  };

  // ── Render Advanced Tab Controls ──────────────────────────────────────────

  const renderAdvancedControls = () => {
    return (
      <div className="space-y-4">
        <div className="space-y-1.5">
          <Label className="text-xs">نام نمایشی المان در لایه‌ها</Label>
          <Input
            value={selectedElement.name}
            onChange={(e) => {
              const name = e.target.value;
              useBuilderStore.setState((s) => ({
                ast: {
                  ...s.ast,
                  rootElements: s.ast.rootElements.map((el) =>
                    el.id === selectedElement.id ? { ...el, name } : el
                  ),
                },
                isDirty: true,
              }));
            }}
            className="h-8 text-xs"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">شناسه اختصاصی CSS (ID)</Label>
          <Input
            value={selectedElement.styles.customCssId || ""}
            placeholder="my-custom-section"
            onChange={(e) =>
              updateElementStyles(selectedElement.id, {
                customCssId: e.target.value,
              })
            }
            className="h-8 text-xs"
          />
        </div>

        <div className="space-y-1.5">
          <Label className="text-xs">کلاس‌های سفارشی Tailwind / CSS</Label>
          <Input
            value={selectedElement.styles.customCssClass || ""}
            placeholder="shadow-lg border-primary/20"
            onChange={(e) =>
              updateElementStyles(selectedElement.id, {
                customCssClass: e.target.value,
              })
            }
            className="h-8 text-xs"
          />
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-border/80">
          <Label className="text-xs">مخفی کردن المان (Visibility)</Label>
          <Switch
            checked={selectedElement.isHidden}
            onCheckedChange={(val) => {
              useBuilderStore.setState((s) => ({
                ast: {
                  ...s.ast,
                  rootElements: s.ast.rootElements.map((el) =>
                    el.id === selectedElement.id ? { ...el, isHidden: val } : el
                  ),
                },
                isDirty: true,
              }));
            }}
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          <Label className="text-xs">قفل کردن المان در ویرایشگر</Label>
          <Switch
            checked={selectedElement.isLocked}
            onCheckedChange={(val) => {
              useBuilderStore.setState((s) => ({
                ast: {
                  ...s.ast,
                  rootElements: s.ast.rootElements.map((el) =>
                    el.id === selectedElement.id ? { ...el, isLocked: val } : el
                  ),
                },
                isDirty: true,
              }));
            }}
          />
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-card border-s border-border select-none">
      <div className="px-4 py-3 border-b border-border/80 flex items-center justify-between bg-muted/30">
        <div className="truncate">
          <span className="text-xs font-bold text-foreground block truncate">
            {selectedElement.name}
          </span>
          <span className="text-[10px] text-muted-foreground font-mono">
            {selectedElement.id}
          </span>
        </div>
      </div>

      <Tabs
        value={activeInspectorTab}
        onValueChange={(val) => setInspectorTab(val as InspectorTab)}
        className="flex-1 flex flex-col"
      >
        <TabsList className="grid grid-cols-3 h-9 mx-3 my-2 rounded-lg bg-muted/60 p-0.5">
          <TabsTrigger value="content" className="text-xs py-1">
            محتوا
          </TabsTrigger>
          <TabsTrigger value="style" className="text-xs py-1">
            استایل
          </TabsTrigger>
          <TabsTrigger value="advanced" className="text-xs py-1">
            پیشرفته
          </TabsTrigger>
        </TabsList>

        <div className="flex-1 overflow-y-auto px-4 py-3">
          <TabsContent value="content" className="m-0 focus-visible:outline-none">
            {renderContentControls()}
          </TabsContent>
          <TabsContent value="style" className="m-0 focus-visible:outline-none">
            {renderStyleControls()}
          </TabsContent>
          <TabsContent value="advanced" className="m-0 focus-visible:outline-none">
            {renderAdvancedControls()}
          </TabsContent>
        </div>
      </Tabs>
    </div>
  );
}
