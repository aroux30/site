"use client";

import React, { useState } from "react";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { normalizeCssColor, toValidHexColor } from "@/lib/builder/color-utils";
import { SHAPE_DIVIDER_OPTIONS } from "@/lib/builder/shape-dividers";
import {
  composeCssFilterString,
  parseCssFilterString,
  type CssFilterValues,
} from "@/lib/builder/motion-runtime";
import type {
  BorderStyle,
  DeviceStyle,
  MotionEffectsStyle,
  ResponsiveStyles,
  UnitType,
  UnitValue,
} from "@/types/builder";

const BLEND_MODES = [
  { value: "normal", label: "عادی (Normal)" },
  { value: "multiply", label: "ضرب (Multiply)" },
  { value: "screen", label: "روشن‌سازی (Screen)" },
  { value: "overlay", label: "روپوش (Overlay)" },
  { value: "darken", label: "تیره (Darken)" },
  { value: "lighten", label: "روشن (Lighten)" },
  { value: "color-dodge", label: "تغییر رنگ روشن (Color Dodge)" },
  { value: "soft-light", label: "نور نرم (Soft Light)" },
  { value: "luminosity", label: "درخشندگی (Luminosity)" },
];

export function UnitSelect({
  value,
  onChange,
  units = ["px", "em", "rem", "%"],
  testId,
}: {
  value?: UnitType;
  onChange: (unit: UnitType) => void;
  units?: UnitType[];
  testId?: string;
}) {
  return (
    <select
      data-testid={testId}
      value={value || "px"}
      onChange={(e) => onChange(e.target.value as UnitType)}
      className="h-6 px-1 rounded border border-input bg-background text-[10px] font-mono text-muted-foreground hover:text-foreground outline-none focus:ring-1 focus:ring-primary"
      dir="ltr"
      aria-label="واحد اندازه‌گیری"
    >
      {units.map((u) => (
        <option key={u} value={u}>
          {u}
        </option>
      ))}
    </select>
  );
}

export function UnitNumberInput({
  label,
  value,
  onChange,
  units = ["px", "em", "rem", "%"],
  min,
  max,
  step = "any",
  placeholder,
  testId,
  unitTestId,
}: {
  label: string;
  value?: UnitValue | null;
  onChange: (next: UnitValue | undefined) => void;
  units?: UnitType[];
  min?: number;
  max?: number;
  step?: string | number;
  placeholder?: string;
  testId?: string;
  unitTestId?: string;
}) {
  const curUnit = value?.unit || units[0] || "px";
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between gap-1">
        <Label className="text-[11px] text-muted-foreground truncate">{label}</Label>
        <UnitSelect
          testId={unitTestId}
          value={curUnit}
          units={units}
          onChange={(u) =>
            onChange({
              value: value?.value ?? 0,
              unit: u,
            })
          }
        />
      </div>
      <Input
        data-testid={testId}
        type="number"
        min={min}
        max={max}
        step={step}
        value={value?.value ?? ""}
        placeholder={placeholder}
        onChange={(e) => {
          if (e.target.value === "") {
            onChange(undefined);
            return;
          }
          const num = parseFloat(e.target.value);
          if (!Number.isNaN(num)) {
            onChange({ value: num, unit: curUnit });
          }
        }}
        className="h-8 text-xs font-mono"
        dir="ltr"
      />
    </div>
  );
}

export function TypographyExtrasSection({
  typography,
  onChange,
}: {
  typography: DeviceStyle["typography"];
  onChange: (patch: Partial<NonNullable<DeviceStyle["typography"]>>) => void;
}) {
  const t = typography || {};
  // Parse shadow string `"x y blur color"` for optional visual controls
  const shadowParts = (t.textShadow || "").trim().match(/^(-?\d+(?:\.\d+)?)px\s+(-?\d+(?:\.\d+)?)px\s+(\d+(?:\.\d+)?)px\s+(.+)$/);
  const shX = shadowParts?.[1] ? Number(shadowParts[1]) : 0;
  const shY = shadowParts?.[2] ? Number(shadowParts[2]) : 2;
  const shBlur = shadowParts?.[3] ? Number(shadowParts[3]) : 4;
  const shCol = shadowParts?.[4] || "rgba(0,0,0,0.3)";

  const updateShadowParts = (x: number, y: number, blur: number, col: string) => {
    onChange({ textShadow: `${x}px ${y}px ${blur}px ${col}` });
  };

  return (
    <div className="space-y-3 pt-2 border-t border-border/40">
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">خانواده فونت (Family)</Label>
          <Select
            value={t.fontFamily || "inherit"}
            onValueChange={(val) => onChange({ fontFamily: val })}
          >
            <SelectTrigger data-testid="typography-fontfamily-select" className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="inherit">پیش‌فرض سایت</SelectItem>
              <SelectItem value="vazirmatn">وزیرمتن (Vazirmatn)</SelectItem>
              <SelectItem value="system-ui">سیستم (System UI)</SelectItem>
              <SelectItem value="monospace">مونواسپیس (Code)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">سبک فونت (Font Style)</Label>
          <Select
            value={t.fontStyle || "normal"}
            onValueChange={(val: any) => onChange({ fontStyle: val })}
          >
            <SelectTrigger data-testid="typography-fontstyle-select" className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="normal">عادی (Normal)</SelectItem>
              <SelectItem value="italic">مورب (Italic)</SelectItem>
              <SelectItem value="oblique">مایل (Oblique)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">تبدیل حروف (Transform)</Label>
          <Select
            value={t.textTransform || "none"}
            onValueChange={(val: any) => onChange({ textTransform: val })}
          >
            <SelectTrigger data-testid="typography-transform-select" className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">بدون تغییر</SelectItem>
              <SelectItem value="uppercase">بزرگ (UPPERCASE)</SelectItem>
              <SelectItem value="lowercase">کوچک (lowercase)</SelectItem>
              <SelectItem value="capitalize">حرف اول بزرگ (Capitalize)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">خط متن (Decoration)</Label>
          <Select
            value={t.textDecoration || "none"}
            onValueChange={(val: any) => onChange({ textDecoration: val })}
          >
            <SelectTrigger data-testid="typography-decoration-select" className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="none">بدون خط</SelectItem>
              <SelectItem value="underline">زیرخط (Underline)</SelectItem>
              <SelectItem value="overline">روخط (Overline)</SelectItem>
              <SelectItem value="line-through">خط‌خورده (Line Through)</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="grid grid-cols-3 gap-1.5">
        <UnitNumberInput
          label="ارتفاع خط"
          value={t.lineHeight}
          onChange={(lineHeight) => onChange({ lineHeight })}
          units={["em", "px", "rem"]}
          step="0.1"
          placeholder="1.5"
          testId="typography-lineheight-input"
          unitTestId="typography-lineheight-unit"
        />
        <UnitNumberInput
          label="فاصله حروف"
          value={t.letterSpacing}
          onChange={(letterSpacing) => onChange({ letterSpacing })}
          units={["px", "em", "rem"]}
          step="0.5"
          placeholder="0"
          testId="typography-letterspacing-input"
          unitTestId="typography-letterspacing-unit"
        />
        <UnitNumberInput
          label="فاصله کلمات"
          value={t.wordSpacing}
          onChange={(wordSpacing) => onChange({ wordSpacing })}
          units={["px", "em", "rem"]}
          step="0.5"
          placeholder="0"
          testId="typography-wordspacing-input"
          unitTestId="typography-wordspacing-unit"
        />
      </div>

      {/* Text Shadow Visual Sliders */}
      <div className="grid grid-cols-4 gap-1.5 pt-1">
        <div className="space-y-0.5">
          <span className="text-[10px] text-muted-foreground block">افقی X</span>
          <Input
            data-testid="text-shadow-x-input"
            type="number"
            value={shadowParts ? shX : ""}
            placeholder="0"
            onChange={(e) => updateShadowParts(parseFloat(e.target.value) || 0, shY, shBlur, shCol)}
            className="h-7 text-[11px] font-mono px-1.5"
            dir="ltr"
          />
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] text-muted-foreground block">عمودی Y</span>
          <Input
            data-testid="text-shadow-y-input"
            type="number"
            value={shadowParts ? shY : ""}
            placeholder="2"
            onChange={(e) => updateShadowParts(shX, parseFloat(e.target.value) || 0, shBlur, shCol)}
            className="h-7 text-[11px] font-mono px-1.5"
            dir="ltr"
          />
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] text-muted-foreground block">محوشدگی</span>
          <Input
            data-testid="text-shadow-blur-input"
            type="number"
            min={0}
            value={shadowParts ? shBlur : ""}
            placeholder="4"
            onChange={(e) => updateShadowParts(shX, shY, Math.max(0, parseFloat(e.target.value) || 0), shCol)}
            className="h-7 text-[11px] font-mono px-1.5"
            dir="ltr"
          />
        </div>
        <div className="space-y-0.5">
          <span className="text-[10px] text-muted-foreground block">رنگ سایه</span>
          <input
            data-testid="text-shadow-color-input"
            type="color"
            value={toValidHexColor(shCol, "#000000")}
            onChange={(e) => updateShadowParts(shX, shY, shBlur, e.target.value)}
            className="w-full h-7 rounded border border-input cursor-pointer p-0.5"
          />
        </div>
      </div>

      {/* Text Stroke (Elementor 3.5+ Parity) */}
      <div className="grid grid-cols-2 gap-2 pt-1.5 border-t border-border/40">
        <UnitNumberInput
          label="دورخط متن (Stroke)"
          value={t.textStroke}
          onChange={(textStroke) => onChange({ textStroke })}
          units={["px", "em", "rem"]}
          min={0}
          max={10}
          step="0.5"
          placeholder="0"
          testId="typography-text-stroke-input"
        />
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">رنگ دورخط</Label>
          <div className="flex items-center gap-1.5">
            <input
              type="color"
              value={toValidHexColor(t.textStrokeColor, "#000000")}
              onChange={(e) => onChange({ textStrokeColor: e.target.value })}
              className="w-8 h-8 rounded border border-input cursor-pointer p-0.5"
            />
            <Input
              data-testid="typography-text-stroke-color-input"
              value={t.textStrokeColor || ""}
              placeholder="#000000"
              onChange={(e) => onChange({ textStrokeColor: normalizeCssColor(e.target.value) || e.target.value })}
              className="h-8 text-xs font-mono flex-1"
              dir="ltr"
            />
          </div>
        </div>
      </div>
    </div>
  );
}

export function CssFilterSliders({
  value,
  onChange,
  testIdPrefix = "css-filter",
}: {
  value?: string | null;
  onChange: (nextFilter: string | undefined) => void;
  testIdPrefix?: string;
}) {
  const parsed = parseCssFilterString(value);
  const updateKey = (k: keyof CssFilterValues, num: number) => {
    const next = { ...parsed, [k]: num };
    onChange(composeCssFilterString(next));
  };

  const sliders: Array<{
    key: keyof CssFilterValues;
    label: string;
    min: number;
    max: number;
    step: number;
    unit: string;
  }> = [
    { key: "blur", label: "تاری (Blur)", min: 0, max: 10, step: 0.5, unit: "px" },
    { key: "brightness", label: "روشنایی (Brightness)", min: 0, max: 200, step: 5, unit: "%" },
    { key: "contrast", label: "کنتراست (Contrast)", min: 0, max: 200, step: 5, unit: "%" },
    { key: "saturate", label: "اشباع رنگ (Saturate)", min: 0, max: 200, step: 5, unit: "%" },
    { key: "hue", label: "چرخش طیف (Hue)", min: 0, max: 360, step: 5, unit: "deg" },
  ];

  return (
    <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
      {sliders.map((s) => (
        <div key={s.key} className="space-y-0.5">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-muted-foreground">{s.label}</span>
            <span className="font-mono text-foreground" dir="ltr">
              {parsed[s.key]}
              {s.unit}
            </span>
          </div>
          <input
            data-testid={`${testIdPrefix}-${s.key}-slider`}
            type="range"
            min={s.min}
            max={s.max}
            step={s.step}
            value={parsed[s.key]}
            onChange={(e) => updateKey(s.key, parseFloat(e.target.value))}
            className="w-full h-1.5 accent-primary cursor-pointer"
          />
        </div>
      ))}
    </div>
  );
}

export function HoverStateSection({
  currentDeviceStyle,
  onChange,
}: {
  currentDeviceStyle: DeviceStyle;
  onChange: (patch: Partial<DeviceStyle>) => void;
}) {
  const [subTab, setSubTab] = useState<"normal" | "hover">("normal");
  const activeBorder: BorderStyle =
    subTab === "hover"
      ? currentDeviceStyle.hoverBorder || { style: "none" }
      : currentDeviceStyle.border || { style: "none" };

  const updateBorder = (patch: Partial<BorderStyle>) => {
    const next = { ...activeBorder, ...patch } as BorderStyle;
    if (subTab === "hover") {
      onChange({ hoverBorder: next });
    } else {
      onChange({ border: next });
    }
  };

  // Visual Box Shadow helpers
  const curShadow =
    subTab === "hover" ? currentDeviceStyle.hoverBoxShadow || "" : currentDeviceStyle.boxShadow || "";
  const shadowM = curShadow
    .trim()
    .match(/^(-?\d+(?:\.\d+)?)px\s+(-?\d+(?:\.\d+)?)px\s+(\d+(?:\.\d+)?)px\s+(-?\d+(?:\.\d+)?)px\s+(inset\s+)?(.+)$/i);
  const bX = shadowM?.[1] ? Number(shadowM[1]) : 0;
  const bY = shadowM?.[2] ? Number(shadowM[2]) : 10;
  const bBlur = shadowM?.[3] ? Number(shadowM[3]) : 20;
  const bSpread = shadowM?.[4] ? Number(shadowM[4]) : 0;
  const bInset = shadowM ? Boolean(shadowM[5]) : false;
  const bColor = (shadowM?.[6] || "rgba(0,0,0,0.18)").trim();

  const setBoxShadowVal = (val: string | undefined) => {
    if (subTab === "hover") onChange({ hoverBoxShadow: val });
    else onChange({ boxShadow: val });
  };

  return (
    <div className="space-y-3 pt-2 border-t">
      <div className="flex items-center justify-between gap-1.5">
        <Label className="text-xs font-bold text-foreground shrink-0">کادر، سایه و هاور</Label>
        <div className="flex gap-1 text-[10px] bg-muted/60 p-0.5 rounded-md border border-border/60 shrink-0">
          <button
            type="button"
            data-testid="border-state-normal-tab"
            onClick={() => setSubTab("normal")}
            className={cn(
              "px-2 py-0.5 rounded transition",
              subTab === "normal"
                ? "bg-primary text-primary-foreground font-bold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            عادی (Normal)
          </button>
          <button
            type="button"
            data-testid="border-state-hover-tab"
            onClick={() => setSubTab("hover")}
            className={cn(
              "px-2 py-0.5 rounded transition",
              subTab === "hover"
                ? "bg-primary text-primary-foreground font-bold"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            هاور (Hover)
          </button>
        </div>
      </div>

      {/* Border style, width, color, radius */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-[11px] text-muted-foreground">نوع خط کادر ({subTab})</Label>
          <Select
            value={activeBorder.style || "none"}
            onValueChange={(val: any) => updateBorder({ style: val })}
          >
            <SelectTrigger data-testid={`border-style-${subTab}-select`} className="h-8 text-xs">
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
            data-testid={subTab === "normal" ? "border-width-input" : "hover-border-width-input"}
            type="number"
            min={0}
            max={24}
            value={activeBorder.width?.top?.value ?? 0}
            onChange={(e) => {
              const val = parseFloat(e.target.value) || 0;
              const prevStyle = activeBorder.style;
              const nextStyle = prevStyle && prevStyle !== "none" ? prevStyle : val > 0 ? "solid" : "none";
              updateBorder({
                style: nextStyle,
                width: {
                  top: { value: val, unit: "px" },
                  right: { value: val, unit: "px" },
                  bottom: { value: val, unit: "px" },
                  left: { value: val, unit: "px" },
                  isLinked: true,
                },
              });
            }}
            className="h-8 text-xs font-mono"
            dir="ltr"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-[11px] text-muted-foreground">رنگ کادر ({subTab})</Label>
        <div className="flex items-center gap-2">
          <input
            type="color"
            value={toValidHexColor(activeBorder.color, "#e4e4e7")}
            onChange={(e) =>
              updateBorder({
                style: activeBorder.style && activeBorder.style !== "none" ? activeBorder.style : "solid",
                color: e.target.value,
              })
            }
            className="w-8 h-8 rounded border border-input cursor-pointer p-0.5"
          />
          <Input
            data-testid={subTab === "normal" ? "border-color-input" : "hover-border-color-input"}
            value={activeBorder.color || ""}
            placeholder="#e4e4e7 یا var(--border)"
            onChange={(e) =>
              updateBorder({
                style: activeBorder.style && activeBorder.style !== "none" ? activeBorder.style : "solid",
                color: normalizeCssColor(e.target.value) || e.target.value,
              })
            }
            className="h-8 text-xs flex-1 font-mono"
            dir="ltr"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label className="text-[11px] font-bold text-foreground">شعاع گردی کادر (Border Radius)</Label>
        <Input
          data-testid={subTab === "normal" ? "border-radius-input" : "hover-border-radius-input"}
          value={(activeBorder as any).radiusToken || ""}
          placeholder="مثلاً 12px یا var(--radius)"
          onChange={(e) => updateBorder({ style: activeBorder.style || "none", radiusToken: e.target.value })}
          className="h-8 text-xs font-mono"
          dir="ltr"
        />
        {subTab === "normal" && (
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
                onClick={() => updateBorder({ style: activeBorder.style || "none", radiusToken: tok.val })}
                className="px-2 py-0.5 rounded text-[10px] bg-muted/80 hover:bg-muted text-muted-foreground hover:text-foreground border border-border/60 transition"
              >
                {tok.label}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Structured Box Shadow Sliders + String */}
      <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
        <div className="flex items-center justify-between">
          <Label className="text-[11px] font-semibold">سایه کادر ({subTab})</Label>
          <select
            data-testid={`box-shadow-position-${subTab}`}
            value={bInset ? "inset" : "outline"}
            onChange={(e) => {
              const ins = e.target.value === "inset" ? "inset " : "";
              setBoxShadowVal(`${bX}px ${bY}px ${bBlur}px ${bSpread}px ${ins}${bColor}`);
            }}
            className="h-6 px-1.5 rounded border border-input bg-background text-[10px]"
          >
            <option value="outline">بیرونی (Outline)</option>
            <option value="inset">داخلی (Inset)</option>
          </select>
        </div>
        <div className="grid grid-cols-4 gap-1">
          {[
            { label: "H", val: bX, k: "x" },
            { label: "V", val: bY, k: "y" },
            { label: "Blur", val: bBlur, k: "blur" },
            { label: "Spread", val: bSpread, k: "spread" },
          ].map((item) => (
            <div key={item.k}>
              <span className="text-[9px] text-muted-foreground block text-center">{item.label}</span>
              <Input
                data-testid={`box-shadow-${item.k}-${subTab}-input`}
                type="number"
                value={shadowM ? item.val : ""}
                placeholder={String(item.val)}
                onChange={(e) => {
                  const v = parseFloat(e.target.value) || 0;
                  const nx = item.k === "x" ? v : bX;
                  const ny = item.k === "y" ? v : bY;
                  const nb = item.k === "blur" ? Math.max(0, v) : bBlur;
                  const ns = item.k === "spread" ? v : bSpread;
                  const ins = bInset ? "inset " : "";
                  setBoxShadowVal(`${nx}px ${ny}px ${nb}px ${ns}px ${ins}${bColor}`);
                }}
                className="h-7 text-[11px] font-mono px-1 text-center"
                dir="ltr"
              />
            </div>
          ))}
        </div>
        <div className="flex items-center gap-1.5">
          <input
            type="color"
            value={toValidHexColor(bColor, "#000000")}
            onChange={(e) => {
              const ins = bInset ? "inset " : "";
              setBoxShadowVal(`${bX}px ${bY}px ${bBlur}px ${bSpread}px ${ins}${e.target.value}`);
            }}
            className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
          />
          <Input
            data-testid={subTab === "normal" ? "box-shadow-input" : "hover-box-shadow-input"}
            value={curShadow}
            placeholder="0 10px 15px -3px rgba(0,0,0,0.1)"
            onChange={(e) => setBoxShadowVal(e.target.value.trim() || undefined)}
            className="h-7 text-[11px] font-mono flex-1"
            dir="ltr"
          />
        </div>
      </div>

      {/* Extra Hover Properties & Transition */}
      {subTab === "hover" && (
        <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
          <div className="space-y-1">
            <Label className="text-[11px] text-muted-foreground">رنگ پس‌زمینه در حالت هاور (Hover Background)</Label>
            <div className="flex items-center gap-2">
              <input
                type="color"
                value={toValidHexColor(currentDeviceStyle.hoverBackground?.color, "#10b981")}
                onChange={(e) =>
                  onChange({ hoverBackground: { type: "color", color: e.target.value } })
                }
                className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
              />
              <Input
                data-testid="hover-bg-color-input"
                value={currentDeviceStyle.hoverBackground?.color || ""}
                placeholder="#10b981 یا none"
                onChange={(e) =>
                  onChange({
                    hoverBackground: e.target.value.trim()
                      ? { type: "color", color: normalizeCssColor(e.target.value) || e.target.value }
                      : null,
                  })
                }
                className="h-7 text-xs font-mono flex-1"
                dir="ltr"
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label className="text-[11px] text-muted-foreground">فیلتر در حالت هاور (Hover Filter)</Label>
            <Input
              data-testid="hover-filter-input"
              value={currentDeviceStyle.hoverFilter || ""}
              placeholder="brightness(110%) contrast(105%)"
              onChange={(e) => onChange({ hoverFilter: e.target.value.trim() || undefined })}
              className="h-7 text-xs font-mono"
              dir="ltr"
            />
          </div>
        </div>
      )}

      <div className="flex items-center justify-between pt-1">
        <Label className="text-[11px] text-muted-foreground">مدت زمان گذار (Transition Duration)</Label>
        <div className="flex items-center gap-1.5 w-28">
          <Input
            data-testid="transition-duration-input"
            type="number"
            step="0.05"
            min={0}
            max={3}
            value={currentDeviceStyle.transitionDuration ?? 0.3}
            onChange={(e) => {
              const val = parseFloat(e.target.value);
              onChange({ transitionDuration: !Number.isNaN(val) ? val : 0.3 });
            }}
            className="h-7 text-xs font-mono"
            dir="ltr"
          />
          <span className="text-[10px] text-muted-foreground">ثانیه</span>
        </div>
      </div>
    </div>
  );
}

export function ShapeDividerGroup({
  styles,
  onUpdate,
}: {
  styles: ResponsiveStyles;
  onUpdate: (patch: Partial<ResponsiveStyles>) => void;
}) {
  const [side, setSide] = useState<"top" | "bottom">("top");
  const curShape = (side === "top" ? styles.shapeDividerTop : styles.shapeDividerBottom) || "none";
  const curColor =
    (side === "top" ? styles.shapeDividerTopColor : styles.shapeDividerBottomColor) ||
    styles.shapeDividerColor ||
    "#ffffff";
  const curWidth = (side === "top" ? styles.shapeDividerTopWidth : styles.shapeDividerBottomWidth) ?? 100;
  const curHeight = (side === "top" ? styles.shapeDividerTopHeight : styles.shapeDividerBottomHeight) ?? 48;
  const curFlip = (side === "top" ? styles.shapeDividerTopFlip : styles.shapeDividerBottomFlip) ?? false;

  return (
    <div className="space-y-3 pt-2 border-t">
      <div className="flex items-center justify-between gap-1.5">
        <Label className="text-xs font-bold text-foreground shrink-0">جداکننده شکل (۳۰ مدل)</Label>
        <div className="flex gap-1 text-[10px] bg-muted/60 p-0.5 rounded-md border border-border/60 shrink-0">
          <button
            type="button"
            data-testid="shape-divider-side-top"
            onClick={() => setSide("top")}
            className={cn(
              "px-2 py-0.5 rounded transition",
              side === "top" ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground"
            )}
          >
            بالا
          </button>
          <button
            type="button"
            data-testid="shape-divider-side-bottom"
            onClick={() => setSide("bottom")}
            className={cn(
              "px-2 py-0.5 rounded transition",
              side === "bottom" ? "bg-primary text-primary-foreground font-bold" : "text-muted-foreground"
            )}
          >
            پایین
          </button>
        </div>
      </div>

      {/* Render both Top and Bottom selects cleanly with preserved testids */}
      <div className="grid grid-cols-2 gap-2">
        <div className="space-y-1">
          <Label className="text-[10px] text-muted-foreground">شکل بالا (Top)</Label>
          <Select
            value={styles.shapeDividerTop || "none"}
            onValueChange={(val: string) => onUpdate({ shapeDividerTop: val === "none" ? null : val })}
          >
            <SelectTrigger data-testid="shape-divider-top-select" className="h-8 text-xs">
              <SelectValue placeholder="انتخاب شکل بالا" />
            </SelectTrigger>
            <SelectContent className="max-h-72">
              {SHAPE_DIVIDER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-[10px] text-muted-foreground">شکل پایین (Bottom)</Label>
          <Select
            value={styles.shapeDividerBottom || "none"}
            onValueChange={(val: string) => onUpdate({ shapeDividerBottom: val === "none" ? null : val })}
          >
            <SelectTrigger data-testid="shape-divider-bottom-select" className="h-8 text-xs">
              <SelectValue placeholder="انتخاب شکل پایین" />
            </SelectTrigger>
            <SelectContent className="max-h-72">
              {SHAPE_DIVIDER_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-2 p-2 rounded-lg border bg-muted/20">
        <div className="space-y-1">
          <Label className="text-[10px] text-muted-foreground">
            رنگ جداکننده ({side === "top" ? "بالا و پیش‌فرض" : "پایین"})
          </Label>
          <div className="flex items-center gap-2">
            <input
              type="color"
              value={toValidHexColor(curColor, "#ffffff")}
              onChange={(e) =>
                onUpdate(
                  side === "top"
                    ? { shapeDividerColor: e.target.value, shapeDividerTopColor: e.target.value }
                    : { shapeDividerBottomColor: e.target.value }
                )
              }
              className="w-7 h-7 rounded border border-input cursor-pointer p-0.5"
            />
            <Input
              data-testid="shape-divider-color-input"
              value={curColor}
              placeholder="#ffffff"
              onChange={(e) =>
                onUpdate(
                  side === "top"
                    ? { shapeDividerColor: e.target.value, shapeDividerTopColor: e.target.value }
                    : { shapeDividerBottomColor: e.target.value }
                )
              }
              className="h-7 text-xs font-mono flex-1"
              dir="ltr"
            />
          </div>
        </div>

        {curShape !== "none" && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div className="space-y-0.5">
                <Label className="text-[10px] text-muted-foreground">عرض (٪): {curWidth}%</Label>
                <Input
                  data-testid="shape-divider-width-input"
                  type="number"
                  min={100}
                  max={300}
                  value={curWidth}
                  onChange={(e) => {
                    const num = Math.max(100, Math.min(300, parseFloat(e.target.value) || 100));
                    onUpdate(side === "top" ? { shapeDividerTopWidth: num } : { shapeDividerBottomWidth: num });
                  }}
                  className="h-7 text-xs font-mono"
                  dir="ltr"
                />
              </div>
              <div className="space-y-0.5">
                <Label className="text-[10px] text-muted-foreground">ارتفاع (px): {curHeight}px</Label>
                <Input
                  data-testid="shape-divider-height-input"
                  type="number"
                  min={10}
                  max={500}
                  value={curHeight}
                  onChange={(e) => {
                    const num = Math.max(10, Math.min(500, parseFloat(e.target.value) || 48));
                    onUpdate(side === "top" ? { shapeDividerTopHeight: num } : { shapeDividerBottomHeight: num });
                  }}
                  className="h-7 text-xs font-mono"
                  dir="ltr"
                />
              </div>
            </div>
            <div className="flex items-center justify-between pt-1">
              <Label className="text-[11px] text-muted-foreground">قرینه افقی شکل (Flip)</Label>
              <Switch
                data-testid="shape-divider-flip-switch"
                checked={curFlip}
                onCheckedChange={(val) =>
                  onUpdate(side === "top" ? { shapeDividerTopFlip: val } : { shapeDividerBottomFlip: val })
                }
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export function StickyAndMotionSection({
  styles,
  currentDeviceStyle,
  onUpdateStyles,
  onChangeDeviceStyle,
}: {
  styles: ResponsiveStyles;
  currentDeviceStyle: DeviceStyle;
  onUpdateStyles: (patch: Partial<ResponsiveStyles>) => void;
  onChangeDeviceStyle: (patch: Partial<DeviceStyle>) => void;
}) {
  const stickyOn = styles.stickyOn || ["desktop", "tablet", "mobile"];
  const motion: MotionEffectsStyle = styles.motionEffects || {};

  const toggleStickyDevice = (dev: "desktop" | "tablet" | "mobile") => {
    const exists = stickyOn.includes(dev);
    const next = exists ? stickyOn.filter((d) => d !== dev) : [...stickyOn, dev];
    onUpdateStyles({ stickyOn: next.length > 0 ? next : [dev] });
  };

  return (
    <div className="space-y-4">
      {/* Blend Mode & Position Offsets */}
      {currentDeviceStyle.position &&
        currentDeviceStyle.position !== "inherit" &&
        currentDeviceStyle.position !== "static" && (
          <div className="p-2.5 rounded-lg border bg-muted/20 space-y-2">
            <Label className="text-[11px] font-bold text-foreground block">مختصات آفست (Position Offsets)</Label>
            <div className="grid grid-cols-2 gap-2">
              <UnitNumberInput
                label="بالا (Top)"
                value={currentDeviceStyle.top}
                onChange={(top) => onChangeDeviceStyle({ top })}
                units={["px", "%", "em", "rem", "vh"]}
                testId="offset-top-input"
              />
              <UnitNumberInput
                label="پایین (Bottom)"
                value={currentDeviceStyle.bottom}
                onChange={(bottom) => onChangeDeviceStyle({ bottom })}
                units={["px", "%", "em", "rem", "vh"]}
                testId="offset-bottom-input"
              />
              <UnitNumberInput
                label="راست (Right)"
                value={currentDeviceStyle.right}
                onChange={(right) => onChangeDeviceStyle({ right })}
                units={["px", "%", "em", "rem", "vw"]}
                testId="offset-right-input"
              />
              <UnitNumberInput
                label="چپ (Left)"
                value={currentDeviceStyle.left}
                onChange={(left) => onChangeDeviceStyle({ left })}
                units={["px", "%", "em", "rem", "vw"]}
                testId="offset-left-input"
              />
            </div>
          </div>
        )}

      {/* Element Mix Blend Mode */}
      <div className="space-y-1.5">
        <Label className="text-xs font-bold text-foreground">حالت ترکیب رنگی المان (Blend Mode)</Label>
        <Select
          value={currentDeviceStyle.mixBlendMode || "normal"}
          onValueChange={(val) => onChangeDeviceStyle({ mixBlendMode: val === "normal" ? undefined : val })}
        >
          <SelectTrigger data-testid="element-blend-mode-select" className="h-8 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {BLEND_MODES.map((m) => (
              <SelectItem key={m.value} value={m.value}>
                {m.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Elementor Pro Sticky Controls */}
      <div className="space-y-2.5 pt-2 border-t border-border/80">
        <Label className="text-xs font-bold text-foreground block">چسبندگی در اسکرول (Sticky - المنتور پرو)</Label>
        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-[10px] text-muted-foreground">وضعیت Sticky</Label>
            <Select
              value={styles.stickyMode || "none"}
              onValueChange={(val: any) =>
                onUpdateStyles({
                  stickyMode: val,
                  stickyOn: styles.stickyOn || ["desktop", "tablet", "mobile"],
                })
              }
            >
              <SelectTrigger data-testid="sticky-mode-select" className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">غیرفعال (None)</SelectItem>
                <SelectItem value="top">چسبان به بالا (Top)</SelectItem>
                <SelectItem value="bottom">چسبان به پایین (Bottom)</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1">
            <Label className="text-[10px] text-muted-foreground">فاصله از لبه (Offset px)</Label>
            <Input
              data-testid="sticky-offset-input"
              type="number"
              min={0}
              max={400}
              value={styles.stickyOffset ?? 0}
              onChange={(e) => onUpdateStyles({ stickyOffset: Math.max(0, parseInt(e.target.value, 10) || 0) })}
              className="h-8 text-xs font-mono"
              dir="ltr"
            />
          </div>
        </div>
        {styles.stickyMode && styles.stickyMode !== "none" && (
          <div className="flex items-center gap-1.5">
            <span className="text-[10px] text-muted-foreground">فعال در:</span>
            {(["desktop", "tablet", "mobile"] as const).map((dev) => {
              const active = stickyOn.includes(dev);
              return (
                <button
                  key={dev}
                  type="button"
                  data-testid={`sticky-on-${dev}`}
                  onClick={() => toggleStickyDevice(dev)}
                  className={cn(
                    "px-2 py-0.5 rounded text-[10px] border transition",
                    active
                      ? "bg-primary text-primary-foreground border-primary font-semibold"
                      : "bg-muted/50 text-muted-foreground border-border/60"
                  )}
                >
                  {dev === "desktop" ? "دسکتاپ" : dev === "tablet" ? "تبلت" : "موبایل"}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Elementor Pro Motion Effects (Scroll + Mouse) */}
      <div className="space-y-2.5 pt-2 border-t border-border/80">
        <Label className="text-xs font-bold text-foreground block">افکت‌های حرکتی و پارالاکس (Motion Effects)</Label>
        <div className="p-2.5 rounded-lg border bg-muted/20 space-y-2.5">
          <div className="flex items-center justify-between">
            <Label className="text-[11px]">پارالاکس عمودی با اسکرول (Vertical Scroll)</Label>
            <Switch
              data-testid="motion-parallax-switch"
              checked={Boolean(motion.scrollParallax)}
              onCheckedChange={(val) =>
                onUpdateStyles({ motionEffects: { ...motion, scrollParallax: val, parallaxSpeed: motion.parallaxSpeed ?? 4 } })
              }
            />
          </div>
          {motion.scrollParallax && (
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-muted-foreground">شدت پارالاکس: {motion.parallaxSpeed ?? 4}</span>
              <input
                data-testid="motion-parallax-speed"
                type="range"
                min={-10}
                max={10}
                step={1}
                value={motion.parallaxSpeed ?? 4}
                onChange={(e) =>
                  onUpdateStyles({ motionEffects: { ...motion, parallaxSpeed: Number(e.target.value) } })
                }
                className="w-32 h-1.5 accent-primary"
              />
            </div>
          )}

          <div className="flex items-center justify-between">
            <Label className="text-[11px]">بزرگ‌نمایی در اسکرول (Scroll Scale)</Label>
            <Switch
              data-testid="motion-scale-switch"
              checked={Boolean(motion.scrollScale)}
              onCheckedChange={(val) =>
                onUpdateStyles({ motionEffects: { ...motion, scrollScale: val, scrollScaleSpeed: motion.scrollScaleSpeed ?? 1.15 } })
              }
            />
          </div>

          <div className="flex items-center justify-between">
            <Label className="text-[11px]">محو/ظاهرشدن تدریجی (Scroll Transparency)</Label>
            <Switch
              data-testid="motion-opacity-switch"
              checked={Boolean(motion.scrollOpacity)}
              onCheckedChange={(val) => onUpdateStyles({ motionEffects: { ...motion, scrollOpacity: val } })}
            />
          </div>

          <div className="flex items-center justify-between pt-1 border-t border-border/40">
            <Label className="text-[11px]">تعقیب نشانگر ماوس (Mouse Track)</Label>
            <Switch
              data-testid="motion-mouse-switch"
              checked={Boolean(motion.mouseTrack)}
              onCheckedChange={(val) =>
                onUpdateStyles({ motionEffects: { ...motion, mouseTrack: val, mouseSpeed: motion.mouseSpeed ?? 3 } })
              }
            />
          </div>
          {motion.mouseTrack && (
            <div className="flex items-center justify-between gap-2">
              <span className="text-[10px] text-muted-foreground">سرعت ماوس: {motion.mouseSpeed ?? 3}</span>
              <input
                data-testid="motion-mouse-speed"
                type="range"
                min={1}
                max={10}
                step={1}
                value={motion.mouseSpeed ?? 3}
                onChange={(e) =>
                  onUpdateStyles({ motionEffects: { ...motion, mouseSpeed: Number(e.target.value) } })
                }
                className="w-32 h-1.5 accent-primary"
              />
            </div>
          )}
        </div>
      </div>

      {/* Elementor Pro Scoped Custom CSS */}
      <div className="space-y-1.5 pt-2 border-t border-border/80">
        <div className="flex items-center justify-between">
          <Label className="text-xs font-bold text-foreground">کد CSS اختصاصی ایزوله (Custom CSS - پرو)</Label>
          <span className="text-[10px] text-muted-foreground font-mono" dir="ltr">
            selector
          </span>
        </div>
        <p className="text-[11px] text-muted-foreground leading-relaxed">
          از <code className="text-primary font-bold">selector</code> یا{" "}
          <code className="text-primary font-bold">{"{{WRAPPER}}"}</code> برای استایل‌دهی ایزوله به همین المان بدون نشت به کل صفحه استفاده کنید.
        </p>
        <textarea
          data-testid="custom-css-textarea"
          rows={4}
          dir="ltr"
          placeholder={"selector {\n  border: 2px dashed #10b981;\n}\nselector:hover {\n  transform: scale(1.02);\n}"}
          value={styles.customCss || ""}
          onChange={(e) => onUpdateStyles({ customCss: e.target.value })}
          className="w-full rounded-md border border-input bg-background p-2 text-xs font-mono outline-none focus:ring-1 focus:ring-primary"
        />
      </div>
    </div>
  );
}

export { BLEND_MODES };
