"use client";

import React, { useCallback, useMemo, useState } from "react";
import {
  GripVertical,
  Copy,
  Trash2,
  Lock,
  EyeOff,
  Plus,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBuilderStore, findElementAndParent, type Breakpoint } from "@/stores/builder-store";
import { resolveResponsiveValue } from "@/lib/builder/schema";
import { BASIC_BLOCK_DEFINITIONS, createPatternElement } from "@/lib/builder/block-registry";
import { blockPatternsApi } from "@/lib/api/block-patterns";
import type { BuilderElement, DeviceStyle, ResponsiveStyles } from "@/types/builder";

interface CanvasElementProps {
  element: BuilderElement;
  activeBreakpoint: Breakpoint;
  depth?: number;
}

export function CanvasElement({
  element,
  activeBreakpoint,
  depth = 1,
}: CanvasElementProps) {
  const [isExternalDragOver, setIsExternalDragOver] = useState(false);
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const hoveredElementId = useBuilderStore((s) => s.hoveredElementId);
  const selectElement = useBuilderStore((s) => s.selectElement);
  const setHoveredElement = useBuilderStore((s) => s.setHoveredElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const addElement = useBuilderStore((s) => s.addElement);
  const moveElement = useBuilderStore((s) => s.moveElement);
  const ast = useBuilderStore((s) => s.ast);
  const previewMode = useBuilderStore((s) => s.previewMode);

  const isSelected = selectedElementId === element.id;
  const isHovered = hoveredElementId === element.id && !isSelected;

  // Drag is native HTML5 drag-and-drop, not dnd-kit. The canvas lives in an
  // iframe, and dnd-kit's pointer sensor never activates across the document
  // boundary (the sensor attaches its move/up listeners to one document while
  // the draggable nodes live in the other), so dragging silently did nothing.
  // HTML5 drag events are dispatched by the browser into the iframe document
  // and bubble normally — the same mechanism the palette→canvas drop uses.
  const [isDragOver, setIsDragOver] = useState(false);

  const readPayload = (e: React.DragEvent) => {
    const raw = e.dataTransfer.getData("application/json");
    if (!raw) return null;
    try {
      return JSON.parse(raw) as
        | { type: "block_def"; blockType: string }
        | { type: "pattern_def"; patternSlug: string; title: string; category: string; html?: string }
        | { type: "element"; elementId: string };
    } catch {
      return null;
    }
  };

  const onDragOver = useCallback(
    (e: React.DragEvent) => {
      if (previewMode) return;
      e.preventDefault();
      e.stopPropagation();
      e.dataTransfer.dropEffect = "move";
      setIsDragOver(true);
    },
    [previewMode]
  );

  const onDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const onDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);
      const payload = readPayload(e);
      if (!payload) return;

      if (payload.type === "element") {
        // Reordering / moving an existing element.
        if (payload.elementId !== element.id) {
          moveElement(payload.elementId, element.id);
        }
        return;
      }

      if (payload.type === "pattern_def") {
        const renderedHtml = payload.html || (await blockPatternsApi.render(payload.patternSlug, {})).html;
        const newEl = createPatternElement(
          { slug: payload.patternSlug, title: payload.title, category: payload.category },
          renderedHtml
        );
        if (element.type === "container") {
          addElement(newEl, element.id);
        } else {
          const info = findElementAndParent(ast.rootElements, element.id);
          addElement(newEl, info?.parent?.id, (info?.index ?? 0) + 1);
        }
        return;
      }

      if (payload.type === "block_def" && payload.blockType) {
        const def = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === payload.blockType);
        if (!def) return;
        const newEl = def.createDefaultElement();
        if (element.type === "container") {
          addElement(newEl, element.id);
        } else {
          const info = findElementAndParent(ast.rootElements, element.id);
          addElement(newEl, info?.parent?.id, (info?.index ?? 0) + 1);
        }
      }
    },
    [element.id, element.type, ast.rootElements, addElement, moveElement]
  );

  // Compute responsive inline styles based on active breakpoint
  const elementStyles = useMemo((): React.CSSProperties => {
    const res = element.styles;
    if (!res) return {};

    const styleObj: React.CSSProperties = {};
    const base = res.mobile;
    const tablet = res.tablet;
    const desktop = res.desktop;

    // Helper for box spacing
    const resolvePadding = () => {
      const p = resolveResponsiveValue({ mobile: base?.padding, tablet: tablet?.padding, desktop: desktop?.padding }, activeBreakpoint);
      if (p) {
        return `${p.top.value}${p.top.unit} ${p.right.value}${p.right.unit} ${p.bottom.value}${p.bottom.unit} ${p.left.value}${p.left.unit}`;
      }
      return undefined;
    };

    const resolveMargin = () => {
      const m = resolveResponsiveValue({ mobile: base?.margin, tablet: tablet?.margin, desktop: desktop?.margin }, activeBreakpoint);
      if (m) {
        return `${m.top.value}${m.top.unit} ${m.right.value}${m.right.unit} ${m.bottom.value}${m.bottom.unit} ${m.left.value}${m.left.unit}`;
      }
      return undefined;
    };

    const pad = resolvePadding();
    if (pad) styleObj.padding = pad;

    const mar = resolveMargin();
    if (mar) styleObj.margin = mar;

    const width = resolveResponsiveValue({ mobile: base?.width, tablet: tablet?.width, desktop: desktop?.width }, activeBreakpoint);
    if (width) styleObj.width = `${width.value}${width.unit}`;

    const minHeight = resolveResponsiveValue({ mobile: base?.minHeight, tablet: tablet?.minHeight, desktop: desktop?.minHeight }, activeBreakpoint);
    if (minHeight) styleObj.minHeight = `${minHeight.value}${minHeight.unit}`;

    const opacity = resolveResponsiveValue({ mobile: base?.opacity, tablet: tablet?.opacity, desktop: desktop?.opacity }, activeBreakpoint);
    if (opacity !== undefined && opacity !== null) styleObj.opacity = opacity;

    // Typography
    const fontObj = resolveResponsiveValue({ mobile: base?.typography, tablet: tablet?.typography, desktop: desktop?.typography }, activeBreakpoint);
    if (fontObj) {
      if (fontObj.fontSize) styleObj.fontSize = `${fontObj.fontSize.value}${fontObj.fontSize.unit}`;
      if (fontObj.fontWeight && fontObj.fontWeight !== "inherit") styleObj.fontWeight = fontObj.fontWeight;
      if (fontObj.lineHeight) styleObj.lineHeight = `${fontObj.lineHeight.value}${fontObj.lineHeight.unit}`;
      if (fontObj.textAlign && fontObj.textAlign !== "inherit") styleObj.textAlign = fontObj.textAlign;
      if (fontObj.color) styleObj.color = fontObj.color;
    }

    // Border & Radius
    const borderObj = resolveResponsiveValue({ mobile: base?.border, tablet: tablet?.border, desktop: desktop?.border }, activeBreakpoint);
    if (borderObj) {
      if (borderObj.style !== "none") {
        styleObj.borderStyle = borderObj.style;
        if (borderObj.color) styleObj.borderColor = borderObj.color;
        if (borderObj.width) {
          styleObj.borderWidth = `${borderObj.width.top.value}${borderObj.width.top.unit}`;
        }
      }
      if (borderObj.radius) {
        const r = borderObj.radius;
        styleObj.borderRadius = `${r.top.value}${r.top.unit} ${r.right.value}${r.right.unit} ${r.bottom.value}${r.bottom.unit} ${r.left.value}${r.left.unit}`;
      }
    }

    // Background
    const bgObj = resolveResponsiveValue({ mobile: base?.background, tablet: tablet?.background, desktop: desktop?.background }, activeBreakpoint);
    if (bgObj) {
      if (bgObj.type === "color" && bgObj.color) {
        styleObj.backgroundColor = bgObj.color;
      } else if (bgObj.type === "gradient" && bgObj.gradient) {
        styleObj.backgroundImage = `linear-gradient(${bgObj.gradient.direction.replace("to-", "to ")}, ${bgObj.gradient.fromColor}, ${bgObj.gradient.toColor})`;
      } else if (bgObj.type === "image" && bgObj.imageUrl) {
        styleObj.backgroundImage = `url(${bgObj.imageUrl})`;
        styleObj.backgroundPosition = bgObj.position || "center";
        styleObj.backgroundSize = bgObj.size || "cover";
      }
    }

    return styleObj;
  }, [element.styles, activeBreakpoint]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!previewMode) {
        selectElement(element.id);
      }
    },
    [element.id, previewMode, selectElement]
  );

  const handleMouseEnter = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!previewMode) {
        setHoveredElement(element.id);
      }
    },
    [element.id, previewMode, setHoveredElement]
  );

  const handleMouseLeave = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!previewMode) {
        setHoveredElement(null);
      }
    },
    [previewMode, setHoveredElement]
  );

  if (element.isHidden && previewMode) {
    return null;
  }

  // ── Render Widget ─────────────────────────────────────────────────────────

  const renderWidgetContent = () => {
    const props = element.widgetProps || {};
    switch (element.widgetType) {
      case "heading": {
        const Tag = (props.tag as "h1" | "h2" | "h3" | "h4" | "h5" | "h6") || "h2";
        return (
          <Tag className="font-bold tracking-tight text-foreground m-0">
            {String(props.text || "عنوان سرتیتر")}
          </Tag>
        );
      }
      case "text_editor": {
        return (
          <div
            className="prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed"
            dangerouslySetInnerHTML={{
              __html: String(props.content || "<p>متن پاراگراف را بنویسید...</p>"),
            }}
          />
        );
      }
      case "button": {
        return (
          <div className="inline-block">
            <span className="inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground shadow-sm transition">
              {String(props.label || "دکمه اقدام")}
            </span>
          </div>
        );
      }
      case "image": {
        return (
          <div className="relative overflow-hidden rounded-xl bg-muted/30">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={String(props.url || "/placeholder-hero.svg")}
              alt={String(props.alt || "تصویر شاخص")}
              className="h-auto max-w-full rounded-xl object-cover"
            />
          </div>
        );
      }
      case "spacer": {
        const h = Number(props.height || 32);
        return (
          <div
            className="w-full flex items-center justify-center border border-dashed border-muted-foreground/20 rounded text-xs text-muted-foreground select-none"
            style={{ height: `${h}px` }}
          >
            فاصله‌ساز ({h}px)
          </div>
        );
      }
      case "divider": {
        return <hr className="w-full border-border/80 my-4" />;
      }
      default:
        return (
          <div className="rounded-lg border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
            ویجت {element.widgetType || "سفارشی"}
          </div>
        );
    }
  };

  // ── Render Container Layout ───────────────────────────────────────────────

  const isContainer = element.type === "container";
  const layout = element.layout;

  const containerClasses = cn(
    "relative transition-all duration-150 w-full",
    isContainer && layout?.kind === "grid" && "grid",
    isContainer && layout?.kind === "grid" && layout.gridColumns === 1 && "grid-cols-1",
    isContainer && layout?.kind === "grid" && layout.gridColumns === 2 && "grid-cols-1 md:grid-cols-2",
    isContainer && layout?.kind === "grid" && layout.gridColumns === 3 && "grid-cols-1 md:grid-cols-2 lg:grid-cols-3",
    isContainer && layout?.kind === "grid" && layout.gridColumns >= 4 && "grid-cols-1 sm:grid-cols-2 lg:grid-cols-4",
    isContainer && (!layout?.kind || layout?.kind === "flex") && "flex",
    isContainer && layout?.direction === "column" && "flex-col",
    isContainer && layout?.direction === "row" && "flex-row",
    isContainer && layout?.direction === "row-reverse" && "flex-row-reverse",
    isContainer && layout?.direction === "column-reverse" && "flex-col-reverse",
    isContainer && layout?.justifyContent === "center" && "justify-center",
    isContainer && layout?.justifyContent === "between" && "justify-between",
    isContainer && layout?.justifyContent === "end" && "justify-end",
    isContainer && layout?.justifyContent === "start" && "justify-start",
    isContainer && layout?.alignItems === "center" && "items-center",
    isContainer && layout?.alignItems === "start" && "items-start",
    isContainer && layout?.alignItems === "end" && "items-end"
  );

  return (
    <div
      style={elementStyles}
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={cn(
        "relative group/elem select-none",
        isContainer ? containerClasses : "block",
        !previewMode && "outline outline-1 outline-transparent transition-all",
        !previewMode && isHovered && "outline-dashed outline-sky-500/80 bg-sky-500/5",
        !previewMode && isSelected && "outline-2 outline-primary bg-primary/5 shadow-sm z-20",
        !previewMode && isDragOver && "outline-2 outline-emerald-500 bg-emerald-500/10 shadow-lg ring-2 ring-emerald-500/30",
        element.isHidden && "opacity-50"
      )}
      data-element-id={element.id}
    >
      {/* Floating Action Toolbar on Selected Element */}
      {!previewMode && isSelected && (
        <div
          className="absolute -top-7 start-0 flex items-center gap-1 bg-primary text-primary-foreground text-[11px] font-bold rounded-t-md px-2 py-0.5 shadow-md z-30 pointer-events-auto"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Drag Handle — native HTML5 drag (see the note above onDrop). */}
          <span
            draggable={!element.isLocked}
            onDragStart={(e) => {
              e.stopPropagation();
              e.dataTransfer.setData(
                "application/json",
                JSON.stringify({ type: "element", elementId: element.id })
              );
              e.dataTransfer.effectAllowed = "move";
            }}
            className="cursor-grab active:cursor-grabbing p-0.5 hover:bg-primary-foreground/20 rounded"
            title="جابه‌جایی"
          >
            <GripVertical className="w-3.5 h-3.5" />
          </span>

          <span>{element.name}</span>

          {element.isLocked && <Lock className="w-3 h-3 text-amber-300" />}
          {element.isHidden && <EyeOff className="w-3 h-3 text-slate-300" />}

          <div className="flex items-center gap-0.5 ms-2 border-s border-primary-foreground/30 ps-1">
            <button
              type="button"
              onClick={() => duplicateElement(element.id)}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="تکثیر (Duplicate)"
            >
              <Copy className="w-3 h-3" />
            </button>
            <button
              type="button"
              onClick={() => deleteElement(element.id)}
              className="p-1 hover:bg-destructive text-destructive-foreground hover:text-white rounded transition"
              title="حذف"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        </div>
      )}

      {/* Content Rendering */}
      {isContainer ? (
        element.children && element.children.length > 0 ? (
          element.children.map((child) => (
            <CanvasElement
              key={child.id}
              element={child}
              activeBreakpoint={activeBreakpoint}
              depth={depth + 1}
            />
          ))
        ) : (
          !previewMode && (
            <div className="flex flex-col items-center justify-center p-8 border-2 border-dashed border-border/80 rounded-xl bg-card/40 text-center w-full min-h-[120px]">
              <span className="text-xs font-semibold text-muted-foreground mb-1">
                کانتینر خالی
              </span>
              <span className="text-[11px] text-muted-foreground/70">
                بلوک‌ها را از پنل سمت چپ به اینجا بکشید یا کلیک کنید
              </span>
            </div>
          )
        )
      ) : (
        renderWidgetContent()
      )}
    </div>
  );
}
