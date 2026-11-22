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
import { Textarea } from "@/components/ui/textarea";
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
import { MediaPicker } from "@/components/admin/media-picker";
import { useBuilderStore, findElementById, type InspectorTab } from "@/stores/builder-store";
import { toValidHexColor, normalizeCssColor } from "@/lib/builder/color-utils";
import { BUILDER_ICON_OPTIONS } from "@/lib/builder/icon-map";
import { cn } from "@/lib/utils";
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
  const updateElementLayout = useBuilderStore((s) => s.updateElementLayout);
  const renameElement = useBuilderStore((s) => s.renameElement);
  const updateElementName = useBuilderStore((s) => s.updateElementName);
  const setElementHidden = useBuilderStore((s) => s.setElementHidden);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);
  const setElementLocked = useBuilderStore((s) => s.setElementLocked);
  const toggleLockElement = useBuilderStore((s) => s.toggleLockElement);
  const detachGlobalComponent = useBuilderStore((s) => s.detachGlobalComponent);
  const unlinkGlobalComponent = useBuilderStore((s) => s.unlinkGlobalComponent);

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
                updateElementLayout(selectedElement.id, { kind: val });
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
            <>
              <div className="space-y-1.5">
                <Label className="text-xs">جهت چینش (Direction)</Label>
                <Select
                  value={layout.direction}
                  onValueChange={(val: "column" | "row") => {
                    updateElementLayout(selectedElement.id, { direction: val });
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

              <div className="space-y-1.5">
                <Label className="text-xs">ترازبندی افقی / اصلی (Justify Content)</Label>
                <Select
                  value={layout.justifyContent || "start"}
                  onValueChange={(val: any) => {
                    updateElementLayout(selectedElement.id, { justifyContent: val });
                  }}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="start">شروع (Start)</SelectItem>
                    <SelectItem value="center">وسط (Center)</SelectItem>
                    <SelectItem value="end">پایان (End)</SelectItem>
                    <SelectItem value="between">فاصله‌گذاری مساوی (Between)</SelectItem>
                    <SelectItem value="around">فاصله‌گذاری دور (Around)</SelectItem>
                    <SelectItem value="evenly">یکدست (Evenly)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">ترازبندی عمودی / فرعی (Align Items)</Label>
                <Select
                  value={layout.alignItems || "stretch"}
                  onValueChange={(val: any) => {
                    updateElementLayout(selectedElement.id, { alignItems: val });
                  }}
                >
                  <SelectTrigger className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="stretch">کشیده (Stretch)</SelectItem>
                    <SelectItem value="center">وسط (Center)</SelectItem>
                    <SelectItem value="start">شروع (Start)</SelectItem>
                    <SelectItem value="end">پایان (End)</SelectItem>
                    <SelectItem value="baseline">خط مبنا (Baseline)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center justify-between pt-1">
                <Label className="text-xs">شکستن به سطر بعدی (Flex Wrap)</Label>
                <Switch
                  checked={layout.flexWrap === "wrap"}
                  onCheckedChange={(val) => {
                    updateElementLayout(selectedElement.id, { flexWrap: val ? "wrap" : "nowrap" });
                  }}
                />
              </div>
            </>
          )}

          {layout.kind === "grid" && (
            <>
              <div className="space-y-1.5">
                <Label className="text-xs">تعداد ستون‌ها در دسکتاپ</Label>
                <Input
                  data-testid="grid-columns-input"
                  type="number"
                  min={1}
                  max={12}
                  value={layout.gridColumns}
                  onChange={(e) => {
                    const num = parseInt(e.target.value, 10) || 1;
                    updateElementLayout(selectedElement.id, { gridColumns: num });
                  }}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>

              <div className="space-y-1.5">
                <Label className="text-xs">جریان خودکار شبکه (Grid Auto Flow)</Label>
                <Select
                  value={layout.gridAutoFlow || "row"}
                  onValueChange={(val: any) => {
                    updateElementLayout(selectedElement.id, { gridAutoFlow: val });
                  }}
                >
                  <SelectTrigger data-testid="grid-auto-flow-select" className="h-8 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="row">سطری (Row)</SelectItem>
                    <SelectItem value="column">ستونی (Column)</SelectItem>
                    <SelectItem value="dense">فشرده (Dense)</SelectItem>
                    <SelectItem value="row dense">سطری فشرده (Row Dense)</SelectItem>
                    <SelectItem value="column dense">ستونی فشرده (Column Dense)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </>
          )}

          <div className="space-y-1.5">
            <Label className="text-xs">فاصله بین آیتم‌ها (Gap)</Label>
            <div className="relative flex items-center">
              <Input
                data-testid="container-gap-input"
                type="number"
                min={0}
                max={128}
                value={layout.gap.value}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  updateElementLayout(selectedElement.id, {
                    gap: { ...layout.gap, value: val },
                  });
                }}
                className="h-8 text-xs pe-8 ps-2"
                dir="ltr"
              />
              <span className="absolute end-2 text-[11px] font-mono text-muted-foreground select-none pointer-events-none">
                px
              </span>
            </div>
          </div>

          {/* Container Width (Boxed vs Full Width - Elementor Parity) */}
          <div className="space-y-1.5 pt-2 border-t">
            <Label className="text-xs font-semibold">محدوده عرض کانتینر (Content Width)</Label>
            <div className="grid grid-cols-2 gap-1.5">
              <button
                type="button"
                data-testid="container-width-boxed-btn"
                onClick={() => {
                  updateElementLayout(selectedElement.id, {
                    boxedWidth: { value: 1280, unit: "px" },
                  });
                }}
                className={cn(
                  "py-1.5 px-2 rounded-lg text-xs font-semibold border transition",
                  layout.boxedWidth
                    ? "bg-primary text-primary-foreground border-primary shadow-xs"
                    : "bg-muted/60 text-muted-foreground hover:text-foreground border-border/70"
                )}
              >
                جعبه‌ای (Boxed)
              </button>
              <button
                type="button"
                data-testid="container-width-full-btn"
                onClick={() => {
                  updateElementLayout(selectedElement.id, {
                    boxedWidth: null,
                  });
                }}
                className={cn(
                  "py-1.5 px-2 rounded-lg text-xs font-semibold border transition",
                  !layout.boxedWidth
                    ? "bg-primary text-primary-foreground border-primary shadow-xs"
                    : "bg-muted/60 text-muted-foreground hover:text-foreground border-border/70"
                )}
              >
                تمام‌عرض (Full Width)
              </button>
            </div>
            {layout.boxedWidth && (
              <div className="relative flex items-center mt-1">
                <Input
                  data-testid="container-boxed-width-input"
                  type="number"
                  min={320}
                  max={2560}
                  value={layout.boxedWidth.value}
                  onChange={(e) => {
                    const val = parseFloat(e.target.value) || 1280;
                    updateElementLayout(selectedElement.id, {
                      boxedWidth: { value: val, unit: "px" },
                    });
                  }}
                  className="h-8 text-xs pe-8 ps-2"
                  dir="ltr"
                />
                <span className="absolute end-2 text-[11px] font-mono text-muted-foreground select-none pointer-events-none">
                  px
                </span>
              </div>
            )}
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
                data-testid="heading-text-input"
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
      case "paragraph":
      case "text":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">محتوای متنی</Label>
              <textarea
                data-testid="text-editor-textarea"
                rows={6}
                value={String(props.content || props.text || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim()}
                onChange={(e) => {
                  handlePropChange("content", e.target.value);
                  handlePropChange("text", e.target.value);
                }}
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
                data-testid="button-label-input"
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
              <Label className="text-xs">انتخاب از کتابخانه رسانه</Label>
              <MediaPicker
                value={String(props.url || "")}
                onChange={(url) => handlePropChange("url", url)}
                label="انتخاب یا آپلود تصویر"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس مستقیم تصویر (URL)</Label>
              <Input
                value={String(props.url || "")}
                onChange={(e) => handlePropChange("url", e.target.value)}
                className="h-8 text-xs font-mono"
                placeholder="https://... یا /placeholder.svg"
                dir="ltr"
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

      case "menu_anchor":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">شناسه لنگر (Anchor ID)</Label>
              <Input
                data-testid="menu-anchor-input"
                value={String(props.anchor_id || "")}
                placeholder="features"
                onChange={(e) => handlePropChange("anchor_id", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
              <p className="text-[10px] text-muted-foreground leading-relaxed">
                برای لینک دادن به این نقطه از صفحه، در دکمه یا منو آدرس را به صورت <span className="text-primary font-bold">#features</span> وارد کنید.
              </p>
            </div>
          </div>
        );

      case "spacer":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">ارتفاع فاصله (پیکسل)</Label>
              <Input
                data-testid="spacer-height-input"
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

      case "html_custom":
      case "legacy_html":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">کد HTML سفارشی</Label>
              <textarea
                rows={8}
                value={String(props.html || props.content || "")}
                onChange={(e) => handlePropChange("html", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 font-mono text-[11px] leading-relaxed"
                dir="ltr"
                placeholder="<div>...</div>"
              />
            </div>
          </div>
        );

      case "table": {
        const headers = (props.headers as string[]) || [];
        const rows = (props.rows as string[][]) || [];
        const bordered = props.bordered !== false;
        const striped = props.striped !== false;
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عناوین ستون‌ها (با کاما جدا کنید)</Label>
              <Input
                data-testid="table-headers-input"
                value={headers.join("، ")}
                onChange={(e) => {
                  const arr = e.target.value.split(/[،,]/).map((s) => s.trim());
                  handlePropChange("headers", arr);
                }}
                className="h-8 text-xs"
                placeholder="عنوان ۱، عنوان ۲، عنوان ۳"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">سطرهای داده (هر خط یک سطر، با کاما جدا کنید)</Label>
              <textarea
                rows={5}
                value={rows.map((r) => r.join("، ")).join("\n")}
                onChange={(e) => {
                  const newRows = e.target.value
                    .split("\n")
                    .map((line) => line.split(/[،,]/).map((s) => s.trim()))
                    .filter((r) => r.length > 0 && r.some((c) => c !== ""));
                  handlePropChange("rows", newRows);
                }}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
                placeholder="سطر ۱: سلول ۱، سلول ۲&#10;سطر ۲: سلول ۱، سلول ۲"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">حاشیه و خطوط کادر (Bordered)</Label>
              <Switch
                checked={bordered}
                onCheckedChange={(val) => handlePropChange("bordered", val)}
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">سطرهای یک‌در‌میان رنگی (Striped)</Label>
              <Switch
                checked={striped}
                onCheckedChange={(val) => handlePropChange("striped", val)}
              />
            </div>
          </div>
        );
      }

      case "form_input":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان فیلد (Label)</Label>
              <Input
                data-testid="form-input-label-input"
                value={String(props.label || "")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام فیلد (Field Name)</Label>
              <Input
                value={String(props.name || "")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن راهنما (Placeholder)</Label>
              <Input
                value={String(props.placeholder || "")}
                onChange={(e) => handlePropChange("placeholder", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نوع ورودی</Label>
              <Select
                value={String(props.input_type || "text")}
                onValueChange={(val) => handlePropChange("input_type", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="text">متن عادی (Text)</SelectItem>
                  <SelectItem value="email">ایمیل (Email)</SelectItem>
                  <SelectItem value="tel">تلفن همراه (Tel)</SelectItem>
                  <SelectItem value="number">عدد (Number)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">فیلد اجباری (Required)</Label>
              <Switch
                checked={Boolean(props.required)}
                onCheckedChange={(val) => handlePropChange("required", val)}
              />
            </div>
          </div>
        );

      case "form_textarea":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان فیلد (Label)</Label>
              <Input
                data-testid="form-textarea-label-input"
                value={String(props.label || "")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام فیلد (Field Name)</Label>
              <Input
                value={String(props.name || "")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن راهنما (Placeholder)</Label>
              <Input
                value={String(props.placeholder || "")}
                onChange={(e) => handlePropChange("placeholder", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد سطرها (ارتفاع)</Label>
              <Input
                type="number"
                min={2}
                max={20}
                value={Number(props.rows || 4)}
                onChange={(e) => handlePropChange("rows", parseInt(e.target.value, 10) || 4)}
                className="h-8 text-xs"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">فیلد اجباری (Required)</Label>
              <Switch
                checked={Boolean(props.required)}
                onCheckedChange={(val) => handlePropChange("required", val)}
              />
            </div>
          </div>
        );

      case "form_select":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان فیلد (Label)</Label>
              <Input
                data-testid="form-select-label-input"
                value={String(props.label || "")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام فیلد (Field Name)</Label>
              <Input
                value={String(props.name || "")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">گزینه‌ها (با کاما یا در خطوط جداگانه بنویسید)</Label>
              <textarea
                rows={4}
                value={Array.isArray(props.options) ? props.options.join("\n") : ""}
                onChange={(e) => {
                  const opts = e.target.value.split(/[\n،,]/).map((s) => s.trim()).filter(Boolean);
                  handlePropChange("options", opts);
                }}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
                placeholder="گزینه ۱&#10;گزینه ۲&#10;گزینه ۳"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">فیلد اجباری (Required)</Label>
              <Switch
                checked={Boolean(props.required)}
                onCheckedChange={(val) => handlePropChange("required", val)}
              />
            </div>
          </div>
        );

      case "product_card":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">نام محصول</Label>
              <Input
                data-testid="product-card-name-input"
                value={String(props.name || "")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">قیمت فروش (تومان)</Label>
                <Input
                  type="number"
                  value={Number(props.min_price) || 0}
                  onChange={(e) => handlePropChange("min_price", parseFloat(e.target.value) || 0)}
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">قیمت اصلی / خط خورده</Label>
                <Input
                  type="number"
                  value={Number(props.max_price) || 0}
                  onChange={(e) => handlePropChange("max_price", parseFloat(e.target.value) || 0)}
                  className="h-8 text-xs"
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تصویر محصول</Label>
              <MediaPicker
                value={String(props.primary_image_url || "")}
                onChange={(url) => handlePropChange("primary_image_url", url)}
                label="انتخاب تصویر محصول"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">موجود در انبار</Label>
              <Switch
                checked={props.is_in_stock !== false}
                onCheckedChange={(val) => handlePropChange("is_in_stock", val)}
              />
            </div>
          </div>
        );

      case "product_grid":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد کالاهای نمایشی</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={Number(props.limit) || 4}
                onChange={(e) => handlePropChange("limit", parseInt(e.target.value) || 4)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">فیلتر پیش‌فرض محصولات</Label>
              <Select
                value={String(props.filter || "all")}
                onValueChange={(val) => handlePropChange("filter", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">همه محصولات</SelectItem>
                  <SelectItem value="featured">کالاهای ویژه</SelectItem>
                  <SelectItem value="best_sellers">پرفروش‌ترین‌ها</SelectItem>
                  <SelectItem value="new_arrivals">جدیدترین‌ها</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش دکمه مشاهده بیشتر</Label>
              <Switch
                checked={props.show_pagination !== false}
                onCheckedChange={(val) => handlePropChange("show_pagination", val)}
              />
            </div>
          </div>
        );

      case "star_rating":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">امتیاز (از ۵)</Label>
              <Input
                data-testid="star-rating-value-input"
                type="number"
                step="0.1"
                min="0"
                max="5"
                value={Number(props.value) || 5}
                onChange={(e) => handlePropChange("value", parseFloat(e.target.value) || 5)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد نظرات</Label>
              <Input
                type="number"
                value={Number(props.reviewCount) || 0}
                onChange={(e) => handlePropChange("reviewCount", parseInt(e.target.value) || 0)}
                className="h-8 text-xs"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش عدد امتیاز</Label>
              <Switch
                checked={props.showValue !== false}
                onCheckedChange={(val) => handlePropChange("showValue", val)}
              />
            </div>
          </div>
        );

      case "review_histogram":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">میانگین امتیازات</Label>
              <Input
                type="number"
                step="0.1"
                min="0"
                max="5"
                value={Number(props.averageRating) || 4.5}
                onChange={(e) => handlePropChange("averageRating", parseFloat(e.target.value) || 4.5)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد کل نظرات</Label>
              <Input
                type="number"
                value={Number(props.totalReviews) || 0}
                onChange={(e) => handlePropChange("totalReviews", parseInt(e.target.value) || 0)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "product_title":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان نمایشی محصول</Label>
              <Input
                value={String(props.fallback_title || "عنوان محصول")}
                onChange={(e) => handlePropChange("fallback_title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "recently_viewed":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان بخش</Label>
              <Input
                value={String(props.title || "بازدیدهای اخیر شما")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد کالاهای اخیر (Limit)</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={Number(props.limit) || 4}
                onChange={(e) => handlePropChange("limit", parseInt(e.target.value) || 4)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "mega_menu":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان دکمه ناوبری (Label)</Label>
              <Input
                value={String(props.label || "دسته‌بندی کالاها")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "product_price":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">قیمت فروش (تومان)</Label>
              <Input
                data-testid="product-price-input"
                type="number"
                value={Number(props.price) || 0}
                onChange={(e) => handlePropChange("price", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">قیمت قبل تخفیف (تومان)</Label>
              <Input
                type="number"
                value={Number(props.compare_at_price) || 0}
                onChange={(e) => handlePropChange("compare_at_price", parseFloat(e.target.value) || 0)}
                className="h-8 text-xs font-mono"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش درصد تخفیف</Label>
              <Switch
                checked={props.show_discount !== false}
                onCheckedChange={(val) => handlePropChange("show_discount", val)}
              />
            </div>
          </div>
        );

      case "add_to_cart":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن روی دکمه</Label>
              <Input
                data-testid="add-to-cart-label-input"
                value={String(props.label || "افزودن به سبد خرید")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش انتخابگر تعداد</Label>
              <Switch
                checked={props.show_quantity !== false}
                onCheckedChange={(val) => handlePropChange("show_quantity", val)}
              />
            </div>
          </div>
        );

      case "product_variants": {
        const variants = (props.variants as any[]) || [
          { id: "var_1", title: "مشکی مات", price: 1850000, is_in_stock: true },
          { id: "var_2", title: "سفید صدفی", price: 1950000, is_in_stock: true },
        ];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان انتخابگر</Label>
              <Input
                value={String(props.product_title || "انتخاب تنوع و مشخصات")}
                onChange={(e) => handlePropChange("product_title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2 pt-2 border-t">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold">تنوع‌های محصول (Variants)</Label>
                <button
                  type="button"
                  onClick={() => {
                    const newVar = {
                      id: `var_${Date.now()}`,
                      title: `تنوع جدید ${variants.length + 1}`,
                      price: 1850000,
                      is_in_stock: true,
                    };
                    handlePropChange("variants", [...variants, newVar]);
                  }}
                  className="text-[11px] text-primary hover:underline font-semibold"
                >
                  + افزودن تنوع
                </button>
              </div>
              <div className="space-y-2">
                {variants.map((v, idx) => (
                  <div key={v.id || idx} className="p-2 rounded-lg border bg-muted/20 space-y-2">
                    <div className="flex items-center justify-between">
                      <Input
                        value={v.title || ""}
                        placeholder="عنوان تنوع"
                        onChange={(e) => {
                          const updated = [...variants];
                          updated[idx] = { ...updated[idx], title: e.target.value };
                          handlePropChange("variants", updated);
                        }}
                        className="h-7 text-xs flex-1 me-2"
                      />
                      {variants.length > 1 && (
                        <button
                          type="button"
                          onClick={() => {
                            const updated = variants.filter((_, i) => i !== idx);
                            handlePropChange("variants", updated);
                          }}
                          className="text-[10px] text-destructive hover:underline shrink-0"
                        >
                          حذف
                        </button>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex-1 space-y-1">
                        <Label className="text-[10px] text-muted-foreground">قیمت (تومان)</Label>
                        <Input
                          type="number"
                          value={v.price || 0}
                          onChange={(e) => {
                            const updated = [...variants];
                            updated[idx] = { ...updated[idx], price: parseFloat(e.target.value) || 0 };
                            handlePropChange("variants", updated);
                          }}
                          className="h-7 text-xs font-mono"
                        />
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        );
      }

      case "mini_cart":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان سبد</Label>
              <Input
                value={String(props.label || "سبد خرید")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش نشانگر تعداد (Badge)</Label>
              <Switch
                checked={props.show_badge !== false}
                onCheckedChange={(val) => handlePropChange("show_badge", val)}
              />
            </div>
          </div>
        );

      case "cart_summary":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان خلاصه سبد</Label>
              <Input
                value={String(props.title || "خلاصه سبد خرید")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن دکمه تسویه</Label>
              <Input
                value={String(props.button_label || "ادامه فرآیند خرید")}
                onChange={(e) => handlePropChange("button_label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس صفحه تسویه حساب</Label>
              <Input
                value={String(props.checkout_url || "/checkout")}
                onChange={(e) => handlePropChange("checkout_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش ردیف تخفیف</Label>
              <Switch
                checked={props.show_discount !== false}
                onCheckedChange={(val) => handlePropChange("show_discount", val)}
              />
            </div>
          </div>
        );

      case "form_container":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس اندپوینت ثبت فرم (Action URL)</Label>
              <Input
                data-testid="form-container-submit-url"
                value={String(props.submit_url || "/api/v1/content/forms/submit")}
                onChange={(e) => handlePropChange("submit_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیام موفقیت‌آمیز ثبت</Label>
              <Input
                data-testid="form-container-success-input"
                value={String(props.success_message || "پیام شما با موفقیت ثبت شد.")}
                onChange={(e) => handlePropChange("success_message", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیام خطا در ارسال</Label>
              <Input
                value={String(props.error_message || "خطا در ارسال فرم. لطفاً فیلدها را بررسی نمایید.")}
                onChange={(e) => handlePropChange("error_message", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "form_checkbox":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن چک‌باکس</Label>
              <Input
                value={String(props.label || "شرایط و قوانین را مطالعه کرده و می‌پذیرم")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام فیلد (Field Name)</Label>
              <Input
                value={String(props.name || "accept_terms")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">فیلد الزامی (Required)</Label>
              <Switch
                checked={Boolean(props.required)}
                onCheckedChange={(val) => handlePropChange("required", val)}
              />
            </div>
          </div>
        );

      case "form_radio":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان گروه گزینه‌ها</Label>
              <Input
                value={String(props.label || "روش ارسال")}
                onChange={(e) => handlePropChange("label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام فیلد (Field Name)</Label>
              <Input
                value={String(props.name || "shipping_method")}
                onChange={(e) => handlePropChange("name", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">گزینه‌ها (هر سطر یک گزینه)</Label>
              <textarea
                rows={4}
                value={Array.isArray(props.options) ? (props.options as string[]).join("\n") : "گزینه یک\nگزینه دو"}
                onChange={(e) => handlePropChange("options", e.target.value.split("\n").filter((s) => s.trim()))}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
          </div>
        );

      case "accordion": {
        const items = (props.items as any[]) || [];
        return (
          <div className="space-y-4">
            <Label className="text-xs font-bold block">مدیریت آیتم‌های تاشو (Accordion)</Label>
            {items.map((item, idx) => (
              <div key={idx} className="p-2.5 rounded-lg border bg-muted/30 space-y-2">
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <Label className="text-[11px]">عنوان سؤال {idx + 1}</Label>
                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = items.filter((_, i) => i !== idx);
                          handlePropChange("items", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    data-testid={`accordion-item-title-${idx}`}
                    value={item.title || ""}
                    onChange={(e) => {
                      const updated = [...items];
                      updated[idx] = { ...updated[idx], title: e.target.value };
                      handlePropChange("items", updated);
                    }}
                    className="h-7 text-xs"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-[11px]">پاسخ / توضیحات</Label>
                  <textarea
                    rows={2}
                    value={item.content || ""}
                    onChange={(e) => {
                      const updated = [...items];
                      updated[idx] = { ...updated[idx], content: e.target.value };
                      handlePropChange("items", updated);
                    }}
                    className="w-full rounded-md border border-input bg-background p-1.5 text-xs"
                  />
                </div>
              </div>
            ))}
            <button
              type="button"
              data-testid="accordion-add-item-btn"
              onClick={() => handlePropChange("items", [...items, { title: "سؤال جدید", content: "پاسخ جدید" }])}
              className="w-full py-1.5 rounded-lg border border-dashed border-primary text-xs font-semibold text-primary hover:bg-primary/5 transition"
            >
              + افزودن آیتم جدید به آکاردئون
            </button>
          </div>
        );
      }

      case "countdown":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان شمارنده</Label>
              <Input
                value={String(props.title || "مهلت تخفیف ویژه")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">تاریخ و ساعت پایان (ISO 8601)</Label>
              <Input
                value={String(props.target_date || "")}
                onChange={(e) => handlePropChange("target_date", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
                placeholder="2026-12-31T23:59:59"
              />
            </div>
          </div>
        );

      case "video":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">نوع منبع ویدئو</Label>
              <Select
                value={String(props.video_type || "aparat")}
                onValueChange={(val) => handlePropChange("video_type", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="aparat">آپارات (Aparat)</SelectItem>
                  <SelectItem value="youtube">یوتیوب (YouTube)</SelectItem>
                  <SelectItem value="direct">فایل مستقیم MP4</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس ویدئو (URL)</Label>
              <Input
                value={String(props.url || "")}
                onChange={(e) => handlePropChange("url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
                placeholder="https://www.aparat.com/video/video/embed/videohash/..."
              />
            </div>
          </div>
        );

      case "icon_box":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">انتخاب آیکون</Label>
              <Select
                value={String(props.icon || "shield-check")}
                onValueChange={(val) => handlePropChange("icon", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-56">
                  {BUILDER_ICON_OPTIONS.map((opt) => (
                    <SelectItem key={opt.id} value={opt.id} className="text-xs">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان ویژگی</Label>
              <Input
                data-testid="iconbox-title-input"
                value={String(props.title || "ضمانت اصالت و سلامت")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">توضیحات</Label>
              <textarea
                rows={3}
                value={String(props.description || "")}
                onChange={(e) => handlePropChange("description", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs"
              />
            </div>
          </div>
        );

      case "tabs": {
        const tabsList = (props.tabs as any[]) || [
          { title: "مشخصات کلی", content: "توضیحات و مشخصات فنی کالا و جدول ابعاد و وزن." },
          { title: "دیدگاه خریداران", content: "نظرات ثبت‌شده کاربران و تجربیات استفاده." },
        ];
        return (
          <div className="space-y-4" data-testid="tabs-inspector-controls">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold">زبانه‌های محتوایی (Tabs)</Label>
              <button
                type="button"
                data-testid="tabs-add-tab-btn"
                onClick={() => {
                  const updated = [...tabsList, { title: `تب جدید ${tabsList.length + 1}`, content: "محتوای زبانه جدید را اینجا بنویسید." }];
                  handlePropChange("tabs", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن زبانه
              </button>
            </div>
            <div className="space-y-3">
              {tabsList.map((t, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] font-bold text-muted-foreground">زبانه {idx + 1}</span>
                    {tabsList.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = tabsList.filter((_, i) => i !== idx);
                          handlePropChange("tabs", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    data-testid={`tab-title-input-${idx}`}
                    value={t.title || ""}
                    placeholder="عنوان زبانه"
                    onChange={(e) => {
                      const updated = [...tabsList];
                      updated[idx] = { ...updated[idx], title: e.target.value };
                      handlePropChange("tabs", updated);
                    }}
                    className="h-8 text-xs"
                  />
                  <textarea
                    rows={3}
                    value={t.content || ""}
                    placeholder="محتوای متنی زبانه"
                    onChange={(e) => {
                      const updated = [...tabsList];
                      updated[idx] = { ...updated[idx], content: e.target.value };
                      handlePropChange("tabs", updated);
                    }}
                    className="w-full rounded-md border border-input bg-background p-2 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "divider": {
        const style = String(props.style || "solid");
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">نوع خط جداکننده</Label>
              <Select
                value={style}
                onValueChange={(val) => handlePropChange("style", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="solid">خط پیوسته (Solid)</SelectItem>
                  <SelectItem value="dashed">خط‌چین (Dashed)</SelectItem>
                  <SelectItem value="dotted">نقطه‌چین (Dotted)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        );
      }

      case "counter":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان شمارنده</Label>
              <Input
                data-testid="counter-title-input"
                value={String(props.title || "مشتری خوشنود")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label className="text-xs">عدد شروع</Label>
                <Input
                  type="number"
                  value={Number(props.starting_number || 0)}
                  onChange={(e) => handlePropChange("starting_number", parseInt(e.target.value, 10) || 0)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">عدد پایان</Label>
                <Input
                  data-testid="counter-ending-input"
                  type="number"
                  value={Number(props.ending_number ?? 100)}
                  onChange={(e) => handlePropChange("ending_number", parseInt(e.target.value, 10) || 0)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1.5">
                <Label className="text-xs">پیشوند</Label>
                <Input
                  value={String(props.prefix || "")}
                  onChange={(e) => handlePropChange("prefix", e.target.value)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">پسوند</Label>
                <Input
                  value={String(props.suffix || "")}
                  onChange={(e) => handlePropChange("suffix", e.target.value)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>
          </div>
        );

      case "progress_bar":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان مهارت یا پیشرفت</Label>
              <Input
                value={String(props.title || "پیشرفت سفارش‌ها")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">درصد پیشرفت (۰ تا ۱۰۰)</Label>
              <Input
                type="number"
                min={0}
                max={100}
                value={Number(props.percentage ?? 80)}
                onChange={(e) => handlePropChange("percentage", parseInt(e.target.value, 10) || 0)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش عدد درصد</Label>
              <Switch
                checked={props.show_percentage !== false}
                onCheckedChange={(val) => handlePropChange("show_percentage", val)}
              />
            </div>
          </div>
        );

      case "testimonial":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">نام مشتری / نویسنده</Label>
              <Input
                value={String(props.author || "")}
                onChange={(e) => handlePropChange("author", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">سمت یا نقش</Label>
              <Input
                value={String(props.role || "")}
                onChange={(e) => handlePropChange("role", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نام سازمان یا شرکت</Label>
              <Input
                value={String(props.company || "")}
                onChange={(e) => handlePropChange("company", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن سخن یا دیدگاه</Label>
              <textarea
                rows={4}
                value={String(props.quote || "")}
                onChange={(e) => handlePropChange("quote", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس تصویر آواتار (URL)</Label>
              <Input
                value={String(props.avatar_url || "")}
                onChange={(e) => handlePropChange("avatar_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "alert":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان اعلان</Label>
              <Input
                data-testid="alert-title-input"
                value={String(props.title || "")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن پیام</Label>
              <textarea
                data-testid="alert-description-input"
                rows={3}
                value={String(props.description || props.message || "")}
                onChange={(e) => {
                  handlePropChange("description", e.target.value);
                  handlePropChange("message", e.target.value);
                }}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نوع پیام (Alert Type)</Label>
              <Select
                value={String(props.alert_type || "info")}
                onValueChange={(val) => handlePropChange("alert_type", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="info">اطلاعیه آبی (Info)</SelectItem>
                  <SelectItem value="success">موفقیت سبز (Success)</SelectItem>
                  <SelectItem value="warning">هشدار زرد (Warning)</SelectItem>
                  <SelectItem value="danger">خطر قرمز (Danger)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        );

      case "image_box":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس تصویر (URL)</Label>
              <Input
                data-testid="image-box-url-input"
                value={String(props.image_url || "")}
                onChange={(e) => handlePropChange("image_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان جعبه تصویر</Label>
              <Input
                data-testid="image-box-title-input"
                value={String(props.title || "")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن توضیحات</Label>
              <textarea
                data-testid="image-box-desc-input"
                rows={3}
                value={String(props.description || "")}
                onChange={(e) => handlePropChange("description", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">لینک کلیک (Link URL)</Label>
              <Input
                value={String(props.link_url || "")}
                onChange={(e) => handlePropChange("link_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "toggle": {
        const items = (props.items as any[]) || [
          { title: "بخش اول", content: "محتوای بخش اول", default_open: true },
        ];
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold">بخش‌های تاگل بازشونده</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...items, { title: `بخش جدید ${items.length + 1}`, content: "محتوای پیش‌فرض", default_open: true }];
                  handlePropChange("items", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن بخش
              </button>
            </div>
            <div className="space-y-2">
              {items.map((itm, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <Input
                      data-testid={`toggle-item-title-${idx}`}
                      value={itm.title || ""}
                      placeholder="عنوان تاگل"
                      onChange={(e) => {
                        const updated = [...items];
                        updated[idx] = { ...updated[idx], title: e.target.value };
                        handlePropChange("items", updated);
                      }}
                      className="h-8 text-xs"
                    />
                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = items.filter((_, i) => i !== idx);
                          handlePropChange("items", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline ms-2"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <textarea
                    rows={2}
                    value={itm.content || ""}
                    placeholder="محتوای متنی..."
                    onChange={(e) => {
                      const updated = [...items];
                      updated[idx] = { ...updated[idx], content: e.target.value };
                      handlePropChange("items", updated);
                    }}
                    className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "hotspot": {
        const hotspots = (props.hotspots as any[]) || [
          { id: "hs_1", x: 30, y: 40, label: "۱", title: "نقطه اول", tooltip: "توضیحات" },
        ];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس تصویر (Image URL)</Label>
              <Input
                data-testid="hotspot-image-input"
                value={String(props.image_url || "")}
                onChange={(e) => handlePropChange("image_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن جایگزین (Alt)</Label>
              <Input
                value={String(props.alt || "")}
                onChange={(e) => handlePropChange("alt", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2 pt-2 border-t">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold">نقاط تعاملی (Hotspots)</Label>
                <button
                  type="button"
                  onClick={() => {
                    const updated = [...hotspots, { id: `hs_${Date.now()}`, x: 50, y: 50, label: `${hotspots.length + 1}`, title: `نقطه ${hotspots.length + 1}`, tooltip: "توضیحات این بخش" }];
                    handlePropChange("hotspots", updated);
                  }}
                  className="text-[11px] text-primary hover:underline font-semibold"
                >
                  + افزودن نقطه
                </button>
              </div>
              {hotspots.map((h, idx) => (
                <div key={idx} className="p-2.5 rounded-xl border bg-muted/20 space-y-2">
                  <div className="flex items-center justify-between gap-2">
                    <Input
                      data-testid={`hotspot-label-input-${idx}`}
                      value={h.label || ""}
                      placeholder="برچسب (۱)"
                      onChange={(e) => {
                        const updated = [...hotspots];
                        updated[idx] = { ...updated[idx], label: e.target.value };
                        handlePropChange("hotspots", updated);
                      }}
                      className="h-8 text-xs w-16 text-center font-bold"
                    />
                    <Input
                      data-testid={`hotspot-title-input-${idx}`}
                      value={h.title || ""}
                      placeholder="عنوان نقطه..."
                      onChange={(e) => {
                        const updated = [...hotspots];
                        updated[idx] = { ...updated[idx], title: e.target.value };
                        handlePropChange("hotspots", updated);
                      }}
                      className="h-8 text-xs flex-1"
                    />
                    {hotspots.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = hotspots.filter((_, i) => i !== idx);
                          handlePropChange("hotspots", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline shrink-0"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-1">
                      <Label className="text-[10px]">موقعیت افقی (X %)</Label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={h.x ?? 50}
                        onChange={(e) => {
                          const updated = [...hotspots];
                          updated[idx] = { ...updated[idx], x: parseFloat(e.target.value) || 0 };
                          handlePropChange("hotspots", updated);
                        }}
                        className="h-7 text-xs font-mono"
                        dir="ltr"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[10px]">موقعیت عمودی (Y %)</Label>
                      <Input
                        type="number"
                        min={0}
                        max={100}
                        value={h.y ?? 50}
                        onChange={(e) => {
                          const updated = [...hotspots];
                          updated[idx] = { ...updated[idx], y: parseFloat(e.target.value) || 0 };
                          handlePropChange("hotspots", updated);
                        }}
                        className="h-7 text-xs font-mono"
                        dir="ltr"
                      />
                    </div>
                  </div>
                  <Input
                    value={h.tooltip || ""}
                    placeholder="متن توضیحات در هاور..."
                    onChange={(e) => {
                      const updated = [...hotspots];
                      updated[idx] = { ...updated[idx], tooltip: e.target.value };
                      handlePropChange("hotspots", updated);
                    }}
                    className="h-7 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "call_to_action":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">برچسب بالای بنر (Badge)</Label>
              <Input
                value={String(props.badge || "")}
                onChange={(e) => handlePropChange("badge", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان فراخوان</Label>
              <Input
                value={String(props.title || "")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن توضیحات</Label>
              <textarea
                rows={3}
                value={String(props.description || "")}
                onChange={(e) => handlePropChange("description", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن روی دکمه</Label>
              <Input
                value={String(props.button_label || "شروع کنید")}
                onChange={(e) => handlePropChange("button_label", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیوند دکمه (URL)</Label>
              <Input
                value={String(props.button_url || "/products")}
                onChange={(e) => handlePropChange("button_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "animated_headline":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن پیشین (Before Text)</Label>
              <Input
                value={String(props.before_text || "")}
                onChange={(e) => handlePropChange("before_text", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن برجسته / متحرک</Label>
              <Input
                value={String(props.highlighted_text || "")}
                onChange={(e) => handlePropChange("highlighted_text", e.target.value)}
                className="h-8 text-xs font-bold text-primary"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن پسین (After Text)</Label>
              <Input
                value={String(props.after_text || "")}
                onChange={(e) => handlePropChange("after_text", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "flip_box":
        return (
          <div className="space-y-4">
            <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
              <span className="text-xs font-bold block">تنظیمات روی کارت (Front)</span>
              <div className="space-y-1">
                <Label className="text-[10px]">عنوان جلو</Label>
                <Input
                  value={String(props.front_title || "")}
                  onChange={(e) => handlePropChange("front_title", e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px]">توضیحات جلو</Label>
                <Input
                  value={String(props.front_desc || "")}
                  onChange={(e) => handlePropChange("front_desc", e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
            </div>

            <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
              <span className="text-xs font-bold block">تنظیمات پشت کارت (Back)</span>
              <div className="space-y-1">
                <Label className="text-[10px]">عنوان پشت</Label>
                <Input
                  value={String(props.back_title || "")}
                  onChange={(e) => handlePropChange("back_title", e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px]">توضیحات پشت</Label>
                <Input
                  value={String(props.back_desc || "")}
                  onChange={(e) => handlePropChange("back_desc", e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[10px]">متن دکمه</Label>
                <Input
                  value={String(props.button_text || "")}
                  onChange={(e) => handlePropChange("button_text", e.target.value)}
                  className="h-7 text-xs"
                />
              </div>
            </div>
          </div>
        );

      case "social_links": {
        const links = (props.links as any[]) || [
          { platform: "اینستاگرام", url: "https://instagram.com" },
          { platform: "تلگرام", url: "https://t.me" },
        ];
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold">لینک‌های شبکه‌های اجتماعی</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...links, { platform: "واتساپ", url: "https://wa.me" }];
                  handlePropChange("links", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن شبکه
              </button>
            </div>
            <div className="space-y-2">
              {links.map((link, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
                  <div className="flex items-center justify-between">
                    <Input
                      value={link.platform || ""}
                      placeholder="نام پلتفرم"
                      onChange={(e) => {
                        const updated = [...links];
                        updated[idx] = { ...updated[idx], platform: e.target.value };
                        handlePropChange("links", updated);
                      }}
                      className="h-8 text-xs w-28"
                    />
                    {links.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = links.filter((_, i) => i !== idx);
                          handlePropChange("links", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    value={link.url || ""}
                    placeholder="https://..."
                    onChange={(e) => {
                      const updated = [...links];
                      updated[idx] = { ...updated[idx], url: e.target.value };
                      handlePropChange("links", updated);
                    }}
                    className="h-8 text-xs font-mono"
                    dir="ltr"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "image_gallery": {
        const images = (props.images as any[]) || [
          { url: "/placeholder-hero.svg", alt: "تصویر ۱" },
          { url: "/placeholder.svg", alt: "تصویر ۲" },
        ];
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold">تصاویر گالری</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...images, { url: "/placeholder.svg", alt: `تصویر ${images.length + 1}` }];
                  handlePropChange("images", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن تصویر
              </button>
            </div>
            <div className="space-y-2">
              {images.map((img, idx) => (
                <div key={idx} className="p-2 rounded-lg border bg-muted/20 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground font-semibold">تصویر {idx + 1}</span>
                    {images.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = images.filter((_, i) => i !== idx);
                          handlePropChange("images", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    value={img.url || ""}
                    placeholder="/path/to/image.jpg"
                    onChange={(e) => {
                      const updated = [...images];
                      updated[idx] = { ...updated[idx], url: e.target.value };
                      handlePropChange("images", updated);
                    }}
                    className="h-7 text-xs font-mono"
                    dir="ltr"
                  />
                  <Input
                    value={img.alt || ""}
                    placeholder="متن جایگزین (Alt)"
                    onChange={(e) => {
                      const updated = [...images];
                      updated[idx] = { ...updated[idx], alt: e.target.value };
                      handlePropChange("images", updated);
                    }}
                    className="h-7 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "blockquote":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">متن نقل‌قول</Label>
              <textarea
                data-testid="blockquote-text-input"
                rows={4}
                value={String(props.text || "")}
                onChange={(e) => handlePropChange("text", e.target.value)}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نویسنده یا مرجع سخن</Label>
              <Input
                data-testid="blockquote-author-input"
                value={String(props.author || "")}
                onChange={(e) => handlePropChange("author", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "share_buttons":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان یا متن اشتراک‌گذاری</Label>
              <Input
                data-testid="share-buttons-title-input"
                value={String(props.title || props.share_text || "")}
                onChange={(e) => {
                  handlePropChange("title", e.target.value);
                  handlePropChange("share_text", e.target.value);
                }}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "image_carousel": {
        const images = (props.images as any[]) || [];
        return (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-xs font-bold">تصاویر اسلایدر</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...images, { url: "/placeholder-hero.svg", alt: `اسلاید ${images.length + 1}` }];
                  handlePropChange("images", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن اسلاید
              </button>
            </div>
            <div className="space-y-2">
              {images.map((img, idx) => (
                <div key={idx} className="p-2 rounded-lg border bg-muted/20 flex items-center gap-2">
                  <Input
                    value={img.url || ""}
                    placeholder="URL اسلاید"
                    onChange={(e) => {
                      const updated = [...images];
                      updated[idx] = { ...updated[idx], url: e.target.value };
                      handlePropChange("images", updated);
                    }}
                    className="h-7 text-xs font-mono flex-1"
                    dir="ltr"
                  />
                  {images.length > 1 && (
                    <button
                      type="button"
                      onClick={() => {
                        const updated = images.filter((_, i) => i !== idx);
                        handlePropChange("images", updated);
                      }}
                      className="text-xs text-destructive hover:underline px-1"
                    >
                      حذف
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "table_of_contents": {
        const rawHeadings = Array.isArray(props.headings) ? props.headings : [];
        const rawItems = Array.isArray(props.items) ? props.items.map((it: any) => (typeof it === "string" ? it : it.title || it.text || "")) : [];
        const headings = rawHeadings.length > 0 ? rawHeadings : (rawItems.length > 0 ? rawItems : ["مقدمه", "ویژگی‌ها", "پرسش‌های متداول"]);
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان فهرست محتوا</Label>
              <Input
                data-testid="toc-title-input"
                value={String(props.title || "فهرست عناوین برگه")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold">عناوین فهرست</Label>
                <button
                  type="button"
                  onClick={() => {
                    const updated = [...headings, `عنوان جدید ${headings.length + 1}`];
                    handlePropChange("headings", updated);
                  }}
                  className="text-[11px] text-primary hover:underline font-semibold"
                >
                  + افزودن سرفصل
                </button>
              </div>
              <div className="space-y-1.5">
                {headings.map((h: string, idx: number) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Input
                      data-testid={`toc-item-title-${idx}`}
                      value={h}
                      onChange={(e) => {
                        const updated = [...headings];
                        updated[idx] = e.target.value;
                        handlePropChange("headings", updated);
                      }}
                      className="h-7 text-xs flex-1"
                    />
                    {headings.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = headings.filter((_: any, i: number) => i !== idx);
                          handlePropChange("headings", updated);
                        }}
                        className="text-xs text-destructive hover:underline px-1"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">شماره‌گذاری ترتیبی (۱، ۲، ۳...)</Label>
              <Switch
                checked={props.ordered !== false}
                onCheckedChange={(val) => handlePropChange("ordered", val)}
              />
            </div>
          </div>
        );
      }

      case "progress_tracker":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">درصد پیش‌نمایش (۰ تا ۱۰۰)</Label>
              <Input
                data-testid="progress-tracker-pct-input"
                type="number"
                min={0}
                max={100}
                value={Number(props.percentage ?? 60)}
                onChange={(e) => handlePropChange("percentage", parseInt(e.target.value, 10) || 0)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "lottie":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">آدرس منبع انیمیشن (JSON URL)</Label>
              <Input
                data-testid="lottie-url-input"
                value={String(props.source_url || "")}
                onChange={(e) => handlePropChange("source_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>تکرار پیوسته (Loop)</span>
              <Switch
                checked={props.loop !== false}
                onCheckedChange={(val) => handlePropChange("loop", val)}
              />
            </div>
          </div>
        );

      case "floating_bar":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">شماره تماس پشتیبانی</Label>
              <Input
                data-testid="floating-bar-phone-input"
                value={String(props.phone || "")}
                onChange={(e) => handlePropChange("phone", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیام ترغیب‌کننده</Label>
              <Input
                value={String(props.message || "")}
                onChange={(e) => handlePropChange("message", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن دکمه تماس</Label>
              <Input
                value={String(props.button_text || "تماس فوری")}
                onChange={(e) => handlePropChange("button_text", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );

      case "off_canvas":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">موقعیت باز شدن کشو</Label>
              <Select
                value={String(props.position || "right")}
                onValueChange={(val) => handlePropChange("position", val)}
              >
                <SelectTrigger data-testid="offcanvas-position-select" className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="right">راست (Right - پیش‌فرض RTL)</SelectItem>
                  <SelectItem value="left">چپ (Left)</SelectItem>
                  <SelectItem value="top">بالا (Top)</SelectItem>
                  <SelectItem value="bottom">پایین (Bottom)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">عرض کشو (پیکسل)</Label>
              <Input
                type="number"
                min={200}
                max={800}
                value={Number(props.width || 340)}
                onChange={(e) => handlePropChange("width", parseInt(e.target.value, 10) || 340)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "popup_builder":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">محرک نمایش (Trigger)</Label>
              <Select
                value={String(props.trigger || "on_scroll")}
                onValueChange={(val) => handlePropChange("trigger", val)}
              >
                <SelectTrigger data-testid="popup-trigger-select" className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="on_scroll">هنگام اسکرول به درصد معین</SelectItem>
                  <SelectItem value="on_load">بلافاصله پس از بارگذاری برگه</SelectItem>
                  <SelectItem value="exit_intent">هنگام خروج ماوس از صفحه</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">درصد اسکرول تریگر</Label>
              <Input
                type="number"
                min={10}
                max={90}
                value={Number(props.scroll_percentage || 50)}
                onChange={(e) => handlePropChange("scroll_percentage", parseInt(e.target.value, 10) || 50)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "loop_grid":
      case "loop_carousel":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">منبع داده حلقه (Data Source)</Label>
              <Select
                value={String(props.source || "products")}
                onValueChange={(val) => handlePropChange("source", val)}
              >
                <SelectTrigger data-testid="loop-source-select" className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="products">محصولات فروشگاه</SelectItem>
                  <SelectItem value="posts">مقالات وبلاگ</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">حداکثر تعداد نمایش</Label>
              <Input
                data-testid="loop-limit-input"
                type="number"
                min={1}
                max={24}
                value={Number(props.limit || 6)}
                onChange={(e) => handlePropChange("limit", parseInt(e.target.value, 10) || 6)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "multi_step_form":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">مرحله جاری پیش‌نمایش</Label>
              <Input
                data-testid="step-form-cur-input"
                type="number"
                min={1}
                max={3}
                value={Number(props.current_step || 1)}
                onChange={(e) => handlePropChange("current_step", parseInt(e.target.value, 10) || 1)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        );

      case "slides": {
        const slidesList = (props.slides as any[]) || [];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان اسلاید اول</Label>
              <Input
                data-testid="slides-title-input"
                value={String(slidesList[0]?.title || "")}
                onChange={(e) => {
                  const updated = [...slidesList];
                  updated[0] = { ...(updated[0] || {}), title: e.target.value };
                  handlePropChange("slides", updated);
                }}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن توضیحات اسلاید</Label>
              <textarea
                data-testid="slides-desc-input"
                rows={3}
                value={String(slidesList[0]?.description || "")}
                onChange={(e) => {
                  const updated = [...slidesList];
                  updated[0] = { ...(updated[0] || {}), description: e.target.value };
                  handlePropChange("slides", updated);
                }}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">متن دکمه اسلاید</Label>
              <Input
                value={String(slidesList[0]?.button_text || "")}
                onChange={(e) => {
                  const updated = [...slidesList];
                  updated[0] = { ...(updated[0] || {}), button_text: e.target.value };
                  handlePropChange("slides", updated);
                }}
                className="h-8 text-xs"
              />
            </div>
          </div>
        );
      }

      case "code_highlight":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان یا نام فایل</Label>
              <Input
                data-testid="code-title-input"
                value={String(props.title || "")}
                placeholder="مثلاً index.ts یا script.py"
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">زبان برنامه‌نویسی (Language)</Label>
              <Select
                value={String(props.language || "javascript")}
                onValueChange={(val) => handlePropChange("language", val)}
              >
                <SelectTrigger data-testid="code-lang-select" className="h-8 text-xs font-mono" dir="ltr">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent dir="ltr">
                  <SelectItem value="javascript">JavaScript / Node.js</SelectItem>
                  <SelectItem value="typescript">TypeScript</SelectItem>
                  <SelectItem value="python">Python</SelectItem>
                  <SelectItem value="html">HTML</SelectItem>
                  <SelectItem value="css">CSS / Tailwind</SelectItem>
                  <SelectItem value="json">JSON</SelectItem>
                  <SelectItem value="sql">SQL / PostgreSQL</SelectItem>
                  <SelectItem value="bash">Bash / Shell</SelectItem>
                  <SelectItem value="php">PHP</SelectItem>
                  <SelectItem value="rust">Rust</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">محتوای کد منبع</Label>
              <Textarea
                data-testid="code-content-textarea"
                value={String(props.code || "")}
                onChange={(e) => handlePropChange("code", e.target.value)}
                className="font-mono text-xs leading-relaxed min-h-[120px] bg-muted/40"
                dir="ltr"
                placeholder="کد خود را اینجا وارد کنید..."
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">نمایش شماره خطوط (Line Numbers)</Label>
              <Switch
                data-testid="code-linenumbers-switch"
                checked={props.line_numbers !== false}
                onCheckedChange={(val) => handlePropChange("line_numbers", val)}
              />
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">دکمه کپی در کلیپ‌بورد</Label>
              <Switch
                data-testid="code-copybtn-switch"
                checked={props.copy_to_clipboard !== false}
                onCheckedChange={(val) => handlePropChange("copy_to_clipboard", val)}
              />
            </div>
          </div>
        );

      case "nested_tabs":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عناوین تب‌های تودرتو (هر خط یک عنوان)</Label>
              <textarea
                data-testid="nested-tabs-titles-input"
                rows={3}
                value={Array.isArray(props.tab_titles) ? props.tab_titles.join("\n") : ""}
                onChange={(e) => handlePropChange("tab_titles", e.target.value.split("\n").filter(Boolean))}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
          </div>
        );

      case "nested_accordion":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عناوین بخش‌های آکاردئون (هر خط یک بخش)</Label>
              <textarea
                data-testid="nested-accordion-titles-input"
                rows={3}
                value={Array.isArray(props.item_titles) ? props.item_titles.join("\n") : ""}
                onChange={(e) => handlePropChange("item_titles", e.target.value.split("\n").filter(Boolean))}
                className="w-full rounded-md border border-input bg-background p-2 text-xs leading-relaxed"
              />
            </div>
          </div>
        );

      case "icon":
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">انتخاب آیکون</Label>
              <Select
                value={String(props.icon || "star")}
                onValueChange={(val) => handlePropChange("icon", val)}
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="max-h-56">
                  {BUILDER_ICON_OPTIONS.map((opt) => (
                    <SelectItem key={opt.id} value={opt.id} className="text-xs">
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نمای آیکون (View)</Label>
              <Select
                value={String(props.view || "default")}
                onValueChange={(val) => handlePropChange("view", val)}
              >
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="default">پیش‌فرض (ساده)</SelectItem>
                  <SelectItem value="stacked">پشته‌ای / پرشده (Stacked)</SelectItem>
                  <SelectItem value="framed">کادردار (Framed)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {Boolean(props.view && props.view !== "default") && (
              <div className="space-y-1.5">
                <Label className="text-xs">شکل کادر (Shape)</Label>
                <Select
                  value={String(props.shape || "circle")}
                  onValueChange={(val) => handlePropChange("shape", val)}
                >
                  <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="circle">دایره (Circle)</SelectItem>
                    <SelectItem value="square">مربع / گوشه‌گرد (Square)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="space-y-1.5">
              <Label className="text-xs">اندازه آیکون (پیکسل)</Label>
              <Input
                type="number"
                min={12}
                max={128}
                value={Number(props.size) || 32}
                onChange={(e) => handlePropChange("size", parseInt(e.target.value) || 32)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">زاویه چرخش (درجه)</Label>
              <Input
                type="number"
                min={0}
                max={360}
                value={Number(props.rotate) || 0}
                onChange={(e) => handlePropChange("rotate", parseInt(e.target.value) || 0)}
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

      case "icon_list": {
        const rawItems = Array.isArray(props.items) ? (props.items as any[]) : [];
        const items = rawItems.length > 0 ? rawItems : [
          { text: "ارسال سریع برای خریدهای بالای ۵۰۰ هزار تومان", icon: "truck", url: "" },
          { text: "ضمانت بازگشت وجه تا ۷ روز کاری", icon: "shield-check", url: "" },
          { text: "پشتیبانی ۲۴ ساعته در تمام روزهای هفته", icon: "headphones", url: "" },
        ];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">چیدمان فهرست</Label>
              <Select
                value={String(props.layout || "vertical")}
                onValueChange={(val) => handlePropChange("layout", val)}
              >
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="vertical">عمودی (Vertical)</SelectItem>
                  <SelectItem value="horizontal">افقی (Horizontal)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs font-bold">آیتم‌های فهرست</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...items, { text: `مورد جدید ${items.length + 1}`, icon: "check", url: "" }];
                  handlePropChange("items", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن آیتم
              </button>
            </div>
            <div className="space-y-2">
              {items.map((it, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
                  <div className="flex items-center gap-2">
                    <Select
                      value={String(it.icon || "check")}
                      onValueChange={(val) => {
                        const updated = [...items];
                        updated[idx] = { ...updated[idx], icon: val };
                        handlePropChange("items", updated);
                      }}
                    >
                      <SelectTrigger className="h-7 text-xs w-28 shrink-0"><SelectValue /></SelectTrigger>
                      <SelectContent className="max-h-56">
                        {BUILDER_ICON_OPTIONS.map((opt) => (
                          <SelectItem key={opt.id} value={opt.id} className="text-xs">
                            {opt.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      data-testid={`icon-list-item-text-${idx}`}
                      value={it.text || ""}
                      placeholder="متن آیتم"
                      onChange={(e) => {
                        const updated = [...items];
                        updated[idx] = { ...updated[idx], text: e.target.value };
                        handlePropChange("items", updated);
                      }}
                      className="h-7 text-xs flex-1"
                    />
                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = items.filter((_, i) => i !== idx);
                          handlePropChange("items", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    value={it.url || ""}
                    placeholder="پیوند اختیاری (https://...)"
                    onChange={(e) => {
                      const updated = [...items];
                      updated[idx] = { ...updated[idx], url: e.target.value };
                      handlePropChange("items", updated);
                    }}
                    className="h-7 text-xs font-mono"
                    dir="ltr"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "price_table": {
        const features = Array.isArray(props.features) ? (props.features as any[]) : [
          { text: "دسترسی نامحدود به تمامی امکانات", available: true },
          { text: "پشتیبانی اختصاصی تلفنی و تیکتی", available: true },
          { text: "فضای ابری ۵۰ گیگابایت امن", available: true },
          { text: "دامنه اختصاصی رایگان ۱ ساله", available: false },
        ];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان پلن</Label>
              <Input
                value={String(props.title || "پلن استاندارد")}
                onChange={(e) => handlePropChange("title", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">توضیح کوتاه زیر عنوان</Label>
              <Input
                value={String(props.subtitle || "")}
                onChange={(e) => handlePropChange("subtitle", e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">قیمت</Label>
                <Input
                  value={String(props.price || "۴۹۰,۰۰۰")}
                  onChange={(e) => handlePropChange("price", e.target.value)}
                  className="h-8 text-xs font-mono"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">واحد پول</Label>
                <Input
                  value={String(props.currency || "تومان")}
                  onChange={(e) => handlePropChange("currency", e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">دوره پرداخت</Label>
                <Input
                  value={String(props.period || "ماهانه")}
                  onChange={(e) => handlePropChange("period", e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">نشان ویژه (Badge)</Label>
                <Input
                  value={String(props.badge || "")}
                  onChange={(e) => handlePropChange("badge", e.target.value)}
                  className="h-8 text-xs"
                  placeholder="مثال: پرفروش‌ترین"
                />
              </div>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs">پلن برجسته / ویژه</Label>
              <Switch
                checked={Boolean(props.is_featured)}
                onCheckedChange={(val) => handlePropChange("is_featured", val)}
              />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-xs">متن دکمه</Label>
                <Input
                  value={String(props.button_label || "انتخاب و شروع پلن")}
                  onChange={(e) => handlePropChange("button_label", e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">لینک دکمه</Label>
                <Input
                  value={String(props.button_url || "/checkout")}
                  onChange={(e) => handlePropChange("button_url", e.target.value)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>
            <div className="space-y-2 pt-2 border-t">
              <div className="flex items-center justify-between">
                <Label className="text-xs font-bold">ویژگی‌های پلن</Label>
                <button
                  type="button"
                  onClick={() => {
                    const updated = [...features, { text: `امکان جدید ${features.length + 1}`, available: true }];
                    handlePropChange("features", updated);
                  }}
                  className="text-[11px] text-primary hover:underline font-semibold"
                >
                  + افزودن ویژگی
                </button>
              </div>
              {features.map((feat, idx) => (
                <div key={idx} className="flex items-center gap-2 p-1.5 rounded-lg border bg-muted/20">
                  <Switch
                    checked={feat.available !== false}
                    onCheckedChange={(val) => {
                      const updated = [...features];
                      updated[idx] = { ...updated[idx], available: val };
                      handlePropChange("features", updated);
                    }}
                  />
                  <Input
                    value={feat.text || ""}
                    onChange={(e) => {
                      const updated = [...features];
                      updated[idx] = { ...updated[idx], text: e.target.value };
                      handlePropChange("features", updated);
                    }}
                    className="h-7 text-xs flex-1"
                  />
                  {features.length > 1 && (
                    <button
                      type="button"
                      onClick={() => {
                        const updated = features.filter((_, i) => i !== idx);
                        handlePropChange("features", updated);
                      }}
                      className="text-[10px] text-destructive hover:underline"
                    >
                      حذف
                    </button>
                  )}
                </div>
              ))}
            </div>
          </div>
        );
      }

      case "price_list": {
        const rawItems = Array.isArray(props.items) ? (props.items as any[]) : [];
        const items = rawItems.length > 0 ? rawItems : [
          { title: "مشاوره اختصاصی کسب‌وکار", description: "جلسه ۱ ساعته تحلیل استراتژیک", price: "۳۵۰,۰۰۰ تومان", url: "" },
          { title: "طراحی هویت بصری و لوگو", description: "شامل فایل‌های وکتور و راهنمای رنگ", price: "۱,۲۰۰,۰۰۰ تومان", url: "" },
          { title: "سئو و بهینه‌سازی فنی سایت", description: "گزارش جامع کلمات کلیدی و ممیزی", price: "۸۵۰,۰۰۰ تومان", url: "" },
        ];
        return (
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label className="text-xs">استایل جداکننده قیمت</Label>
              <Select
                value={String(props.separator_style || "dotted")}
                onValueChange={(val) => handlePropChange("separator_style", val)}
              >
                <SelectTrigger className="h-8 text-xs"><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="dotted">نقطه‌چین (Dotted)</SelectItem>
                  <SelectItem value="dashed">خط‌چین (Dashed)</SelectItem>
                  <SelectItem value="solid">خط پیوسته (Solid)</SelectItem>
                  <SelectItem value="none">بدون خط (None)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-xs font-bold">آیتم‌های منو و قیمت</Label>
              <button
                type="button"
                onClick={() => {
                  const updated = [...items, { title: "خدمت جدید", description: "", price: "۱۰۰,۰۰۰ تومان", url: "" }];
                  handlePropChange("items", updated);
                }}
                className="text-[11px] text-primary hover:underline font-semibold"
              >
                + افزودن آیتم
              </button>
            </div>
            <div className="space-y-2">
              {items.map((it, idx) => (
                <div key={idx} className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
                  <div className="flex items-center gap-2">
                    <Input
                      value={it.title || ""}
                      placeholder="عنوان خدمت"
                      onChange={(e) => {
                        const updated = [...items];
                        updated[idx] = { ...updated[idx], title: e.target.value };
                        handlePropChange("items", updated);
                      }}
                      className="h-7 text-xs flex-1 font-semibold"
                    />
                    <Input
                      value={it.price || ""}
                      placeholder="قیمت"
                      onChange={(e) => {
                        const updated = [...items];
                        updated[idx] = { ...updated[idx], price: e.target.value };
                        handlePropChange("items", updated);
                      }}
                      className="h-7 text-xs w-28 font-mono"
                    />
                    {items.length > 1 && (
                      <button
                        type="button"
                        onClick={() => {
                          const updated = items.filter((_, i) => i !== idx);
                          handlePropChange("items", updated);
                        }}
                        className="text-[10px] text-destructive hover:underline"
                      >
                        حذف
                      </button>
                    )}
                  </div>
                  <Input
                    value={it.description || ""}
                    placeholder="توضیحات کوتاه اختیاری"
                    onChange={(e) => {
                      const updated = [...items];
                      updated[idx] = { ...updated[idx], description: e.target.value };
                      handlePropChange("items", updated);
                    }}
                    className="h-7 text-xs"
                  />
                </div>
              ))}
            </div>
          </div>
        );
      }

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
                data-testid="padding-top-input"
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
          {/* Quick Spacing Scale Chips */}
          <div className="flex flex-wrap gap-1 mt-1">
            <span className="text-[10px] text-muted-foreground me-1 self-center">مقیاس پدینگ:</span>
            {[
              { label: "۶۴ پیکسل (سکشن)", val: 64 },
              { label: "۳۲ پیکسل (بزرگ)", val: 32 },
              { label: "۱۶ پیکسل (پایه)", val: 16 },
              { label: "۸ پیکسل (کوچک)", val: 8 },
              { label: "صفر", val: 0 },
            ].map((sp) => (
              <button
                key={sp.label}
                type="button"
                onClick={() => {
                  handleDeviceStyleChange({
                    padding: {
                      top: { value: sp.val, unit: "px" },
                      right: { value: sp.val, unit: "px" },
                      bottom: { value: sp.val, unit: "px" },
                      left: { value: sp.val, unit: "px" },
                      isLinked: true,
                    },
                  });
                }}
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {sp.label}
              </button>
            ))}
          </div>
        </div>

        {/* Width & Layout Dimensions Tokens */}
        <div className="space-y-1.5 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">عرض و محدوده عنصر (Width)</Label>
          <div className="flex items-center gap-2">
            <Input
              value={currentDeviceStyle.width ? `${currentDeviceStyle.width.value}${currentDeviceStyle.width.unit}` : ""}
              placeholder="100% یا 1280px / خودکار"
              onChange={(e) => {
                const raw = e.target.value.trim();
                if (!raw || raw === "auto") {
                  handleDeviceStyleChange({ width: undefined });
                  return;
                }
                if (raw.endsWith("%")) {
                  handleDeviceStyleChange({ width: { value: parseFloat(raw) || 100, unit: "%" } });
                } else if (raw.endsWith("px")) {
                  handleDeviceStyleChange({ width: { value: parseFloat(raw) || 0, unit: "px" } });
                } else {
                  const val = parseFloat(raw);
                  if (!isNaN(val)) {
                    handleDeviceStyleChange({ width: { value: val, unit: "px" } });
                  }
                }
              }}
              className="h-8 text-xs flex-1 font-mono"
              dir="ltr"
            />
          </div>
          <div className="flex flex-wrap gap-1 mt-1">
            <span className="text-[10px] text-muted-foreground me-1 self-center">توکن‌های عرض:</span>
            {[
              { label: "خودکار (Auto)", w: undefined },
              { label: "۱۰۰٪", w: { value: 100, unit: "%" as UnitType } },
              { label: "۱۲۸۰ پیکسل (کانتینر)", w: { value: 1280, unit: "px" as UnitType } },
              { label: "۷۶۸ پیکسل (محتوا)", w: { value: 768, unit: "px" as UnitType } },
            ].map((wt) => (
              <button
                key={wt.label}
                type="button"
                onClick={() => handleDeviceStyleChange({ width: wt.w })}
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {wt.label}
              </button>
            ))}
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

        {/* Professional Background Group Controls (Elementor Parity) */}
        <div className="space-y-3 pt-2 border-t">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">پس‌زمینه (Background - المنتور)</Label>
            <div className="flex gap-1 text-[10px] bg-muted/60 p-0.5 rounded-md border border-border/60">
              {[
                { id: "color", label: "تک‌رنگ" },
                { id: "gradient", label: "گرادیانت" },
                { id: "image", label: "تصویر" },
                { id: "none", label: "هیچ" },
              ].map((bgType) => {
                const active = (currentDeviceStyle.background?.type || "color") === bgType.id;
                return (
                  <button
                    key={bgType.id}
                    type="button"
                    onClick={() => {
                      const existingGrad = currentDeviceStyle.background?.gradient;
                      const existingImg = currentDeviceStyle.background?.imageUrl;
                      handleDeviceStyleChange({
                        background: {
                          ...currentDeviceStyle.background,
                          type: bgType.id as any,
                          gradient: bgType.id === "gradient" ? (existingGrad || {
                            direction: "to-r",
                            fromColor: "#10b981",
                            toColor: "#3b82f6",
                          }) : existingGrad,
                          imageUrl: bgType.id === "image" ? (existingImg || "/placeholder-hero.svg") : existingImg,
                        },
                      });
                    }}
                    className={cn(
                      "px-2 py-0.5 rounded transition",
                      active ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {bgType.label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Color Mode */}
          {(!currentDeviceStyle.background?.type || currentDeviceStyle.background.type === "color") && (
            <div className="space-y-1.5">
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={toValidHexColor(currentDeviceStyle.background?.color, "#ffffff")}
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
                  placeholder="#ffffff یا hsl(var(--primary))"
                  onChange={(e) =>
                    handleDeviceStyleChange({
                      background: {
                        type: "color",
                        color: normalizeCssColor(e.target.value) || e.target.value,
                      },
                    })
                  }
                  className="h-8 text-xs flex-1 font-mono"
                  dir="ltr"
                />
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {[
                  { label: "رنگ اصلی", val: "var(--primary)" },
                  { label: "رنگ ثانویه", val: "var(--secondary)" },
                  { label: "سطح / کارت", val: "var(--card)" },
                  { label: "ملایم (Muted)", val: "var(--muted)" },
                  { label: "پس‌زمینه", val: "var(--background)" },
                ].map((tok) => (
                  <button
                    key={tok.val}
                    type="button"
                    onClick={() =>
                      handleDeviceStyleChange({
                        background: {
                          type: "color",
                          color: tok.val,
                        },
                      })
                    }
                    className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
                  >
                    {tok.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Gradient Mode */}
          {currentDeviceStyle.background?.type === "gradient" && (
            <div className="space-y-2 p-2.5 rounded-lg border bg-muted/20">
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">رنگ شروع</Label>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="color"
                      value={toValidHexColor(currentDeviceStyle.background?.gradient?.fromColor, "#10b981")}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: e.target.value,
                              toColor: currentDeviceStyle.background?.gradient?.toColor || "#3b82f6",
                            },
                          },
                        })
                      }
                      className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
                    />
                    <Input
                      value={currentDeviceStyle.background?.gradient?.fromColor || "#10b981"}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: e.target.value,
                              toColor: currentDeviceStyle.background?.gradient?.toColor || "#3b82f6",
                            },
                          },
                        })
                      }
                      className="h-7 text-[11px] font-mono"
                      dir="ltr"
                    />
                  </div>
                </div>

                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">رنگ پایان</Label>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="color"
                      value={toValidHexColor(currentDeviceStyle.background?.gradient?.toColor, "#3b82f6")}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: currentDeviceStyle.background?.gradient?.fromColor || "#10b981",
                              toColor: e.target.value,
                            },
                          },
                        })
                      }
                      className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
                    />
                    <Input
                      value={currentDeviceStyle.background?.gradient?.toColor || "#3b82f6"}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: currentDeviceStyle.background?.gradient?.fromColor || "#10b981",
                              toColor: e.target.value,
                            },
                          },
                        })
                      }
                      className="h-7 text-[11px] font-mono"
                      dir="ltr"
                    />
                  </div>
                </div>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">جهت گرادیانت</Label>
                <Select
                  value={currentDeviceStyle.background?.gradient?.direction || "to-r"}
                  onValueChange={(dir: any) =>
                    handleDeviceStyleChange({
                      background: {
                        type: "gradient",
                        gradient: {
                          direction: dir,
                          fromColor: currentDeviceStyle.background?.gradient?.fromColor || "#10b981",
                          toColor: currentDeviceStyle.background?.gradient?.toColor || "#3b82f6",
                        },
                      },
                    })
                  }
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="to-r">افقی به راست (to right)</SelectItem>
                    <SelectItem value="to-l">افقی به چپ (to left)</SelectItem>
                    <SelectItem value="to-b">عمودی به پایین (to bottom)</SelectItem>
                    <SelectItem value="to-t">عمودی به بالا (to top)</SelectItem>
                    <SelectItem value="to-tr">مورب به گوشه بالا راست (to top right)</SelectItem>
                    <SelectItem value="to-tl">مورب به گوشه بالا چپ (to top left)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          )}

          {/* Image Mode */}
          {currentDeviceStyle.background?.type === "image" && (
            <div className="space-y-2 p-2.5 rounded-lg border bg-muted/20">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">آدرس تصویر پس‌زمینه (URL)</Label>
                <Input
                  value={currentDeviceStyle.background?.imageUrl || ""}
                  placeholder="https://... یا /image.png"
                  onChange={(e) =>
                    handleDeviceStyleChange({
                      background: {
                        type: "image",
                        imageUrl: e.target.value.trim(),
                        position: currentDeviceStyle.background?.position || "center",
                        size: currentDeviceStyle.background?.size || "cover",
                      },
                    })
                  }
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">موقعیت تصویر</Label>
                  <Select
                    value={currentDeviceStyle.background?.position || "center"}
                    onValueChange={(pos: any) =>
                      handleDeviceStyleChange({
                        background: {
                          type: "image",
                          imageUrl: currentDeviceStyle.background?.imageUrl || "",
                          position: pos,
                          size: currentDeviceStyle.background?.size || "cover",
                        },
                      })
                    }
                  >
                    <SelectTrigger className="h-7 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="center">مرکز (Center)</SelectItem>
                      <SelectItem value="top">بالا (Top)</SelectItem>
                      <SelectItem value="bottom">پایین (Bottom)</SelectItem>
                      <SelectItem value="left">چپ (Left)</SelectItem>
                      <SelectItem value="right">راست (Right)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">اندازه پوشش</Label>
                  <Select
                    value={currentDeviceStyle.background?.size || "cover"}
                    onValueChange={(sz: any) =>
                      handleDeviceStyleChange({
                        background: {
                          type: "image",
                          imageUrl: currentDeviceStyle.background?.imageUrl || "",
                          position: currentDeviceStyle.background?.position || "center",
                          size: sz,
                        },
                      })
                    }
                  >
                    <SelectTrigger className="h-7 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="cover">پوشش کامل (Cover)</SelectItem>
                      <SelectItem value="contain">دربرگیرنده (Contain)</SelectItem>
                      <SelectItem value="auto">اندازه اصلی (Auto)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}

          {/* Background Overlay Controls (Elementor Parity) */}
          <div className="space-y-2 pt-2 border-t border-border/50">
            <div className="flex items-center justify-between">
              <Label className="text-[11px] font-bold text-foreground">لایه رویی پس‌زمینه (Background Overlay)</Label>
              <div className="flex gap-1 text-[9px] bg-muted/60 p-0.5 rounded border border-border/60">
                {[
                  { id: "none", label: "هیچ" },
                  { id: "color", label: "رنگ" },
                  { id: "gradient", label: "گرادیانت" },
                ].map((ovType) => {
                  const active = (currentDeviceStyle.backgroundOverlay?.type || "none") === ovType.id;
                  return (
                    <button
                      key={ovType.id}
                      type="button"
                      data-testid={`overlay-type-${ovType.id}`}
                      onClick={() =>
                        handleDeviceStyleChange({
                          backgroundOverlay: {
                            ...currentDeviceStyle.backgroundOverlay,
                            type: ovType.id as any,
                            color: ovType.id === "color" ? (currentDeviceStyle.backgroundOverlay?.color || "rgba(0,0,0,0.5)") : undefined,
                            opacity: currentDeviceStyle.backgroundOverlay?.opacity ?? 0.5,
                          },
                        })
                      }
                      className={cn(
                        "px-1.5 py-0.5 rounded transition",
                        active ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground hover:text-foreground"
                      )}
                    >
                      {ovType.label}
                    </button>
                  );
                })}
              </div>
            </div>

            {currentDeviceStyle.backgroundOverlay && currentDeviceStyle.backgroundOverlay.type !== "none" && (
              <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
                {currentDeviceStyle.backgroundOverlay.type === "color" && (
                  <div className="flex items-center gap-2">
                    <input
                      type="color"
                      value={toValidHexColor(currentDeviceStyle.backgroundOverlay.color, "#000000")}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          backgroundOverlay: {
                            ...currentDeviceStyle.backgroundOverlay!,
                            color: e.target.value,
                          },
                        })
                      }
                      className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
                    />
                    <Input
                      value={currentDeviceStyle.backgroundOverlay.color || ""}
                      placeholder="rgba(0,0,0,0.5) یا #000000"
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          backgroundOverlay: {
                            ...currentDeviceStyle.backgroundOverlay!,
                            color: e.target.value,
                          },
                        })
                      }
                      className="h-7 text-xs flex-1 font-mono"
                      dir="ltr"
                    />
                  </div>
                )}

                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">شفافیت لایه رویی (Opacity: 0-1)</Label>
                  <Input
                    data-testid="bg-overlay-opacity-input"
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    value={currentDeviceStyle.backgroundOverlay.opacity ?? 0.5}
                    onChange={(e) => {
                      const val = parseFloat(e.target.value);
                      handleDeviceStyleChange({
                        backgroundOverlay: {
                          ...currentDeviceStyle.backgroundOverlay!,
                          opacity: !isNaN(val) ? Math.max(0, Math.min(1, val)) : 0.5,
                        },
                      });
                    }}
                    className="h-7 text-xs font-mono"
                    dir="ltr"
                  />
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Professional Typography Group Controls (Elementor Parity) */}
        <div className="space-y-3 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">تایپوگرافی کامل (Typography - المنتور)</Label>

          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">رنگ متن</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(currentDeviceStyle.typography?.color, "#09090b")}
                onChange={(e) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      color: e.target.value,
                    },
                  })
                }
                className="w-8 h-8 rounded border border-input cursor-pointer p-0.5"
              />
              <Input
                value={currentDeviceStyle.typography?.color || ""}
                placeholder="#000000 یا var(--foreground)"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      color: normalizeCssColor(e.target.value) || e.target.value,
                    },
                  })
                }
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1.5">
              <span className="text-[10px] text-muted-foreground me-1 self-center">توکن رنگ متن:</span>
              {[
                { label: "متن اصلی", val: "var(--foreground)" },
                { label: "اصلی برند", val: "var(--primary)" },
                { label: "ثانویه", val: "var(--secondary)" },
                { label: "متن کمرنگ", val: "var(--muted-foreground)" },
                { label: "موفقیت", val: "var(--success)" },
                { label: "هشدار", val: "var(--destructive)" },
              ].map((tok) => (
                <button
                  key={tok.val}
                  type="button"
                  onClick={() =>
                    handleDeviceStyleChange({
                      typography: {
                        ...currentDeviceStyle.typography,
                        color: tok.val,
                      },
                    })
                  }
                  className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
                >
                  {tok.label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">اندازه فونت (Font Size)</Label>
              <Input
                data-testid="typography-fontsize-input"
                type="number"
                min={8}
                max={96}
                value={currentDeviceStyle.typography?.fontSize?.value || ""}
                placeholder="مثلاً 16"
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      fontSize: !isNaN(val) ? { value: val, unit: "px" } : undefined,
                    },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">وزن فونت (Weight)</Label>
              <Select
                value={currentDeviceStyle.typography?.fontWeight || "inherit"}
                onValueChange={(val: any) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      fontWeight: val === "inherit" ? undefined : val,
                    },
                  })
                }
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="inherit">پیش‌فرض</SelectItem>
                  <SelectItem value="300">باریک (300)</SelectItem>
                  <SelectItem value="400">عادی (400)</SelectItem>
                  <SelectItem value="500">متوسط (500)</SelectItem>
                  <SelectItem value="600">نیمه‌پررنگ (600)</SelectItem>
                  <SelectItem value="700">پررنگ (700)</SelectItem>
                  <SelectItem value="900">سیاه (900)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-[11px] text-muted-foreground">جهت چینش متن (Text Align)</Label>
            <div className="grid grid-cols-4 gap-1 p-0.5 rounded-lg bg-muted/60 border border-border/60">
              {[
                { id: "right", label: "راست" },
                { id: "center", label: "وسط" },
                { id: "left", label: "چپ" },
                { id: "justify", label: "تراز" },
              ].map((al) => {
                const active = (currentDeviceStyle.typography?.textAlign || "right") === al.id;
                return (
                  <button
                    key={al.id}
                    type="button"
                    onClick={() =>
                      handleDeviceStyleChange({
                        typography: {
                          ...currentDeviceStyle.typography,
                          textAlign: al.id as any,
                        },
                      })
                    }
                    className={cn(
                      "py-1 rounded text-[11px] font-semibold transition",
                      active ? "bg-background text-foreground shadow-xs" : "text-muted-foreground hover:text-foreground"
                    )}
                  >
                    {al.label}
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-1.5 pt-1">
            <Label className="text-[11px] text-muted-foreground">سایه متن (Text Shadow - المنتور)</Label>
            <div className="flex items-center gap-2">
              <Input
                data-testid="typography-text-shadow-input"
                value={currentDeviceStyle.typography?.textShadow || ""}
                placeholder="مثلاً 0 2px 4px rgba(0,0,0,0.3)"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      textShadow: e.target.value.trim() || undefined,
                    },
                  })
                }
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              {[
                { label: "بدون سایه", val: "none" },
                { label: "ظریف", val: "0 1px 2px rgba(0,0,0,0.2)" },
                { label: "متوسط", val: "0 2px 4px rgba(0,0,0,0.3)" },
                { label: "عمیق", val: "0 4px 8px rgba(0,0,0,0.4)" },
                { label: "درخشان (Glow)", val: "0 0 8px var(--primary)" },
              ].map((tok) => (
                <button
                  key={tok.label}
                  type="button"
                  onClick={() =>
                    handleDeviceStyleChange({
                      typography: {
                        ...currentDeviceStyle.typography,
                        textShadow: tok.val === "none" ? undefined : tok.val,
                      },
                    })
                  }
                  className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
                >
                  {tok.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* CSS Filters (Elementor Parity) */}
        <div className="space-y-1.5 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">فیلترهای گرافیکی (CSS Filters - المنتور)</Label>
          <div className="flex items-center gap-2">
            <Input
              data-testid="css-filter-input"
              value={currentDeviceStyle.filter || ""}
              placeholder="مثلاً blur(4px) یا grayscale(100%)"
              onChange={(e) =>
                handleDeviceStyleChange({
                  filter: e.target.value.trim() || undefined,
                })
              }
              className="h-8 text-xs flex-1 font-mono"
              dir="ltr"
            />
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            <span className="text-[10px] text-muted-foreground me-1 self-center">پریست‌های فیلتر:</span>
            {[
              { label: "عادی (None)", val: "none" },
              { label: "مات (Blur 4px)", val: "blur(4px)" },
              { label: "سیاه و سفید", val: "grayscale(100%)" },
              { label: "پرکنتراست", val: "contrast(125%) brightness(105%)" },
              { label: "نوستالژی (Sepia)", val: "sepia(80%)" },
            ].map((fil) => (
              <button
                key={fil.label}
                type="button"
                onClick={() =>
                  handleDeviceStyleChange({
                    filter: fil.val === "none" ? undefined : fil.val,
                  })
                }
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {fil.label}
              </button>
            ))}
          </div>
        </div>

        {/* Box Shadow Preset Tokens (Elementor Grouped Controls) */}
        <div className="space-y-1.5 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">سایه کادر (Box Shadow - المنتور)</Label>
          <div className="flex items-center gap-2">
            <Input
              value={currentDeviceStyle.boxShadow || ""}
              placeholder="مثلاً 0 10px 15px -3px rgba(0,0,0,0.1)"
              onChange={(e) =>
                handleDeviceStyleChange({
                  boxShadow: e.target.value.trim() || undefined,
                })
              }
              className="h-8 text-xs flex-1 font-mono"
              dir="ltr"
            />
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            <span className="text-[10px] text-muted-foreground me-1 self-center">پریست‌های سایه:</span>
            {[
              { label: "بدون سایه", val: "none" },
              { label: "بسیار ظریف (xs)", val: "0 1px 2px 0 rgb(0 0 0 / 0.05)" },
              { label: "نرم (sm)", val: "0 1px 3px 0 rgb(0 0 0 / 0.1), 0 1px 2px -1px rgb(0 0 0 / 0.1)" },
              { label: "متوسط (md)", val: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)" },
              { label: "عمیق (lg)", val: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)" },
              { label: "شناور (xl)", val: "0 20px 25px -5px rgb(0 0 0 / 0.1), 0 8px 10px -6px rgb(0 0 0 / 0.1)" },
            ].map((tok) => (
              <button
                key={tok.label}
                type="button"
                onClick={() =>
                  handleDeviceStyleChange({
                    boxShadow: tok.val === "none" ? undefined : tok.val,
                  })
                }
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {tok.label}
              </button>
            ))}
          </div>

          <div className="space-y-1 pt-1.5">
            <Label className="text-[11px] text-muted-foreground">سایه کادر در حالت هاور (Hover Box Shadow)</Label>
            <Input
              data-testid="hover-box-shadow-input"
              value={currentDeviceStyle.hoverBoxShadow || ""}
              placeholder="مثلاً 0 20px 25px -5px rgba(0,0,0,0.2)"
              onChange={(e) =>
                handleDeviceStyleChange({
                  hoverBoxShadow: e.target.value.trim() || undefined,
                })
              }
              className="h-8 text-xs font-mono"
              dir="ltr"
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            <Label className="text-[11px] text-muted-foreground">مدت زمان گذار (Transition Duration)</Label>
            <div className="flex items-center gap-1.5 w-28">
              <Input
                data-testid="transition-duration-input"
                type="number"
                step="0.05"
                min={0}
                max={2}
                value={currentDeviceStyle.transitionDuration ?? 0.3}
                onChange={(e) => {
                  const val = parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    transitionDuration: !isNaN(val) ? val : 0.3,
                  });
                }}
                className="h-7 text-xs font-mono"
                dir="ltr"
              />
              <span className="text-[10px] text-muted-foreground">ثانیه</span>
            </div>
          </div>
        </div>

        {/* Backdrop Filter & CSS Blur (Glassmorphism & Frosted Glass - Elementor Parity) */}
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">شیشه مات پس‌زمینه (Backdrop Blur - Glassmorphism)</Label>
            <Select
              value={currentDeviceStyle.backdropBlur || "none"}
              onValueChange={(val: any) => handleDeviceStyleChange({ backdropBlur: val === "none" ? null : val })}
            >
              <SelectTrigger className="h-7 text-xs w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون تاری</SelectItem>
                <SelectItem value="sm">تاری ملایم (4px)</SelectItem>
                <SelectItem value="md">تاری متوسط (8px)</SelectItem>
                <SelectItem value="lg">تاری شیشه‌ای (16px)</SelectItem>
                <SelectItem value="xl">تاری عمیق (24px)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Section Shape Dividers (Elementor Parity) */}
        {selectedElement.type === "container" && (
          <div className="space-y-3 pt-2 border-t">
            <Label className="text-xs font-bold text-foreground block">جداکننده شکل کانتینر (Shape Divider)</Label>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">شکل بالا (Top)</Label>
                <Select
                  value={selectedElement.styles?.shapeDividerTop || "none"}
                  onValueChange={(val: string) =>
                    updateElementStyles(selectedElement.id, {
                      shapeDividerTop: val === "none" ? null : val,
                    })
                  }
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">بدون شکل</SelectItem>
                    <SelectItem value="waves">موجی (Waves)</SelectItem>
                    <SelectItem value="curve">منحنی (Curve)</SelectItem>
                    <SelectItem value="triangle">مثلث (Triangle)</SelectItem>
                    <SelectItem value="tilt">مورب (Tilt)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">شکل پایین (Bottom)</Label>
                <Select
                  value={selectedElement.styles?.shapeDividerBottom || "none"}
                  onValueChange={(val: string) =>
                    updateElementStyles(selectedElement.id, {
                      shapeDividerBottom: val === "none" ? null : val,
                    })
                  }
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">بدون شکل</SelectItem>
                    <SelectItem value="waves">موجی (Waves)</SelectItem>
                    <SelectItem value="curve">منحنی (Curve)</SelectItem>
                    <SelectItem value="triangle">مثلث (Triangle)</SelectItem>
                    <SelectItem value="tilt">مورب (Tilt)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>
        )}

        {/* Border Style, Width, Color & Radius Grouped Controls */}
        <div className="space-y-3 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">کادر و حاشیه (Border & Radius - المنتور)</Label>

          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">نوع خط کادر</Label>
              <Select
                value={currentDeviceStyle.border?.style || "none"}
                onValueChange={(val: any) =>
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: val,
                    },
                  })
                }
              >
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">بدون کادر (None)</SelectItem>
                  <SelectItem value="solid">یکپارچه (Solid)</SelectItem>
                  <SelectItem value="dashed">خط‌چین (Dashed)</SelectItem>
                  <SelectItem value="dotted">نقطه‌چین (Dotted)</SelectItem>
                  <SelectItem value="double">دوتایی (Double)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">ضخامت کادر (Width)</Label>
              <Input
                type="number"
                min={0}
                max={24}
                value={currentDeviceStyle.border?.width?.top?.value ?? 0}
                onChange={(e) => {
                  const val = parseFloat(e.target.value) || 0;
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: currentDeviceStyle.border?.style || "solid",
                      width: {
                        top: { value: val, unit: "px" },
                        right: { value: val, unit: "px" },
                        bottom: { value: val, unit: "px" },
                        left: { value: val, unit: "px" },
                        isLinked: true,
                      },
                    },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">رنگ کادر</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(currentDeviceStyle.border?.color, "#e4e4e7")}
                onChange={(e) =>
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: currentDeviceStyle.border?.style || "solid",
                      color: e.target.value,
                    },
                  })
                }
                className="w-8 h-8 rounded border border-input cursor-pointer p-0.5"
              />
              <Input
                value={currentDeviceStyle.border?.color || ""}
                placeholder="#e4e4e7 یا var(--border)"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: currentDeviceStyle.border?.style || "solid",
                      color: normalizeCssColor(e.target.value) || e.target.value,
                    },
                  })
                }
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-bold text-foreground">شعاع گردی کادر (Border Radius)</Label>
            <div className="flex items-center gap-2">
              <Input
                value={(currentDeviceStyle.border as any)?.radiusToken || ""}
                placeholder="مثلاً 12px یا var(--radius)"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: currentDeviceStyle.border?.style || "solid",
                      radiusToken: e.target.value,
                    } as any,
                  })
                }
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1.5">
              <span className="text-[10px] text-muted-foreground me-1 self-center">توکن شعاع:</span>
              {[
                { label: "بدون گردی", val: "0px" },
                { label: "شعاع تم سازمانی", val: "var(--radius)" },
                { label: "کوچک (6px)", val: "6px" },
                { label: "متوسط (12px)", val: "12px" },
                { label: "بزرگ (16px)", val: "16px" },
                { label: "کپسولی", val: "9999px" },
              ].map((tok) => (
                <button
                  key={tok.val}
                  type="button"
                  onClick={() =>
                    handleDeviceStyleChange({
                      border: {
                        ...currentDeviceStyle.border,
                        style: currentDeviceStyle.border?.style || "solid",
                        radiusToken: tok.val,
                      } as any,
                    })
                  }
                  className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
                >
                  {tok.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Advanced Layout & Flexbox/Grid (P4) */}
        <div className="space-y-4 pt-3 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">چیدمان پیشرفته (Advanced Layout - P4)</Label>

          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">نوع نمایش (Display)</Label>
            <Select
              value={currentDeviceStyle.display || "inherit"}
              onValueChange={(val) => handleDeviceStyleChange({ display: val as any })}
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="inherit">ارث‌بری (Inherit)</SelectItem>
                <SelectItem value="block">بلاک (Block)</SelectItem>
                <SelectItem value="flex">فلکس (Flexbox)</SelectItem>
                <SelectItem value="grid">شبکه (CSS Grid)</SelectItem>
                <SelectItem value="inline-block">درون‌خطی (Inline Block)</SelectItem>
                <SelectItem value="none">مخفی (None)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Flexbox options */}
          <div className="p-2.5 rounded-lg border bg-muted/20 space-y-3">
            <span className="text-[11px] font-bold text-foreground block">تنظیمات فلکس (Flexbox Controls)</span>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">جهت چیدمان (Direction)</Label>
                <Select
                  value={currentDeviceStyle.flexDirection || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ flexDirection: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="row">افقی (Row)</SelectItem>
                    <SelectItem value="column">عمودی (Column)</SelectItem>
                    <SelectItem value="row-reverse">افقی معکوس</SelectItem>
                    <SelectItem value="column-reverse">عمودی معکوس</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">ترازبندی اصلی (Justify)</Label>
                <Select
                  value={currentDeviceStyle.justifyContent || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ justifyContent: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="start">شروع (Start)</SelectItem>
                    <SelectItem value="center">وسط (Center)</SelectItem>
                    <SelectItem value="end">انتها (End)</SelectItem>
                    <SelectItem value="between">فاصله بینابین</SelectItem>
                    <SelectItem value="around">فاصله پیرامون</SelectItem>
                    <SelectItem value="evenly">فاصله مساوی</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">ترازبندی عمود (Align)</Label>
                <Select
                  value={currentDeviceStyle.alignItems || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ alignItems: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="stretch">کشیده (Stretch)</SelectItem>
                    <SelectItem value="center">وسط (Center)</SelectItem>
                    <SelectItem value="start">شروع (Start)</SelectItem>
                    <SelectItem value="end">انتها (End)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">شکست سطر (Wrap)</Label>
                <Select
                  value={currentDeviceStyle.flexWrap || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ flexWrap: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="nowrap">یک‌سطری (Nowrap)</SelectItem>
                    <SelectItem value="wrap">چندسطری (Wrap)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          </div>

          {/* Positioning & Z-Index & Overflow */}
          <div className="p-2.5 rounded-lg border bg-muted/20 space-y-3">
            <span className="text-[11px] font-bold text-foreground block">موقعیت‌یابی و لایه‌بندی (Positioning & Z-Index)</span>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">موقعیت (Position)</Label>
                <Select
                  value={currentDeviceStyle.position || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ position: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="static">عادی (Static)</SelectItem>
                    <SelectItem value="relative">نسبی (Relative)</SelectItem>
                    <SelectItem value="absolute">مطلق (Absolute)</SelectItem>
                    <SelectItem value="sticky">چسبان (Sticky)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">سرریز (Overflow)</Label>
                <Select
                  value={currentDeviceStyle.overflow || "inherit"}
                  onValueChange={(val) => handleDeviceStyleChange({ overflow: val as any })}
                >
                  <SelectTrigger className="h-7 text-xs"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">ارث‌بری</SelectItem>
                    <SelectItem value="visible">نمایان (Visible)</SelectItem>
                    <SelectItem value="hidden">مخفی (Hidden)</SelectItem>
                    <SelectItem value="scroll">اسکرول (Scroll)</SelectItem>
                    <SelectItem value="auto">خودکار (Auto)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">ترتیب لایه عمقی (Z-Index)</Label>
                <Input
                  type="number"
                  min={0}
                  max={999}
                  value={currentDeviceStyle.zIndex ?? ""}
                  placeholder="خودکار"
                  onChange={(e) =>
                    handleDeviceStyleChange({
                      zIndex: e.target.value === "" ? null : parseInt(e.target.value, 10),
                    })
                  }
                  className="h-7 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">میزان شفافیت (Opacity)</Label>
                <Input
                  data-testid="opacity-input"
                  type="number"
                  step="0.05"
                  min={0}
                  max={1}
                  value={currentDeviceStyle.opacity ?? ""}
                  placeholder="۱.۰"
                  onChange={(e) => {
                    const val = e.target.value === "" ? null : parseFloat(e.target.value);
                    handleDeviceStyleChange({
                      opacity: val !== null && !isNaN(val) ? Math.max(0, Math.min(1, val)) : null,
                    });
                  }}
                  className="h-7 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>

            {/* Flex Item Self Alignment & Order (Elementor Item Controls) */}
            <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/50">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">تراز انفرادی (Align Self)</Label>
                <Select
                  value={currentDeviceStyle.alignSelf || "inherit"}
                  onValueChange={(val: any) =>
                    handleDeviceStyleChange({
                      alignSelf: val === "inherit" ? undefined : val,
                    })
                  }
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="inherit">پیش‌فرض والد</SelectItem>
                    <SelectItem value="auto">خودکار (Auto)</SelectItem>
                    <SelectItem value="start">شروع (Start)</SelectItem>
                    <SelectItem value="center">وسط (Center)</SelectItem>
                    <SelectItem value="end">پایان (End)</SelectItem>
                    <SelectItem value="stretch">کشیده (Stretch)</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">ترتیب چینش (Order)</Label>
                <Input
                  data-testid="order-input"
                  type="number"
                  value={currentDeviceStyle.order ?? ""}
                  placeholder="خودکار"
                  onChange={(e) => {
                    const val = e.target.value === "" ? null : parseInt(e.target.value, 10);
                    handleDeviceStyleChange({
                      order: val !== null && !isNaN(val) ? val : null,
                    });
                  }}
                  className="h-7 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>
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
              renameElement(selectedElement.id, e.target.value);
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

        {/* Custom Attributes (Elementor Pro Parity) */}
        <div className="space-y-1.5 pt-2 border-t border-border/80" data-testid="custom-attributes-control">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">ویژگی‌های سفارشی (Custom Attributes - المنتور)</Label>
            <span className="text-[10px] text-muted-foreground font-mono">key|value</span>
          </div>
          <p className="text-[11px] text-muted-foreground leading-relaxed">
            ویژگی‌های سفارشی المان را وارد کنید. هر ویژگی در یک خط، کلید و مقدار با نویسه <code className="text-primary font-bold">|</code> تفکیک می‌شوند (مانند <span dir="ltr" className="font-mono text-[10px]">data-tracking|hero-cta</span>).
          </p>
          <textarea
            data-testid="custom-attributes-textarea"
            rows={3}
            dir="ltr"
            placeholder={"key|value\ndata-tracking|hero-cta\naria-label|test-region"}
            value={
              typeof selectedElement.styles.customAttributes === "string"
                ? selectedElement.styles.customAttributes
                : selectedElement.styles.customAttributes && typeof selectedElement.styles.customAttributes === "object"
                ? Object.entries(selectedElement.styles.customAttributes)
                    .map(([k, v]) => `${k}|${v}`)
                    .join("\n")
                : ""
            }
            onChange={(e) =>
              updateElementStyles(selectedElement.id, {
                customAttributes: e.target.value,
              })
            }
            className="w-full rounded-md border border-input bg-background p-2 text-xs font-mono outline-none focus:ring-1 focus:ring-primary"
          />
        </div>

        {/* Transform (Elementor Parity Wave 1) */}
        <div className="space-y-3 pt-2 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">تبدیل سه‌بعدی و چرخش (Transform)</Label>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">زاویه چرخش (درجه)</Label>
              <Input
                data-testid="transform-rotate-input"
                type="number"
                min={-360}
                max={360}
                value={currentDeviceStyle.transform?.rotate ?? ""}
                placeholder="۰°"
                onChange={(e) => {
                  const val = e.target.value === "" ? null : parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    transform: { ...(currentDeviceStyle.transform || {}), rotate: val },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">مقیاس (Scale)</Label>
              <Input
                data-testid="transform-scale-input"
                type="number"
                step="0.05"
                min={0.1}
                max={3}
                value={currentDeviceStyle.transform?.scale ?? ""}
                placeholder="۱.۰"
                onChange={(e) => {
                  const val = e.target.value === "" ? null : parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    transform: { ...(currentDeviceStyle.transform || {}), scale: val },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">اریب افقی (Skew X)</Label>
              <Input
                data-testid="transform-skewx-input"
                type="number"
                min={-180}
                max={180}
                value={currentDeviceStyle.transform?.skewX ?? ""}
                placeholder="۰°"
                onChange={(e) => {
                  const val = e.target.value === "" ? null : parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    transform: { ...(currentDeviceStyle.transform || {}), skewX: val },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1">
              <Label className="text-[11px] text-muted-foreground">اریب عمودی (Skew Y)</Label>
              <Input
                data-testid="transform-skewy-input"
                type="number"
                min={-180}
                max={180}
                value={currentDeviceStyle.transform?.skewY ?? ""}
                placeholder="۰°"
                onChange={(e) => {
                  const val = e.target.value === "" ? null : parseFloat(e.target.value);
                  handleDeviceStyleChange({
                    transform: { ...(currentDeviceStyle.transform || {}), skewY: val },
                  });
                }}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              data-testid="transform-flipx-btn"
              onClick={() => {
                const cur = currentDeviceStyle.transform?.flipX || false;
                handleDeviceStyleChange({
                  transform: { ...(currentDeviceStyle.transform || {}), flipX: !cur },
                });
              }}
              className={cn(
                "py-1.5 px-2 rounded-lg text-xs font-semibold border transition text-center",
                currentDeviceStyle.transform?.flipX
                  ? "bg-primary text-primary-foreground border-primary shadow-xs"
                  : "bg-muted/60 text-muted-foreground hover:text-foreground border-border/70"
              )}
            >
              وارون افقی (Flip X)
            </button>
            <button
              type="button"
              data-testid="transform-flipy-btn"
              onClick={() => {
                const cur = currentDeviceStyle.transform?.flipY || false;
                handleDeviceStyleChange({
                  transform: { ...(currentDeviceStyle.transform || {}), flipY: !cur },
                });
              }}
              className={cn(
                "py-1.5 px-2 rounded-lg text-xs font-semibold border transition text-center",
                currentDeviceStyle.transform?.flipY
                  ? "bg-primary text-primary-foreground border-primary shadow-xs"
                  : "bg-muted/60 text-muted-foreground hover:text-foreground border-border/70"
              )}
            >
              وارون عمودی (Flip Y)
            </button>
          </div>
        </div>

        {/* Masking (Elementor Parity Wave 1) */}
        <div className="space-y-3 pt-2 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">ماسک تصویر و المان (Mask)</Label>
          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">شکل ماسک</Label>
            <Select
              value={currentDeviceStyle.mask?.shape || "none"}
              onValueChange={(val) =>
                handleDeviceStyleChange({
                  mask: { ...(currentDeviceStyle.mask || {}), shape: val === "none" ? undefined : val },
                })
              }
            >
              <SelectTrigger data-testid="mask-shape-select" className="h-8 text-xs">
                <SelectValue placeholder="انتخاب شکل ماسک" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون ماسک (None)</SelectItem>
                <SelectItem value="circle">دایره‌ای (Circle)</SelectItem>
                <SelectItem value="flower">گلبرگ (Flower)</SelectItem>
                <SelectItem value="triangle">مثلثی (Triangle)</SelectItem>
                <SelectItem value="blob">حبابی (Blob)</SelectItem>
                <SelectItem value="hexagon">شش‌ضلعی (Hexagon)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Entrance / Scroll Animation */}
        <div className="space-y-3 pt-2 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">انیمیشن ورود و اسکرول (Animation)</Label>
          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">نوع انیمیشن</Label>
            <Select
              value={selectedElement.styles.animation || "none"}
              onValueChange={(val) =>
                updateElementStyles(selectedElement.id, {
                  animation: val,
                })
              }
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue placeholder="انتخاب انیمیشن" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون انیمیشن (None)</SelectItem>
                <SelectItem value="fade-in">محو شدن به پیدایش (Fade In)</SelectItem>
                <SelectItem value="slide-up">لغزش از پایین به بالا (Slide Up)</SelectItem>
                <SelectItem value="zoom-in">بزرگ‌نمایی نرم (Zoom In)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {selectedElement.styles.animation && selectedElement.styles.animation !== "none" && (
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">مدت زمان (ثانیه)</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0.1"
                  max="3"
                  value={selectedElement.styles.animationDuration || 0.6}
                  onChange={(e) =>
                    updateElementStyles(selectedElement.id, {
                      animationDuration: parseFloat(e.target.value) || 0.6,
                    })
                  }
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-[11px] text-muted-foreground">تأخیر (ثانیه)</Label>
                <Input
                  type="number"
                  step="0.1"
                  min="0"
                  max="3"
                  value={selectedElement.styles.animationDelay || 0}
                  onChange={(e) =>
                    updateElementStyles(selectedElement.id, {
                      animationDelay: parseFloat(e.target.value) || 0,
                    })
                  }
                  className="h-8 text-xs"
                />
              </div>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between pt-2 border-t border-border/80">
          <Label className="text-xs">مخفی کردن المان (Visibility)</Label>
          <Switch
            checked={selectedElement.isHidden}
            onCheckedChange={(val) => {
              setElementHidden(selectedElement.id, val);
            }}
          />
        </div>

        <div className="flex items-center justify-between pt-1">
          <Label className="text-xs">قفل کردن المان در ویرایشگر</Label>
          <Switch
            checked={selectedElement.isLocked}
            onCheckedChange={(val) => {
              setElementLocked(selectedElement.id, val);
            }}
          />
        </div>

        {/* Shape Dividers (Elementor Parity Wave 1) */}
        {selectedElement.type === "container" && (
          <div className="space-y-3 pt-3 border-t border-border/80">
            <Label className="text-xs font-bold text-foreground block">اشکال جداکننده بخش (Shape Dividers)</Label>
            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground">شکل جداکننده بالا (Top Shape)</Label>
              <Select
                value={selectedElement.styles?.shapeDividerTop || "none"}
                onValueChange={(val) =>
                  updateElementStyles(selectedElement.id, {
                    shapeDividerTop: val,
                  })
                }
              >
                <SelectTrigger data-testid="shape-divider-top-select" className="h-8 text-xs">
                  <SelectValue placeholder="انتخاب شکل بالا" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">بدون جداکننده (None)</SelectItem>
                  <SelectItem value="waves">امواج نرم (Waves)</SelectItem>
                  <SelectItem value="curve">منحنی مقعر (Curve)</SelectItem>
                  <SelectItem value="triangle">مثلث (Triangle)</SelectItem>
                  <SelectItem value="tilt">شیب مایل (Tilt)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground">شکل جداکننده پایین (Bottom Shape)</Label>
              <Select
                value={selectedElement.styles?.shapeDividerBottom || "none"}
                onValueChange={(val) =>
                  updateElementStyles(selectedElement.id, {
                    shapeDividerBottom: val,
                  })
                }
              >
                <SelectTrigger data-testid="shape-divider-bottom-select" className="h-8 text-xs">
                  <SelectValue placeholder="انتخاب شکل پایین" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="none">بدون جداکننده (None)</SelectItem>
                  <SelectItem value="waves">امواج نرم (Waves)</SelectItem>
                  <SelectItem value="curve">منحنی مقعر (Curve)</SelectItem>
                  <SelectItem value="triangle">مثلث (Triangle)</SelectItem>
                  <SelectItem value="tilt">شیب مایل (Tilt)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label className="text-[11px] text-muted-foreground">رنگ شکل جداکننده</Label>
              <Input
                data-testid="shape-divider-color-input"
                type="text"
                placeholder="#ffffff"
                value={selectedElement.styles?.shapeDividerColor || "#ffffff"}
                onChange={(e) =>
                  updateElementStyles(selectedElement.id, {
                    shapeDividerColor: e.target.value,
                  })
                }
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>
        )}

        {/* Conditional Visibility (P4) */}
        <div className="space-y-3 pt-3 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">نمایش شرطی (Conditional Visibility - P4)</Label>

          <div className="space-y-2 p-2.5 rounded-lg border bg-muted/20">
            <span className="text-[11px] font-semibold text-muted-foreground block">نمایش بر اساس نوع دستگاه:</span>
            <div className="flex items-center justify-between text-xs">
              <span>نمایش در دسکتاپ</span>
              <Switch
                checked={selectedElement.visibleOnDesktop !== false}
                onCheckedChange={(val) =>
                  useBuilderStore.getState().updateElementVisibility(selectedElement.id, { desktop: val })
                }
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>نمایش در تبلت</span>
              <Switch
                checked={selectedElement.visibleOnTablet !== false}
                onCheckedChange={(val) =>
                  useBuilderStore.getState().updateElementVisibility(selectedElement.id, { tablet: val })
                }
              />
            </div>
            <div className="flex items-center justify-between text-xs">
              <span>نمایش در موبایل</span>
              <Switch
                checked={selectedElement.visibleOnMobile !== false}
                onCheckedChange={(val) =>
                  useBuilderStore.getState().updateElementVisibility(selectedElement.id, { mobile: val })
                }
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label className="text-[11px] text-muted-foreground">شرط ورود کاربر (Auth Visibility)</Label>
            <Select
              value={selectedElement.authVisibility || "all"}
              onValueChange={(val: any) =>
                useBuilderStore.getState().updateElementVisibility(selectedElement.id, { auth: val })
              }
            >
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">همه کاربران (عمومی)</SelectItem>
                <SelectItem value="authenticated">فقط کاربران واردشده (اعضا)</SelectItem>
                <SelectItem value="guest">فقط کاربران مهمان (واردنشده)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Global Component Controls (P4) */}
        <div className="space-y-2 pt-3 border-t border-border/80">
          <Label className="text-xs font-bold text-foreground block">کامپوننت سراسری (Global / Synced Component)</Label>
          {selectedElement.globalComponentId ? (
            <div className="p-2.5 rounded-lg border border-emerald-500/30 bg-emerald-500/5 space-y-2">
              <div className="flex items-center gap-1.5 text-xs text-emerald-600 dark:text-emerald-400 font-bold">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                <span>کامپوننت همگام سراسری فعال است</span>
              </div>
              <p className="text-[10px] text-muted-foreground leading-relaxed">
                تغییرات این المان به صورت خودکار در تمام نمونه‌های استفاده‌کننده از این کامپوننت همگام‌سازی می‌شود.
              </p>
              <button
                type="button"
                onClick={() => {
                  detachGlobalComponent(selectedElement.id);
                }}
                className="w-full py-1 text-xs rounded border border-border text-muted-foreground hover:text-destructive hover:border-destructive transition"
              >
                جدا کردن از کامپوننت سراسری (Detach)
              </button>
            </div>
          ) : (
            <button
              type="button"
              onClick={() => {
                useBuilderStore.getState().makeGlobalComponent(selectedElement.id);
              }}
              className="w-full py-1.5 rounded-lg border border-primary text-xs font-semibold text-primary hover:bg-primary/5 transition"
            >
              تبدیل به کامپوننت همگام سراسری (Make Global)
            </button>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="flex flex-col h-full bg-card border-s border-border select-none" dir="rtl">
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
        <TabsList className="grid grid-cols-3 h-9 mx-3 my-2 rounded-xl bg-muted/70 p-1 border border-border/60">
          <TabsTrigger value="content" className="text-xs py-1 font-semibold rounded-lg">
            محتوا
          </TabsTrigger>
          <TabsTrigger value="style" className="text-xs py-1 font-semibold rounded-lg">
            استایل
          </TabsTrigger>
          <TabsTrigger value="advanced" className="text-xs py-1 font-semibold rounded-lg">
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
