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
import { MediaPicker } from "@/components/admin/media-picker";
import { useBuilderStore, findElementById, type InspectorTab } from "@/stores/builder-store";
import { toValidHexColor, normalizeCssColor } from "@/lib/builder/color-utils";
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
            <div className="space-y-1.5">
              <Label className="text-xs">تعداد ستون‌ها در دسکتاپ</Label>
              <Input
                type="number"
                min={1}
                max={12}
                value={layout.gridColumns}
                onChange={(e) => {
                  const num = parseInt(e.target.value, 10) || 1;
                  updateElementLayout(selectedElement.id, { gridColumns: num });
                }}
                className="h-8 text-xs"
              />
            </div>
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
                value={String(props.submit_url || "/api/v1/content/forms/submit")}
                onChange={(e) => handlePropChange("submit_url", e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">پیام موفقیت‌آمیز ثبت</Label>
              <Input
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
              <Label className="text-xs">عنوان ویژگی</Label>
              <Input
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
              placeholder="100% / 1280px / خودکار"
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

        {/* Height / Min-Height & Fit to Screen (Elementor Parity) */}
        {selectedElement.type === "container" && (
          <div className="space-y-1.5 pt-2 border-t">
            <Label className="text-xs font-bold text-foreground">ارتفاع کانتینر (Height / Min-Height)</Label>
            <div className="flex items-center gap-2">
              <Input
                value={currentDeviceStyle.minHeight ? `${currentDeviceStyle.minHeight.value}${currentDeviceStyle.minHeight.unit}` : ""}
                placeholder="مثلاً 100vh یا 450px"
                onChange={(e) => {
                  const raw = e.target.value.trim();
                  if (!raw || raw === "auto") {
                    handleDeviceStyleChange({ minHeight: undefined });
                    return;
                  }
                  if (raw.endsWith("vh")) {
                    handleDeviceStyleChange({ minHeight: { value: parseFloat(raw) || 100, unit: "vh" as any } });
                  } else if (raw.endsWith("px")) {
                    handleDeviceStyleChange({ minHeight: { value: parseFloat(raw) || 0, unit: "px" } });
                  } else {
                    const val = parseFloat(raw);
                    if (!isNaN(val)) {
                      handleDeviceStyleChange({ minHeight: { value: val, unit: "px" } });
                    }
                  }
                }}
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
              <span className="text-[10px] text-muted-foreground me-1 self-center">پریست ارتفاع:</span>
              {[
                { label: "پیش‌فرض (خودکار)", h: undefined },
                { label: "تمام‌صفحه (100vh)", h: { value: 100, unit: "vh" as any } },
                { label: "هیرو بزرگ (600px)", h: { value: 600, unit: "px" as UnitType } },
                { label: "سکشن متوسط (400px)", h: { value: 400, unit: "px" as UnitType } },
              ].map((ht) => (
                <button
                  key={ht.label}
                  type="button"
                  data-testid={`height-preset-${ht.label}`}
                  onClick={() => handleDeviceStyleChange({ minHeight: ht.h })}
                  className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
                >
                  {ht.label}
                </button>
              ))}
            </div>
          </div>
        )}

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

        {/* Background Style: Solid, Gradient, or Image (Elementor Parity) */}
        <div className="space-y-3 pt-2 border-t">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">پس‌زمینه (Background)</Label>
            <Select
              value={currentDeviceStyle.background?.type || "color"}
              onValueChange={(val: "none" | "color" | "gradient" | "image") =>
                handleDeviceStyleChange({
                  background: {
                    type: val,
                    color: currentDeviceStyle.background?.color || "#ffffff",
                    gradient: currentDeviceStyle.background?.gradient || {
                      direction: "to-r",
                      fromColor: "#10b981",
                      toColor: "#3b82f6",
                    },
                    imageUrl: currentDeviceStyle.background?.imageUrl || "",
                    position: "center",
                    size: "cover",
                  },
                })
              }
            >
              <SelectTrigger className="h-7 text-xs w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون پس‌زمینه</SelectItem>
                <SelectItem value="color">رنگ خالص (Solid)</SelectItem>
                <SelectItem value="gradient">گرادیانت (Gradient)</SelectItem>
                <SelectItem value="image">تصویر پس‌زمینه</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {currentDeviceStyle.background?.type === "gradient" ? (
            <div className="p-2.5 rounded-lg border bg-muted/20 space-y-2.5">
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1">
                  <Label className="text-[10px] text-muted-foreground">رنگ شروع</Label>
                  <div className="flex items-center gap-1.5">
                    <input
                      type="color"
                      value={toValidHexColor(currentDeviceStyle.background.gradient?.fromColor, "#10b981")}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            ...currentDeviceStyle.background!,
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: e.target.value,
                              toColor: currentDeviceStyle.background?.gradient?.toColor || "#3b82f6",
                            },
                          },
                        })
                      }
                      className="w-6 h-6 rounded border cursor-pointer p-0.5"
                    />
                    <Input
                      value={currentDeviceStyle.background.gradient?.fromColor || "#10b981"}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            ...currentDeviceStyle.background!,
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
                      value={toValidHexColor(currentDeviceStyle.background.gradient?.toColor, "#3b82f6")}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            ...currentDeviceStyle.background!,
                            type: "gradient",
                            gradient: {
                              direction: currentDeviceStyle.background?.gradient?.direction || "to-r",
                              fromColor: currentDeviceStyle.background?.gradient?.fromColor || "#10b981",
                              toColor: e.target.value,
                            },
                          },
                        })
                      }
                      className="w-6 h-6 rounded border cursor-pointer p-0.5"
                    />
                    <Input
                      value={currentDeviceStyle.background.gradient?.toColor || "#3b82f6"}
                      onChange={(e) =>
                        handleDeviceStyleChange({
                          background: {
                            ...currentDeviceStyle.background!,
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
                  value={currentDeviceStyle.background.gradient?.direction || "to-r"}
                  onValueChange={(val: any) =>
                    handleDeviceStyleChange({
                      background: {
                        ...currentDeviceStyle.background!,
                        type: "gradient",
                        gradient: {
                          fromColor: currentDeviceStyle.background?.gradient?.fromColor || "#10b981",
                          toColor: currentDeviceStyle.background?.gradient?.toColor || "#3b82f6",
                          direction: val,
                        },
                      },
                    })
                  }
                >
                  <SelectTrigger className="h-7 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="to-r">افقی به راست (→)</SelectItem>
                    <SelectItem value="to-l">افقی به چپ (←)</SelectItem>
                    <SelectItem value="to-b">عمودی به پایین (↓)</SelectItem>
                    <SelectItem value="to-t">عمودی به بالا (↑)</SelectItem>
                    <SelectItem value="to-tr">مورب به بالا راست (↗)</SelectItem>
                    <SelectItem value="to-tl">مورب به بالا چپ (↖)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
          ) : currentDeviceStyle.background?.type === "image" ? (
            <div className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
              <Label className="text-[10px] text-muted-foreground">آدرس تصویر پس‌زمینه (URL)</Label>
              <Input
                value={currentDeviceStyle.background.imageUrl || ""}
                placeholder="https://... یا /image.png"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    background: {
                      ...currentDeviceStyle.background!,
                      type: "image",
                      imageUrl: e.target.value,
                    },
                  })
                }
                className="h-7 text-xs font-mono"
                dir="ltr"
              />
            </div>
          ) : currentDeviceStyle.background?.type === "none" ? null : (
            <>
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
              <div className="flex flex-wrap gap-1 mt-1.5">
                <span className="text-[10px] text-muted-foreground me-1 self-center">توکن‌های تم:</span>
                {[
                  { label: "رنگ اصلی", val: "var(--primary)" },
                  { label: "رنگ ثانویه", val: "var(--secondary)" },
                  { label: "سطح / کارت", val: "var(--surface, var(--card))" },
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
            </>
          )}
        </div>

        {/* Box Shadow Controls (Elementor Style Parity) */}
        <div className="space-y-1.5 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">سایه کادر (Box Shadow - Elementor Style)</Label>
          <div className="flex items-center gap-2">
            <Input
              value={currentDeviceStyle.shadow || ""}
              placeholder="none / 0 4px 6px -1px rgba(0,0,0,0.1)"
              onChange={(e) => handleDeviceStyleChange({ shadow: e.target.value })}
              className="h-8 text-xs flex-1 font-mono"
              dir="ltr"
            />
          </div>
          <div className="flex flex-wrap gap-1 mt-1.5">
            <span className="text-[10px] text-muted-foreground me-1 self-center">پریست سایه:</span>
            {[
              { label: "بدون سایه", val: "none" },
              { label: "سایه ملایم (SM)", val: "0 1px 2px 0 rgba(0, 0, 0, 0.05)" },
              { label: "سایه استاندارد (MD)", val: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1)" },
              { label: "سایه عمیق (LG)", val: "0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -4px rgba(0, 0, 0, 0.1)" },
              { label: "درخشش برند (Glow)", val: "0 0 15px rgba(16, 185, 129, 0.3)" },
            ].map((sh) => (
              <button
                key={sh.label}
                type="button"
                onClick={() => handleDeviceStyleChange({ shadow: sh.val })}
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {sh.label}
              </button>
            ))}
          </div>
        </div>

        {/* Text Color & Typography Tokens */}
        <div className="space-y-1.5 pt-2 border-t">
          <Label className="text-xs font-bold text-foreground">رنگ و تایپوگرافی متن (Typography)</Label>
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
              placeholder="#000000 یا hsl(var(--foreground))"
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

          {/* Typography Details (Font Size, Weight, Alignment) */}
          <div className="grid grid-cols-2 gap-2 pt-2 border-t border-border/40">
            <div className="space-y-1">
              <Label className="text-[10px] text-muted-foreground">اندازه قلم (Font Size)</Label>
              <Input
                type="number"
                min={8}
                max={96}
                value={currentDeviceStyle.typography?.fontSize?.value || 16}
                onChange={(e) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      fontSize: { value: parseFloat(e.target.value) || 16, unit: "px" },
                    },
                  })
                }
                className="h-7 text-xs"
              />
            </div>

            <div className="space-y-1">
              <Label className="text-[10px] text-muted-foreground">وزن قلم (Font Weight)</Label>
              <Select
                value={currentDeviceStyle.typography?.fontWeight || "inherit"}
                onValueChange={(val: any) =>
                  handleDeviceStyleChange({
                    typography: {
                      ...currentDeviceStyle.typography,
                      fontWeight: val === "inherit" ? null : val,
                    },
                  })
                }
              >
                <SelectTrigger className="h-7 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="inherit">ارث‌بری (Inherit)</SelectItem>
                  <SelectItem value="300">۳۰۰ (نازک - Light)</SelectItem>
                  <SelectItem value="400">۴۰۰ (عادی - Regular)</SelectItem>
                  <SelectItem value="500">۵۰۰ (متوسط - Medium)</SelectItem>
                  <SelectItem value="600">۶۰۰ (نیمه‌پررنگ - SemiBold)</SelectItem>
                  <SelectItem value="700">۷۰۰ (پررنگ - Bold)</SelectItem>
                  <SelectItem value="800">۸۰۰ (خیلی پررنگ - ExtraBold)</SelectItem>
                  <SelectItem value="900">۹۰۰ (سیاه - Black)</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-1 pt-1.5">
            <Label className="text-[10px] text-muted-foreground">ترازبندی افقی متن (Text Align)</Label>
            <div className="grid grid-cols-4 gap-1">
              {[
                { label: "راست", val: "right" },
                { label: "وسط", val: "center" },
                { label: "چپ", val: "left" },
                { label: "هم‌تراز", val: "justify" },
              ].map((al) => (
                <button
                  key={al.val}
                  type="button"
                  onClick={() =>
                    handleDeviceStyleChange({
                      typography: {
                        ...currentDeviceStyle.typography,
                        textAlign: al.val as any,
                      },
                    })
                  }
                  className={cn(
                    "py-1 rounded text-[11px] font-semibold border transition",
                    currentDeviceStyle.typography?.textAlign === al.val
                      ? "bg-primary text-primary-foreground border-primary"
                      : "bg-muted/60 text-muted-foreground hover:text-foreground border-border/60"
                  )}
                >
                  {al.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Border Style, Width, Color & Radius (Elementor Parity) */}
        <div className="space-y-2 pt-2 border-t">
          <div className="flex items-center justify-between">
            <Label className="text-xs font-bold text-foreground">نوع و حاشیه کادر (Border)</Label>
            <Select
              value={currentDeviceStyle.border?.style || "none"}
              onValueChange={(val: any) =>
                handleDeviceStyleChange({
                  border: {
                    ...currentDeviceStyle.border,
                    style: val,
                    color: currentDeviceStyle.border?.color || "var(--border)",
                  },
                })
              }
            >
              <SelectTrigger className="h-7 text-xs w-28">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">بدون حاشیه</SelectItem>
                <SelectItem value="solid">یکپارچه (Solid)</SelectItem>
                <SelectItem value="dashed">خط‌چین (Dashed)</SelectItem>
                <SelectItem value="dotted">نقطه‌چین (Dotted)</SelectItem>
                <SelectItem value="double">دوتایی (Double)</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {currentDeviceStyle.border?.style && currentDeviceStyle.border.style !== "none" && (
            <div className="grid grid-cols-2 gap-2 pt-1">
              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">ضخامت حاشیه (px)</Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={currentDeviceStyle.border.width?.top?.value || 1}
                  onChange={(e) => {
                    const w = parseFloat(e.target.value) || 1;
                    handleDeviceStyleChange({
                      border: {
                        ...currentDeviceStyle.border!,
                        width: {
                          top: { value: w, unit: "px" },
                          right: { value: w, unit: "px" },
                          bottom: { value: w, unit: "px" },
                          left: { value: w, unit: "px" },
                          isLinked: true,
                        },
                      },
                    });
                  }}
                  className="h-7 text-xs"
                />
              </div>

              <div className="space-y-1">
                <Label className="text-[10px] text-muted-foreground">رنگ حاشیه</Label>
                <div className="flex items-center gap-1.5">
                  <input
                    type="color"
                    value={toValidHexColor(currentDeviceStyle.border.color, "#e4e4e7")}
                    onChange={(e) =>
                      handleDeviceStyleChange({
                        border: {
                          ...currentDeviceStyle.border!,
                          color: e.target.value,
                        },
                      })
                    }
                    className="w-6 h-6 rounded border cursor-pointer p-0.5"
                  />
                  <Input
                    value={currentDeviceStyle.border.color || ""}
                    placeholder="var(--border)"
                    onChange={(e) =>
                      handleDeviceStyleChange({
                        border: {
                          ...currentDeviceStyle.border!,
                          color: e.target.value,
                        },
                      })
                    }
                    className="h-7 text-[11px] font-mono flex-1"
                    dir="ltr"
                  />
                </div>
              </div>
            </div>
          )}

          <div className="space-y-1.5 pt-1.5">
            <Label className="text-[11px] font-semibold text-foreground">شعاع گردی کادر (Border Radius)</Label>
            <div className="flex items-center gap-2">
              <Input
                value={(currentDeviceStyle.border as any)?.radiusToken || ""}
                placeholder="مثلاً 12px یا var(--radius)"
                onChange={(e) =>
                  handleDeviceStyleChange({
                    border: {
                      ...currentDeviceStyle.border,
                      style: currentDeviceStyle.border?.style || "none",
                      radiusToken: e.target.value,
                    } as any,
                  })
                }
                className="h-8 text-xs flex-1 font-mono"
                dir="ltr"
              />
            </div>
            <div className="flex flex-wrap gap-1 mt-1">
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
                        style: currentDeviceStyle.border?.style || "none",
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

            <div className="space-y-1">
              <Label className="text-[10px] text-muted-foreground">ترتیب لایه عمقی (Z-Index: 0-999)</Label>
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
