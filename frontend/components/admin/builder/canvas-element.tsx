"use client";

import React, { useCallback, useMemo, useState, useRef, useEffect } from "react";
import {
  GripVertical,
  Copy,
  Trash2,
  Lock,
  EyeOff,
  Plus,
  BookmarkPlus,
  Globe,
  Palette,
  ShoppingCart,
  CheckSquare,
  CircleDot,
  ChevronDown,
  Folders,
  Hourglass,
  Video,
  Sparkles,
  Share2,
  Tag,
  Receipt,
  Minus,
  Check,
  ArrowUp,
  ArrowDown,
  RotateCw,
} from "lucide-react";
import { SaveTemplateDialog } from "./save-template-dialog";
import { cn } from "@/lib/utils";
import { useBuilderStore, findElementAndParent, cloneElementWithNewIds, type Breakpoint } from "@/stores/builder-store";
import { resolveResponsiveValue } from "@/lib/builder/schema";
import { BASIC_BLOCK_DEFINITIONS, createPatternElement } from "@/lib/builder/block-registry";
import { blockPatternsApi } from "@/lib/api/block-patterns";
import { ProductCard } from "@/components/store/product-card";
import { ImageGallery } from "@/components/store/image-gallery";
import { StarRating } from "@/components/ui/star-rating";
import { ReviewHistogram } from "@/components/store/review-histogram";
import { RecentlyViewed } from "@/components/store/recently-viewed";
import { MegaMenu } from "@/components/layout/mega-menu";
import { ContainerPresetPicker } from "./container-preset-picker";
import { Badge } from "@/components/ui/badge";
import { useCartStore } from "@/stores/cart-store";
import { useToast } from "@/components/ui/use-toast";
import { normalizeCssColor } from "@/lib/builder/color-utils";
import { getBuilderIcon } from "@/lib/builder/icon-map";
import type { BuilderElement, DeviceStyle, ResponsiveStyles } from "@/types/builder";

interface CanvasElementProps {
  element: BuilderElement;
  activeBreakpoint: Breakpoint;
  depth?: number;
}

function CanvasElementComponent({
  element,
  activeBreakpoint,
  depth = 1,
}: CanvasElementProps) {
  const { toast } = useToast();
  const [isExternalDragOver, setIsExternalDragOver] = useState(false);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [activeTabIdx, setActiveTabIdx] = useState(0);
  const [selectedVariantId, setSelectedVariantId] = useState<string>("var_1");
  const [cartQuantity, setCartQuantity] = useState(1);
  const [activeGridFilter, setActiveGridFilter] = useState<string>("all");
  const [isInlineEditing, setIsInlineEditing] = useState(false);
  const elementRef = useRef<HTMLDivElement>(null);
  const [isNearTop, setIsNearTop] = useState(false);

  // Performance-optimized fine-grained selectors (P5 Hardening):
  // Subscribe to boolean expressions instead of full AST tree, preventing cascade re-renders
  const isSelected = useBuilderStore((s) => s.selectedElementId === element.id || s.selectedElementIds.includes(element.id));
  const isHovered = useBuilderStore((s) => s.hoveredElementId === element.id && s.selectedElementId !== element.id);
  const selectElement = useBuilderStore((s) => s.selectElement);
  const toggleSelectElement = useBuilderStore((s) => s.toggleSelectElement);
  const setHoveredElement = useBuilderStore((s) => s.setHoveredElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const updateElementProps = useBuilderStore((s) => s.updateElementProps);

  // Dynamic clearance detection: check if element is near the canvas top
  useEffect(() => {
    if (!elementRef.current || !isSelected) return;
    const updateClearance = () => {
      if (elementRef.current) {
        const rect = elementRef.current.getBoundingClientRect();
        setIsNearTop(rect.top < 36);
      }
    };
    updateClearance();
    window.addEventListener("scroll", updateClearance, true);
    return () => window.removeEventListener("scroll", updateClearance, true);
  }, [isSelected]);
  const addElement = useBuilderStore((s) => s.addElement);
  const moveElement = useBuilderStore((s) => s.moveElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const makeGlobalComponent = useBuilderStore((s) => s.makeGlobalComponent);
  const previewMode = useBuilderStore((s) => s.previewMode);

  // Custom Attributes (Elementor Pro Parity)
  const customAttrs = useMemo(() => {
    const raw = element.styles?.customAttributes;
    if (!raw) return {};
    const parsed: Record<string, string> = {};
    const blacklist = new Set(["id", "class", "style", "data-element-id", "data-element-name"]);
    for (const line of raw.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || !trimmed.includes("|")) continue;
      const parts = trimmed.split("|");
      const k = parts[0]?.trim().toLowerCase();
      const v = parts.slice(1).join("|").trim();
      if (k && !blacklist.has(k) && !k.startsWith("on")) {
        parsed[k] = v;
      }
    }
    return parsed;
  }, [element.styles?.customAttributes]);

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
        | { type: "pattern_def"; patternSlug: string; title: string; category: string; html?: string; variables?: Record<string, string> }
        | { type: "template_def"; templateId: string; title: string; elements: BuilderElement[] }
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
      const isMove = e.dataTransfer.effectAllowed === "move";
      e.dataTransfer.dropEffect = isMove ? "move" : "copy";
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
          renderedHtml,
          payload.variables
        );
        const roots = useBuilderStore.getState().ast.rootElements;
        if (element.type === "container") {
          addElement(newEl, element.id);
        } else {
          const info = findElementAndParent(roots, element.id);
          addElement(newEl, info?.parent?.id, (info?.index ?? 0) + 1);
        }
        return;
      }

      if (payload.type === "template_def" && Array.isArray((payload as any).elements)) {
        const roots = useBuilderStore.getState().ast.rootElements;
        for (const el of (payload as any).elements) {
          const cloned = cloneElementWithNewIds(el);
          if (element.type === "container") {
            addElement(cloned, element.id);
          } else {
            const info = findElementAndParent(roots, element.id);
            addElement(cloned, info?.parent?.id, (info?.index ?? 0) + 1);
          }
        }
        return;
      }

      if (payload.type === "block_def" && payload.blockType) {
        const def = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === payload.blockType);
        if (!def) return;
        const newEl = def.createDefaultElement();
        const roots = useBuilderStore.getState().ast.rootElements;
        if (element.type === "container") {
          addElement(newEl, element.id);
        } else {
          const info = findElementAndParent(roots, element.id);
          addElement(newEl, info?.parent?.id, (info?.index ?? 0) + 1);
        }
      }
    },
    [element.id, element.type, addElement, moveElement]
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
        const top = p.top ? `${p.top.value}${p.top.unit}` : "0px";
        const right = p.right ? `${p.right.value}${p.right.unit}` : top;
        const bottom = p.bottom ? `${p.bottom.value}${p.bottom.unit}` : top;
        const left = p.left ? `${p.left.value}${p.left.unit}` : right;
        return `${top} ${right} ${bottom} ${left}`;
      }
      return undefined;
    };

    const resolveMargin = () => {
      const m = resolveResponsiveValue({ mobile: base?.margin, tablet: tablet?.margin, desktop: desktop?.margin }, activeBreakpoint);
      if (m) {
        const top = m.top ? `${m.top.value}${m.top.unit}` : "0px";
        const right = m.right ? `${m.right.value}${m.right.unit}` : top;
        const bottom = m.bottom ? `${m.bottom.value}${m.bottom.unit}` : top;
        const left = m.left ? `${m.left.value}${m.left.unit}` : right;
        return `${top} ${right} ${bottom} ${left}`;
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
      if (fontObj.color) styleObj.color = normalizeCssColor(fontObj.color);
      if (fontObj.fontFamily && fontObj.fontFamily !== "inherit") {
        styleObj.fontFamily = fontObj.fontFamily.startsWith("var(")
          ? fontObj.fontFamily
          : fontObj.fontFamily === "vazirmatn"
          ? "var(--font-vazirmatn, system-ui, sans-serif)"
          : fontObj.fontFamily;
      }
    }

    // Border & Radius
    const borderObj = resolveResponsiveValue({ mobile: base?.border, tablet: tablet?.border, desktop: desktop?.border }, activeBreakpoint);
    if (borderObj) {
      if (borderObj.style !== "none") {
        styleObj.borderStyle = borderObj.style;
        if (borderObj.color) styleObj.borderColor = normalizeCssColor(borderObj.color);
        if (borderObj.width) {
          styleObj.borderWidth = `${borderObj.width.top.value}${borderObj.width.top.unit}`;
        }
      }
      if ((borderObj as any).radiusToken) {
        styleObj.borderRadius = (borderObj as any).radiusToken;
      } else if (borderObj.radius) {
        const r = borderObj.radius;
        styleObj.borderRadius = `${r.top.value}${r.top.unit} ${r.right.value}${r.right.unit} ${r.bottom.value}${r.bottom.unit} ${r.left.value}${r.left.unit}`;
      }
    }

    // Background
    const bgObj = resolveResponsiveValue({ mobile: base?.background, tablet: tablet?.background, desktop: desktop?.background }, activeBreakpoint);
    if (bgObj) {
      if (bgObj.type === "color" && bgObj.color) {
        styleObj.backgroundColor = normalizeCssColor(bgObj.color);
      } else if (bgObj.type === "gradient" && bgObj.gradient) {
        const dirMap: Record<string, string> = {
          "to-r": "to right",
          "to-l": "to left",
          "to-b": "to bottom",
          "to-t": "to top",
          "to-tr": "to top right",
          "to-tl": "to top left",
        };
        const dir = dirMap[bgObj.gradient.direction] || "to right";
        styleObj.backgroundImage = `linear-gradient(${dir}, ${bgObj.gradient.fromColor}, ${bgObj.gradient.toColor})`;
      } else if (bgObj.type === "image" && bgObj.imageUrl) {
        styleObj.backgroundImage = `url(${bgObj.imageUrl})`;
        styleObj.backgroundPosition = bgObj.position || "center";
        styleObj.backgroundSize = bgObj.size || "cover";
        styleObj.backgroundRepeat = "no-repeat";
      }
    }

    // Box Shadow
    const shadow = resolveResponsiveValue({ mobile: base?.shadow || base?.boxShadow, tablet: tablet?.shadow || tablet?.boxShadow, desktop: desktop?.shadow || desktop?.boxShadow }, activeBreakpoint);
    if (shadow && shadow !== "none") {
      styleObj.boxShadow = shadow;
    }

    // CSS Filters & Backdrop Blur (Elementor Parity)
    const filter = resolveResponsiveValue({ mobile: base?.filter, tablet: tablet?.filter, desktop: desktop?.filter }, activeBreakpoint);
    if (filter && filter !== "none") {
      styleObj.filter = filter;
    }

    const backdropBlur = resolveResponsiveValue({ mobile: base?.backdropBlur, tablet: tablet?.backdropBlur, desktop: desktop?.backdropBlur }, activeBreakpoint);
    if (backdropBlur && backdropBlur !== "none") {
      const blurMap: Record<string, string> = {
        sm: "blur(4px)",
        md: "blur(8px)",
        lg: "blur(16px)",
        xl: "blur(24px)",
      };
      styleObj.backdropFilter = blurMap[backdropBlur] || `blur(${backdropBlur})`;
      (styleObj as any).WebkitBackdropFilter = styleObj.backdropFilter;
    }

    const filterBlur = resolveResponsiveValue({ mobile: base?.filterBlur, tablet: tablet?.filterBlur, desktop: desktop?.filterBlur }, activeBreakpoint);
    if (filterBlur && filterBlur > 0 && !filter) {
      styleObj.filter = `blur(${filterBlur}px)`;
    }

    // Animation styles
    const anim = res.animation || (res as any).entranceAnimation;
    if (anim && anim !== "none") {
      if (res.animationDuration) styleObj.animationDuration = `${res.animationDuration}s`;
      if (res.animationDelay) styleObj.animationDelay = `${res.animationDelay}s`;
    }

    // Transform & CSS Mask (Elementor Parity)
    const transform = resolveResponsiveValue({ mobile: base?.transform, tablet: tablet?.transform, desktop: desktop?.transform }, activeBreakpoint);
    if (transform) {
      const parts: string[] = [];
      if (transform.rotate) parts.push(`rotate(${transform.rotate}deg)`);
      if (transform.scale) parts.push(`scale(${transform.scale})`);
      if (transform.skewX) parts.push(`skewX(${transform.skewX}deg)`);
      if (transform.skewY) parts.push(`skewY(${transform.skewY}deg)`);
      if (transform.translateX || transform.translateY) {
        parts.push(`translate(${transform.translateX || 0}px, ${transform.translateY || 0}px)`);
      }
      if (parts.length > 0) {
        styleObj.transform = parts.join(" ");
      }
    }

    const mask = resolveResponsiveValue({ mobile: base?.mask, tablet: tablet?.mask, desktop: desktop?.mask }, activeBreakpoint);
    if (mask && mask.shape && mask.shape !== "none") {
      const maskVal = `url(/masks/${mask.shape}.svg)`;
      (styleObj as any).WebkitMaskImage = maskVal;
      (styleObj as any).maskImage = maskVal;
      (styleObj as any).WebkitMaskSize = mask.size || "contain";
      (styleObj as any).maskSize = mask.size || "contain";
      (styleObj as any).WebkitMaskRepeat = "no-repeat";
      (styleObj as any).maskRepeat = "no-repeat";
      (styleObj as any).WebkitMaskPosition = mask.position || "center";
      (styleObj as any).maskPosition = mask.position || "center";
    }

    // Advanced Layout Controls (P4)
    const position = resolveResponsiveValue({ mobile: base?.position, tablet: tablet?.position, desktop: desktop?.position }, activeBreakpoint);
    if (position && position !== "inherit") styleObj.position = position as any;

    const top = resolveResponsiveValue({ mobile: base?.top, tablet: tablet?.top, desktop: desktop?.top }, activeBreakpoint);
    if (top) styleObj.top = `${top.value}${top.unit}`;

    const bottom = resolveResponsiveValue({ mobile: base?.bottom, tablet: tablet?.bottom, desktop: desktop?.bottom }, activeBreakpoint);
    if (bottom) styleObj.bottom = `${bottom.value}${bottom.unit}`;

    const left = resolveResponsiveValue({ mobile: base?.left, tablet: tablet?.left, desktop: desktop?.left }, activeBreakpoint);
    if (left) styleObj.left = `${left.value}${left.unit}`;

    const right = resolveResponsiveValue({ mobile: base?.right, tablet: tablet?.right, desktop: desktop?.right }, activeBreakpoint);
    if (right) styleObj.right = `${right.value}${right.unit}`;

    const zIndex = resolveResponsiveValue({ mobile: base?.zIndex, tablet: tablet?.zIndex, desktop: desktop?.zIndex }, activeBreakpoint);
    if (zIndex !== undefined && zIndex !== null) styleObj.zIndex = zIndex;

    const overflow = resolveResponsiveValue({ mobile: base?.overflow, tablet: tablet?.overflow, desktop: desktop?.overflow }, activeBreakpoint);
    if (overflow && overflow !== "inherit") styleObj.overflow = overflow as any;

    const display = resolveResponsiveValue({ mobile: base?.display, tablet: tablet?.display, desktop: desktop?.display }, activeBreakpoint);
    if (display && display !== "inherit") styleObj.display = display as any;

    const flexDirection = resolveResponsiveValue({ mobile: base?.flexDirection, tablet: tablet?.flexDirection, desktop: desktop?.flexDirection }, activeBreakpoint);
    if (flexDirection && flexDirection !== "inherit") styleObj.flexDirection = flexDirection as any;

    const justifyContent = resolveResponsiveValue({ mobile: base?.justifyContent, tablet: tablet?.justifyContent, desktop: desktop?.justifyContent }, activeBreakpoint);
    if (justifyContent && justifyContent !== "inherit") {
      const jcMap: Record<string, string> = { start: "flex-start", end: "flex-end", between: "space-between", around: "space-around", evenly: "space-evenly" };
      styleObj.justifyContent = (jcMap[justifyContent] || justifyContent) as any;
    }

    const alignItems = resolveResponsiveValue({ mobile: base?.alignItems, tablet: tablet?.alignItems, desktop: desktop?.alignItems }, activeBreakpoint);
    if (alignItems && alignItems !== "inherit") {
      const aiMap: Record<string, string> = { start: "flex-start", end: "flex-end" };
      styleObj.alignItems = (aiMap[alignItems] || alignItems) as any;
    }

    const alignSelf = resolveResponsiveValue({ mobile: base?.alignSelf, tablet: tablet?.alignSelf, desktop: desktop?.alignSelf }, activeBreakpoint);
    if (alignSelf && alignSelf !== "inherit") {
      const asMap: Record<string, string> = { start: "flex-start", end: "flex-end" };
      styleObj.alignSelf = (asMap[alignSelf] || alignSelf) as any;
    }

    const order = resolveResponsiveValue({ mobile: base?.order, tablet: tablet?.order, desktop: desktop?.order }, activeBreakpoint);
    if (order !== undefined && order !== null) {
      styleObj.order = order;
    }

    const flexGrow = resolveResponsiveValue({ mobile: base?.flexGrow, tablet: tablet?.flexGrow, desktop: desktop?.flexGrow }, activeBreakpoint);
    if (flexGrow !== undefined && flexGrow !== null) {
      styleObj.flexGrow = flexGrow;
    }

    const flexWrap = resolveResponsiveValue({ mobile: base?.flexWrap, tablet: tablet?.flexWrap, desktop: desktop?.flexWrap }, activeBreakpoint);
    if (flexWrap && flexWrap !== "inherit") styleObj.flexWrap = flexWrap as any;

    const gap = resolveResponsiveValue({ mobile: base?.gap, tablet: tablet?.gap, desktop: desktop?.gap }, activeBreakpoint);
    if (gap) {
      styleObj.gap = `${gap.value}${gap.unit}`;
    } else if (element.layout?.gap) {
      styleObj.gap = `${element.layout.gap.value}${element.layout.gap.unit}`;
    }

    const gridTemplateColumns = resolveResponsiveValue({ mobile: base?.gridTemplateColumns, tablet: tablet?.gridTemplateColumns, desktop: desktop?.gridTemplateColumns }, activeBreakpoint);
    if (gridTemplateColumns) styleObj.gridTemplateColumns = gridTemplateColumns;

    // Elementor Boxed Container Max-Width & Centering
    if (element.type === "container" && element.layout?.boxedWidth) {
      styleObj.maxWidth = `${element.layout.boxedWidth.value}${element.layout.boxedWidth.unit}`;
      styleObj.marginLeft = "auto";
      styleObj.marginRight = "auto";
    }

    return styleObj;
  }, [element.styles, element.layout, activeBreakpoint]);

  // Elementor Background Overlay calculation
  const overlayStyle = useMemo((): React.CSSProperties | null => {
    const res = element.styles;
    if (!res) return null;
    const base = res.mobile;
    const tablet = res.tablet;
    const desktop = res.desktop;

    const overlay = resolveResponsiveValue(
      { mobile: base?.backgroundOverlay, tablet: tablet?.backgroundOverlay, desktop: desktop?.backgroundOverlay },
      activeBreakpoint
    );
    if (!overlay || overlay.type === "none") return null;

    const s: React.CSSProperties = {
      position: "absolute",
      inset: 0,
      pointerEvents: "none",
      borderRadius: "inherit",
      zIndex: 0,
    };
    if (overlay.opacity !== undefined && overlay.opacity !== null) {
      s.opacity = overlay.opacity;
    }
    if (overlay.type === "color" && overlay.color) {
      s.backgroundColor = normalizeCssColor(overlay.color);
    } else if (overlay.type === "gradient" && overlay.gradient) {
      const dirMap: Record<string, string> = {
        "to-r": "to right",
        "to-l": "to left",
        "to-b": "to bottom",
        "to-t": "to top",
        "to-tr": "to top right",
        "to-tl": "to top left",
      };
      const dir = dirMap[overlay.gradient.direction] || "to bottom";
      s.backgroundImage = `linear-gradient(${dir}, ${overlay.gradient.fromColor}, ${overlay.gradient.toColor})`;
    }
    return s;
  }, [element.styles, activeBreakpoint]);

  const isHiddenOnActiveBreakpoint = useMemo(() => {
    const styles = element.styles as any;
    if (activeBreakpoint === "desktop" && (element.visibleOnDesktop === false || styles?.hideOnDesktop === true)) return true;
    if (activeBreakpoint === "tablet" && (element.visibleOnTablet === false || styles?.hideOnTablet === true)) return true;
    if (activeBreakpoint === "mobile" && (element.visibleOnMobile === false || styles?.hideOnMobile === true)) return true;
    return false;
  }, [activeBreakpoint, element.visibleOnDesktop, element.visibleOnTablet, element.visibleOnMobile, element.styles]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (!previewMode) {
        if (e.ctrlKey || e.metaKey || e.shiftKey) {
          toggleSelectElement(element.id, true);
        } else {
          selectElement(element.id);
        }
      }
    },
    [element.id, previewMode, selectElement, toggleSelectElement]
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

  if ((element.isHidden || isHiddenOnActiveBreakpoint) && previewMode) {
    return null;
  }

  // ── Render Widget ─────────────────────────────────────────────────────────

  const renderWidgetContent = () => {
    const props = element.widgetProps || {};
    switch (element.widgetType) {
      case "heading": {
        const Tag = (props.tag as "h1" | "h2" | "h3" | "h4" | "h5" | "h6") || "h2";
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        const textVal = String(props.text || "عنوان سرتیتر");

        if (isInlineEditing && !previewMode) {
          return (
            <Tag
              contentEditable
              suppressContentEditableWarning
              autoFocus
              data-testid="inline-text-editor"
              className={cn("font-bold tracking-tight text-foreground m-0 break-words [overflow-wrap:anywhere] outline-2 outline-primary bg-primary/10 rounded px-1 min-w-[60px]", customClass)}
              onBlur={(e) => {
                const newText = e.currentTarget.textContent?.trim() || "";
                if (newText && newText !== textVal) {
                  updateElementProps(element.id, { text: newText });
                }
                setIsInlineEditing(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  e.currentTarget.blur();
                } else if (e.key === "Escape") {
                  e.preventDefault();
                  e.currentTarget.textContent = textVal;
                  setIsInlineEditing(false);
                }
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {textVal}
            </Tag>
          );
        }

        return (
          <Tag
            onDoubleClick={(e) => {
              if (!previewMode) {
                e.stopPropagation();
                setIsInlineEditing(true);
              }
            }}
            title="دابل‌کلیک برای ویرایش مستقیم متن (Inline Editing)"
            className={cn("font-bold tracking-tight text-foreground m-0 break-words [overflow-wrap:anywhere]", customClass)}
          >
            {textVal}
          </Tag>
        );
      }
      case "text_editor":
      case "text":
      case "paragraph": {
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        const rawContent = String(props.content || props.text || "<p>متن پاراگراف را بنویسید...</p>");
        const hasTags = /<[a-z][\s\S]*>/i.test(rawContent);

        if (isInlineEditing && !previewMode) {
          return (
            <div
              contentEditable
              suppressContentEditableWarning
              autoFocus
              data-testid="inline-text-editor"
              className={cn("prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed break-words [overflow-wrap:anywhere] outline-2 outline-primary bg-primary/10 rounded p-1 min-h-[30px]", customClass)}
              onBlur={(e) => {
                const newContent = e.currentTarget.innerHTML || "";
                if (newContent && newContent !== rawContent) {
                  updateElementProps(element.id, { content: newContent });
                }
                setIsInlineEditing(false);
              }}
              onKeyDown={(e) => {
                if (e.key === "Escape") {
                  e.preventDefault();
                  e.currentTarget.innerHTML = rawContent;
                  setIsInlineEditing(false);
                }
              }}
              onClick={(e) => e.stopPropagation()}
              dangerouslySetInnerHTML={{ __html: rawContent }}
            />
          );
        }

        return (
          <div
            onDoubleClick={(e) => {
              if (!previewMode) {
                e.stopPropagation();
                setIsInlineEditing(true);
              }
            }}
            title="دابل‌کلیک برای ویرایش مستقیم متن (Inline Editing)"
            className={cn(
              "prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed break-words [overflow-wrap:anywhere] outline-none",
              customClass
            )}
          >
            {hasTags ? (
              <div dangerouslySetInnerHTML={{ __html: rawContent }} />
            ) : (
              <p className="m-0 leading-relaxed">{rawContent}</p>
            )}
          </div>
        );
      }
      case "button": {
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        const isFull = customClass.includes("w-full");
        const url = String(props.url || "#");
        const labelVal = String(props.label || "دکمه اقدام");

        if (isInlineEditing && !previewMode) {
          return (
            <div className={isFull ? "w-full block" : "inline-block"}>
              <span
                contentEditable
                suppressContentEditableWarning
                autoFocus
                data-testid="inline-text-editor"
                className={cn(
                  "inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground shadow-sm transition outline-2 outline-white",
                  isFull && "w-full",
                  customClass
                )}
                onBlur={(e) => {
                  const newLabel = e.currentTarget.textContent?.trim() || "";
                  if (newLabel && newLabel !== labelVal) {
                    updateElementProps(element.id, { label: newLabel });
                  }
                  setIsInlineEditing(false);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    e.currentTarget.blur();
                  } else if (e.key === "Escape") {
                    e.preventDefault();
                    e.currentTarget.textContent = labelVal;
                    setIsInlineEditing(false);
                  }
                }}
                onClick={(e) => e.stopPropagation()}
              >
                {labelVal}
              </span>
            </div>
          );
        }

        return (
          <div className={isFull ? "w-full block" : "inline-block"}>
            <a
              href={url}
              data-url={url}
              onDoubleClick={(e) => {
                if (!previewMode) {
                  e.stopPropagation();
                  setIsInlineEditing(true);
                }
              }}
              title="دابل‌کلیک برای ویرایش مستقیم متن دکمه"
              className={cn(
                "inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground shadow-sm transition",
                isFull && "w-full",
                customClass
              )}
            >
              <span>{labelVal}</span>
            </a>
          </div>
        );
      }
      case "image": {
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        return (
          <div className={cn("relative overflow-hidden rounded-xl bg-muted/30 min-h-[120px] w-full flex items-center justify-center", customClass)}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={String(props.url || "/placeholder-hero.svg")}
              alt={String(props.alt || "تصویر شاخص")}
              className={cn("h-auto max-w-full rounded-xl object-cover", customClass)}
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
        const dStyle = String(props.style || "solid");
        return (
          <hr
            className={cn(
              "w-full border-border/80 my-4",
              dStyle === "dashed" && "border-dashed",
              dStyle === "dotted" && "border-dotted"
            )}
          />
        );
      }
      case "html_custom":
      case "legacy_html": {
        const rawHtml = String(props.html || props.content || "");
        if (!rawHtml.trim()) {
          return (
            <div className="rounded-lg border border-dashed border-border p-4 text-center text-xs text-muted-foreground">
              بلوک HTML سفارشی (خالی)
            </div>
          );
        }
        return (
          <div
            className="builder-custom-html w-full"
            dangerouslySetInnerHTML={{ __html: rawHtml }}
          />
        );
      }
      case "icon": {
        const iconChar = String(props.icon || "★");
        return <span className="inline-block text-xl leading-none">{iconChar}</span>;
      }
      case "video": {
        const url = String(props.url || "");
        const vType = String(props.video_type || "aparat");
        const poster = props.poster ? String(props.poster) : undefined;
        return (
          <div className="aspect-video w-full rounded-2xl overflow-hidden bg-black/10 border border-border/80 flex items-center justify-center">
            {url ? (
              vType === "aparat" || vType === "youtube" ? (
                <iframe src={url} className="w-full h-full border-0 pointer-events-none" allowFullScreen title="ویدیو" />
              ) : (
                <video src={url} controls poster={poster} className="w-full h-full object-cover" />
              )
            ) : (
              <div className="flex flex-col items-center gap-1.5 text-muted-foreground">
                <Video className="w-6 h-6" />
                <span className="text-xs">پخش‌کننده ویدئو (آدرس ویدئو را در بازرس وارد کنید)</span>
              </div>
            )}
          </div>
        );
      }
      case "product_card": {
        const prod = {
          id: String(props.id || "preview_prod_1"),
          name: String(props.name || "هدفون بی‌سیم پرو مکس"),
          slug: String(props.slug || "wireless-headphones"),
          category_id: "",
          is_active: true,
          is_featured: Boolean(props.is_featured),
          is_in_stock: props.is_in_stock !== false,
          min_price: Number(props.min_price) || 1850000,
          max_price: Number(props.max_price) || 2200000,
          variant_count: Number(props.variant_count) || 1,
          primary_image_url: String(props.primary_image_url || "/placeholder-hero.svg"),
          rating_average: Number(props.rating_average) || 4.6,
          review_count: Number(props.review_count) || 38,
        };
        return (
          <div className="w-full max-w-sm">
            <ProductCard product={prod as any} variant={(props.variant as any) || "default"} />
          </div>
        );
      }
      case "product_grid":
      case "loop_grid": {
        const limit = Number(props.limit) || 4;
        const filter = String(props.filter || "all");
        const showPagination = props.show_pagination !== false;

        const sampleProducts = Array.from({ length: limit }, (_, i) => ({
          id: `grid_prod_${i + 1}`,
          name: `کالای نمونه شماره ${i + 1}`,
          slug: `product-${i + 1}`,
          category_id: "",
          is_active: true,
          is_featured: i === 0 || filter === "featured",
          is_in_stock: true,
          min_price: (i + 1) * 350000,
          max_price: (i + 1) * 420000,
          variant_count: 1,
          primary_image_url: "/placeholder-hero.svg",
          rating_average: 4.5,
          review_count: 15 + i * 4,
        }));
        return (
          <div className="space-y-4 w-full">
            {/* Filter Pills */}
            <div className="flex items-center gap-1.5 pb-1">
              {[
                { key: "all", label: "همه محصولات" },
                { key: "featured", label: "ویژه" },
                { key: "best_sellers", label: "پرفروش‌ترین‌ها" },
                { key: "new_arrivals", label: "جدیدترین‌ها" },
              ].map((f) => (
                <button
                  key={f.key}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveGridFilter(f.key);
                  }}
                  className={cn(
                    "px-3 py-1 rounded-lg text-xs font-semibold transition",
                    activeGridFilter === f.key
                      ? "bg-primary text-primary-foreground shadow-sm"
                      : "bg-muted/60 text-muted-foreground hover:text-foreground"
                  )}
                >
                  {f.label}
                </button>
              ))}
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 w-full">
              {sampleProducts.map((p) => (
                <ProductCard key={p.id} product={p as any} variant="compact" />
              ))}
            </div>

            {showPagination && (
              <div className="text-center pt-2">
                <button
                  type="button"
                  className="px-5 py-2 rounded-xl border border-primary text-xs font-bold text-primary hover:bg-primary/5 transition"
                >
                  مشاهده محصولات بیشتر (Load More)
                </button>
              </div>
            )}
          </div>
        );
      }
      case "image_gallery": {
        const images = Array.isArray(props.images) && props.images.length > 0
          ? (props.images as any[])
          : [
              { url: "/placeholder-hero.svg", alt: "تصویر ۱" },
              { url: "/placeholder.svg", alt: "تصویر ۲" },
            ];
        return (
          <div className="w-full max-w-md mx-auto">
            <ImageGallery images={images} productName={String(props.productName || "محصول نمونه")} />
          </div>
        );
      }
      case "star_rating": {
        return (
          <div className="inline-flex items-center gap-2 p-2 rounded-lg bg-card border">
            <StarRating
              value={Number(props.value) || 4.8}
              reviewCount={props.reviewCount !== undefined ? Number(props.reviewCount) : 124}
              size={(props.size as any) || "md"}
              showValue={props.showValue !== false}
            />
          </div>
        );
      }
      case "review_histogram": {
        const dist = (props.distribution as any) || {
          star_5: 58,
          star_4: 18,
          star_3: 6,
          star_2: 3,
          star_1: 1,
        };
        return (
          <div className="w-full max-w-md">
            <ReviewHistogram
              distribution={dist}
              averageRating={Number(props.averageRating) || 4.5}
              totalReviews={Number(props.totalReviews) || 86}
              verifiedCount={Number(props.verifiedCount) || 72}
            />
          </div>
        );
      }
      case "recently_viewed": {
        const title = String(props.title || "بازدیدهای اخیر شما");
        const limit = Number(props.limit) || 4;
        const dummyRecentProducts = Array.from({ length: limit }, (_, i) => ({
          id: `recent_${i + 1}`,
          name: `کالای مشاهده‌شده ${i + 1}`,
          slug: `recent-prod-${i + 1}`,
          category_id: "",
          is_active: true,
          is_in_stock: true,
          min_price: (i + 1) * 290000,
          max_price: (i + 1) * 350000,
          variant_count: 1,
          primary_image_url: "/placeholder-hero.svg",
          rating_average: 4.7,
          review_count: 22,
        }));
        return (
          <div className="w-full space-y-3">
            <h4 className="text-sm font-bold text-foreground">{title}</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
              {dummyRecentProducts.map((p) => (
                <ProductCard key={p.id} product={p as any} variant="compact" />
              ))}
            </div>
          </div>
        );
      }
      case "mega_menu": {
        const sampleCats = [
          { id: "c1", name: "کالای دیجیتال", slug: "digital", parent_id: null, is_active: true, display_order: 1, image_url: "/placeholder.svg" },
          { id: "c2", name: "موبایل و تبلت", slug: "mobile", parent_id: "c1", is_active: true, display_order: 1, image_url: "/placeholder.svg" },
          { id: "c3", name: "لپ‌تاپ", slug: "laptop", parent_id: "c1", is_active: true, display_order: 2, image_url: "/placeholder.svg" },
          { id: "c4", name: "لوازم جانبی", slug: "accessories", parent_id: "c1", is_active: true, display_order: 3, image_url: "/placeholder.svg" },
          { id: "c5", name: "خانه و آشپزخانه", slug: "home", parent_id: null, is_active: true, display_order: 2, image_url: "/placeholder.svg" },
          { id: "c6", name: "لوازم برقی", slug: "appliances", parent_id: "c5", is_active: true, display_order: 1, image_url: "/placeholder.svg" },
        ];
        return (
          <div className="inline-block p-1">
            <MegaMenu categories={sampleCats as any} label={String(props.label || "دسته‌بندی کالاها")} />
          </div>
        );
      }
      case "product_title": {
        return (
          <h1 className="text-2xl font-bold text-foreground">
            {String(props.fallback_title || "عنوان محصول")}
          </h1>
        );
      }
      case "product_price": {
        const price = Number(props.price || props.fallback_price) || 1850000;
        const compareAt = props.compare_at_price ? Number(props.compare_at_price) : null;
        const currency = String(props.currency || "تومان");
        const showDiscount = props.show_discount !== false;
        const discountPercent = compareAt && compareAt > price ? Math.round(((compareAt - price) / compareAt) * 100) : null;

        return (
          <div className="flex items-center gap-2.5 flex-wrap">
            <span className="text-2xl font-black text-primary tracking-tight">
              {price.toLocaleString("fa-IR")} {currency}
            </span>
            {compareAt && compareAt > price && (
              <del className="text-sm text-muted-foreground">
                {compareAt.toLocaleString("fa-IR")} {currency}
              </del>
            )}
            {showDiscount && discountPercent && (
              <Badge className="bg-destructive text-destructive-foreground font-bold text-[11px] px-2 py-0.5 rounded-full">
                {discountPercent}٪ تخفیف
              </Badge>
            )}
          </div>
        );
      }
      case "add_to_cart": {
        const label = String(props.label || "افزودن به سبد خرید");
        const showQty = props.show_quantity !== false;

        const handleAddToCart = (e: React.MouseEvent) => {
          e.stopPropagation();
          useCartStore.getState().addItem({
            productId: String(props.product_id || element.id),
            variantId: String(props.variant_id || selectedVariantId || "var_1"),
            title: String(props.product_title || "کالای فروشگاه"),
            price: Number(props.price) || 1850000,
            quantity: cartQuantity,
          });
          toast({
            title: "به سبد خرید اضافه شد",
            description: `${label} (${cartQuantity} عدد) با موفقیت در سبد ثبت گردید.`,
          });
        };

        return (
          <div className="flex items-center gap-2 w-full">
            {showQty && (
              <div className="flex items-center border border-border/80 rounded-xl bg-card overflow-hidden shrink-0">
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCartQuantity(Math.max(1, cartQuantity - 1));
                  }}
                  className="px-2.5 py-2 hover:bg-muted text-xs text-muted-foreground"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
                <span className="px-3 text-xs font-bold">{cartQuantity}</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setCartQuantity(cartQuantity + 1);
                  }}
                  className="px-2.5 py-2 hover:bg-muted text-xs text-muted-foreground"
                >
                  <Plus className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            <button
              type="button"
              onClick={handleAddToCart}
              className="flex-1 rounded-xl bg-primary py-3 px-6 font-bold text-primary-foreground shadow hover:bg-primary/90 transition flex items-center justify-center gap-2 text-sm"
            >
              <ShoppingCart className="w-4 h-4" />
              <span>{label}</span>
            </button>
          </div>
        );
      }
      case "product_variants": {
        const pTitle = String(props.product_title || "انتخاب تنوع و مشخصات");
        const variants = (props.variants as any[]) || [
          { id: "var_1", title: "مشکی مات", price: 1850000, is_in_stock: true },
          { id: "var_2", title: "سفید صدفی", price: 1950000, is_in_stock: true },
        ];

        return (
          <div className="space-y-2 w-full">
            <span className="block text-xs font-bold text-foreground">{pTitle}</span>
            <div className="flex flex-wrap gap-2">
              {variants.map((v) => {
                const isSelected = selectedVariantId === v.id;
                return (
                  <button
                    key={v.id}
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelectedVariantId(v.id);
                    }}
                    className={cn(
                      "px-3 py-1.5 rounded-xl border text-xs font-semibold transition flex items-center gap-1.5",
                      isSelected
                        ? "border-primary bg-primary/10 text-primary font-bold shadow-sm"
                        : "border-border/80 bg-card hover:bg-muted/50 text-foreground"
                    )}
                  >
                    {isSelected && <Check className="w-3.5 h-3.5 text-primary" />}
                    <span>{v.title}</span>
                    {v.price && (
                      <span className="text-[10px] text-muted-foreground">
                        ({Number(v.price).toLocaleString("fa-IR")} تومان)
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        );
      }
      case "mini_cart": {
        const showBadge = props.show_badge !== false;
        const label = String(props.label || "سبد خرید");
        return (
          <div className="inline-flex items-center gap-2 px-3 py-2 rounded-xl bg-card border border-border/80 shadow-sm">
            <ShoppingCart className="w-4 h-4 text-primary" />
            <span className="text-xs font-bold text-foreground">{label}</span>
            {showBadge && (
              <Badge className="bg-primary text-primary-foreground text-[10px] font-bold px-1.5 py-0 h-4">
                ۲
              </Badge>
            )}
            <span className="text-xs text-muted-foreground font-semibold border-s ps-2">
              ۳,۷۰۰,۰۰۰ تومان
            </span>
          </div>
        );
      }
      case "cart_summary": {
        const title = String(props.title || "خلاصه سبد خرید");
        const btnLabel = String(props.button_label || "ادامه فرآیند خرید");
        return (
          <div className="p-4 rounded-2xl border border-border/80 bg-card space-y-3 shadow-sm w-full max-w-sm">
            <div className="flex items-center justify-between border-b pb-2">
              <span className="text-xs font-bold text-foreground">{title}</span>
              <Receipt className="w-4 h-4 text-primary" />
            </div>
            <div className="space-y-1.5 text-xs text-muted-foreground">
              <div className="flex justify-between">
                <span>جمع اقلام:</span>
                <span className="font-semibold text-foreground">۳,۸۰۰,۰۰۰ تومان</span>
              </div>
              <div className="flex justify-between text-emerald-600">
                <span>تخفیف:</span>
                <span className="font-semibold">- ۱۰۰,۰۰۰ تومان</span>
              </div>
              <div className="flex justify-between">
                <span>مالیات بر ارزش افزوده (۹٪):</span>
                <span>۳۳۳,۰۰۰ تومان</span>
              </div>
            </div>
            <div className="flex justify-between items-center pt-2 border-t font-bold text-sm text-foreground">
              <span>مبلغ قابل پرداخت:</span>
              <span className="text-primary text-base font-black">۴,۰۳۳,۰۰۰ تومان</span>
            </div>
            <a
              href={String(props.checkout_url || "/checkout")}
              data-checkout-url={props.checkout_url ? String(props.checkout_url) : undefined}
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition shadow block text-center"
            >
              {btnLabel}
            </a>
          </div>
        );
      }
      case "table": {
        const headers = (props.headers as string[]) || [];
        const rows = (props.rows as string[][]) || [];
        const bordered = props.bordered !== false;
        const striped = props.striped !== false;
        const highlightCol = props.highlightCol !== undefined && props.highlightCol !== null ? Number(props.highlightCol) : null;
        return (
          <div className="builder-table overflow-x-auto w-full select-text">
            <table className={cn(
              "w-full border-collapse text-right text-sm",
              bordered && "border border-border/80 rounded-xl overflow-hidden"
            )}>
              {headers.length > 0 && (
                <thead>
                  <tr className="bg-muted/40 border-b border-border/80">
                    {headers.map((h, i) => (
                      <th
                        key={i}
                        className={cn(
                          "p-3.5 font-semibold text-muted-foreground",
                          highlightCol === i && "bg-primary/10 text-primary font-bold border-x border-primary/20"
                        )}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
              )}
              <tbody className="divide-y divide-border/60">
                {rows.map((row, rIdx) => (
                  <tr key={rIdx} className={cn("hover:bg-muted/30 transition", striped && rIdx % 2 === 1 && "bg-muted/10")}>
                    {row.map((cell, cIdx) => (
                      <td
                        key={cIdx}
                        className={cn(
                          "p-3.5 text-foreground border-b border-border/60",
                          highlightCol === cIdx && "bg-primary/5 border-x border-primary/20 font-semibold"
                        )}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      }
      case "form_input": {
        const label = String(props.label || "");
        const placeholder = String(props.placeholder || "");
        const inputType = String(props.input_type || "text");
        const isRequired = Boolean(props.required);
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        return (
          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
            {label && (
              <label className="block text-xs font-semibold text-foreground">
                {label}
                {isRequired && <span className="text-destructive ms-1">*</span>}
              </label>
            )}
            <input
              type={inputType}
              placeholder={placeholder}
              required={isRequired}
              readOnly
              className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm"
            />
          </div>
        );
      }
      case "form_textarea": {
        const label = String(props.label || "");
        const placeholder = String(props.placeholder || "");
        const rowsNum = Number(props.rows || 4);
        const isRequired = Boolean(props.required);
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        return (
          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
            {label && (
              <label className="block text-xs font-semibold text-foreground">
                {label}
                {isRequired && <span className="text-destructive ms-1">*</span>}
              </label>
            )}
            <textarea
              placeholder={placeholder}
              rows={rowsNum}
              required={isRequired}
              readOnly
              className="w-full rounded-xl border border-input bg-background p-3 text-sm"
            />
          </div>
        );
      }
      case "form_select": {
        const label = String(props.label || "");
        const options = (props.options as string[]) || ["گزینه ۱", "گزینه ۲"];
        const isRequired = Boolean(props.required);
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        return (
          <div className={cn("space-y-1 w-full text-right pointer-events-none", customClass)} data-required={isRequired ? "true" : undefined}>
            {label && (
              <label className="block text-xs font-semibold text-foreground">
                {label}
                {isRequired && <span className="text-destructive ms-1">*</span>}
              </label>
            )}
            <select className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm" required={isRequired} disabled>
              {options.map((opt, i) => (
                <option key={i}>{typeof opt === "string" ? opt : (opt as any)?.label || opt}</option>
              ))}
            </select>
          </div>
        );
      }
      case "form_checkbox": {
        const label = String(props.label || "شرایط و قوانین را می‌پذیرم");
        const name = String(props.name || "terms");
        return (
          <div className="flex items-center gap-2 text-right">
            <input
              type="checkbox"
              id={`chk_${element.id}`}
              name={name}
              defaultChecked={Boolean(props.checked)}
              className="rounded border-input text-primary focus:ring-primary h-4 w-4"
            />
            <label htmlFor={`chk_${element.id}`} className="text-xs font-medium text-foreground cursor-pointer select-none">
              {label}
            </label>
          </div>
        );
      }
      case "form_radio": {
        const label = String(props.label || "انتخاب گزینه");
        const options = (props.options as string[]) || ["گزینه ۱", "گزینه ۲"];
        const name = String(props.name || "radio_group");
        return (
          <div className="space-y-1.5 text-right w-full">
            <span className="block text-xs font-bold text-foreground">{label}</span>
            <div className="flex flex-col gap-1.5">
              {options.map((opt, i) => (
                <label key={i} className="flex items-center gap-2 text-xs text-foreground cursor-pointer select-none">
                  <input
                    type="radio"
                    name={name}
                    defaultChecked={i === 0}
                    className="text-primary focus:ring-primary h-4 w-4"
                  />
                  <span>{opt}</span>
                </label>
              ))}
            </div>
          </div>
        );
      }
      case "accordion": {
        const items = (props.items as any[]) || [
          { title: "سؤال متداول ۱", content: "پاسخ مشروح به سؤال اول کاربر." },
          { title: "سؤال متداول ۲", content: "پاسخ مشروح به سؤال دوم کاربر." },
        ];
        return (
          <div className="space-y-2 w-full">
            {items.map((item, idx) => (
              <details
                key={idx}
                className="group rounded-xl border border-border/80 bg-card overflow-hidden shadow-sm"
                open={item.default_open || idx === 0}
              >
                <summary className="p-3.5 font-bold text-xs text-foreground cursor-pointer list-none flex items-center justify-between hover:bg-muted/40 transition select-none">
                  <span>{item.title}</span>
                  <ChevronDown className="w-4 h-4 text-muted-foreground transition-transform group-open:rotate-180" />
                </summary>
                <div className="p-3.5 pt-0 text-xs text-muted-foreground border-t border-border/40 leading-relaxed">
                  {item.content}
                </div>
              </details>
            ))}
          </div>
        );
      }
      case "tabs": {
        const tabsList = (props.tabs as any[]) || [
          { title: "مشخصات کلی", content: "توضیحات مشخصات فنی و ویژگی‌های برجسته کالا." },
          { title: "دیدگاه کاربران", content: "ثبت و بررسی دیدگاه‌های خریداران." },
        ];
        return (
          <div className="rounded-xl border border-border/80 bg-card overflow-hidden w-full shadow-sm">
            <div className="flex border-b border-border/60 bg-muted/30">
              {tabsList.map((t, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setActiveTabIdx(idx);
                  }}
                  className={cn(
                    "px-4 py-2.5 text-xs font-bold border-b-2 transition",
                    activeTabIdx === idx
                      ? "border-primary text-primary bg-background shadow-xs"
                      : "border-transparent text-muted-foreground hover:text-foreground"
                  )}
                >
                  {t.title}
                </button>
              ))}
            </div>
            <div className="p-4 text-xs text-muted-foreground leading-relaxed">
              {tabsList[activeTabIdx]?.content || tabsList[0]?.content}
            </div>
          </div>
        );
      }
      case "countdown": {
        const title = String(props.title || "پیشنهاد شگفت‌انگیز");
        const targetDate = String(props.target_date || "");

        let days = "۰۲";
        let hours = "۱۴";
        let minutes = "۳۵";
        let seconds = "۴۸";

        if (targetDate) {
          const targetTime = new Date(targetDate).getTime();
          if (!isNaN(targetTime)) {
            const diff = Math.max(0, targetTime - Date.now());
            const d = Math.floor(diff / (1000 * 60 * 60 * 24));
            const h = Math.floor((diff / (1000 * 60 * 60)) % 24);
            const m = Math.floor((diff / (1000 * 60)) % 60);
            const s = Math.floor((diff / 1000) % 60);
            days = d.toLocaleString("fa-IR", { minimumIntegerDigits: 2 });
            hours = h.toLocaleString("fa-IR", { minimumIntegerDigits: 2 });
            minutes = m.toLocaleString("fa-IR", { minimumIntegerDigits: 2 });
            seconds = s.toLocaleString("fa-IR", { minimumIntegerDigits: 2 });
          }
        }

        return (
          <div className="p-4 rounded-2xl bg-card border border-border/80 text-center space-y-3 shadow-sm w-full">
            <h3 className="font-bold text-sm text-foreground">{title}</h3>
            <div className="flex items-center justify-center gap-2 text-center" dir="ltr">
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">{days}</span>
                <span className="text-[10px] text-muted-foreground">روز</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">{hours}</span>
                <span className="text-[10px] text-muted-foreground">ساعت</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">{minutes}</span>
                <span className="text-[10px] text-muted-foreground">دقیقه</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">{seconds}</span>
                <span className="text-[10px] text-muted-foreground">ثانیه</span>
              </div>
            </div>
          </div>
        );
      }
      case "icon_box": {
        const title = String(props.title || "ارسال سریع و مطمئن");
        const desc = String(props.description || "تحویل در کمترین زمان ممکن با بسته‌بندی ویژه به سراسر کشور");
        const iconKey = String(props.icon || "shield-check");
        const BoxIcon = getBuilderIcon(iconKey);
        return (
          <div className="p-4 rounded-2xl border border-border/80 bg-card flex items-start gap-3 shadow-sm w-full">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <BoxIcon className="w-5 h-5" />
            </div>
            <div className="space-y-1 text-right">
              <h4 className="font-bold text-xs text-foreground">{title}</h4>
              <p className="text-[11px] text-muted-foreground leading-relaxed">{desc}</p>
            </div>
          </div>
        );
      }
      case "icon": {
        const iconKey = String(props.icon || "star");
        const IconComponent = getBuilderIcon(iconKey);
        const view = String(props.view || "default");
        const shape = String(props.shape || "circle");
        const size = Number(props.size || 32);
        const rotate = Number(props.rotate || 0);
        const url = String(props.url || "");
        const newTab = Boolean(props.newTab);

        const iconEl = (
          <div
            className={cn(
              "inline-flex items-center justify-center transition-transform",
              view === "stacked" && "bg-primary text-primary-foreground shadow-sm",
              view === "framed" && "border-2 border-primary text-primary bg-transparent",
              view === "default" && "text-primary",
              shape === "circle" ? "rounded-full" : "rounded-xl"
            )}
            style={{
              padding: view !== "default" ? `${Math.round(size * 0.4)}px` : undefined,
              transform: rotate ? `rotate(${rotate}deg)` : undefined,
            }}
          >
            <IconComponent style={{ width: `${size}px`, height: `${size}px` }} />
          </div>
        );

        if (url) {
          return (
            <a
              href={url}
              target={newTab ? "_blank" : undefined}
              rel={newTab ? "noopener noreferrer" : undefined}
              className="inline-block"
              onClick={(e) => e.preventDefault()}
            >
              {iconEl}
            </a>
          );
        }
        return <div className="inline-block">{iconEl}</div>;
      }
      case "icon_list": {
        const layout = String(props.layout || "vertical");
        const rawItems = Array.isArray(props.items) ? (props.items as any[]) : [];
        const items = rawItems.length > 0 ? rawItems : [
          { text: "ارسال سریع برای خریدهای بالای ۵۰۰ هزار تومان", icon: "truck", url: "" },
          { text: "ضمانت بازگشت وجه تا ۷ روز کاری", icon: "shield-check", url: "" },
          { text: "پشتیبانی ۲۴ ساعته در تمام روزهای هفته", icon: "headphones", url: "" },
        ];
        return (
          <ul className={cn(
            "w-full text-right space-y-2.5",
            layout === "horizontal" && "flex flex-wrap items-center gap-4 space-y-0"
          )}>
            {items.map((item, idx) => {
              const ItemIcon = getBuilderIcon(item.icon || "check");
              return (
                <li key={idx} className="flex items-center gap-2.5 text-xs text-foreground">
                  <div className="w-5 h-5 rounded-full bg-primary/10 text-primary flex items-center justify-center shrink-0">
                    <ItemIcon className="w-3 h-3" />
                  </div>
                  {item.url ? (
                    <a
                      href={item.url}
                      className="hover:text-primary transition hover:underline"
                      onClick={(e) => e.preventDefault()}
                    >
                      {item.text}
                    </a>
                  ) : (
                    <span>{item.text}</span>
                  )}
                </li>
              );
            })}
          </ul>
        );
      }
      case "price_table": {
        const title = String(props.title || "پلن استاندارد");
        const subtitle = String(props.subtitle || "مناسب برای کسب‌وکارهای در حال رشد");
        const price = String(props.price || "۴۹۰,۰۰۰");
        const currency = String(props.currency || "تومان");
        const period = String(props.period || "ماهانه");
        const badge = String(props.badge || "");
        const isFeatured = Boolean(props.is_featured);
        const features = Array.isArray(props.features) ? (props.features as any[]) : [
          { text: "دسترسی نامحدود به تمامی امکانات", available: true },
          { text: "پشتیبانی اختصاصی تلفنی و تیکتی", available: true },
          { text: "فضای ابری ۵۰ گیگابایت امن", available: true },
          { text: "دامنه اختصاصی رایگان ۱ ساله", available: false },
        ];
        const btnLabel = String(props.button_label || "انتخاب و شروع پلن");
        const btnUrl = String(props.button_url || "/checkout");

        return (
          <div className={cn(
            "w-full max-w-sm rounded-3xl border bg-card p-6 text-right space-y-5 transition shadow-sm relative overflow-hidden",
            isFeatured ? "border-primary shadow-md ring-2 ring-primary/20" : "border-border/80"
          )}>
            {badge && (
              <div className="absolute top-3 left-3 bg-primary text-primary-foreground text-[10px] font-bold px-2.5 py-0.5 rounded-full shadow-xs">
                {badge}
              </div>
            )}
            <div className="space-y-1">
              <h3 className="text-base font-extrabold text-foreground">{title}</h3>
              {subtitle && <p className="text-[11px] text-muted-foreground">{subtitle}</p>}
            </div>
            <div className="flex items-baseline gap-1.5 border-y border-border/60 py-4">
              <span className="text-2xl font-black text-primary font-mono">{price}</span>
              <span className="text-xs font-semibold text-muted-foreground">{currency}</span>
              {period && <span className="text-[10px] text-muted-foreground/80">/ {period}</span>}
            </div>
            <ul className="space-y-2.5 text-xs">
              {features.map((f, i) => (
                <li key={i} className="flex items-center gap-2">
                  <div className={cn(
                    "w-4 h-4 rounded-full flex items-center justify-center shrink-0",
                    f.available ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400" : "bg-muted text-muted-foreground/40"
                  )}>
                    {f.available ? <Check className="w-2.5 h-2.5" /> : <Minus className="w-2.5 h-2.5" />}
                  </div>
                  <span className={cn(f.available ? "text-foreground font-medium" : "text-muted-foreground line-through opacity-70")}>
                    {f.text}
                  </span>
                </li>
              ))}
            </ul>
            <a
              href={btnUrl}
              onClick={(e) => e.preventDefault()}
              className={cn(
                "block w-full text-center py-2.5 rounded-xl font-bold text-xs transition shadow-sm",
                isFeatured
                  ? "bg-primary text-primary-foreground hover:bg-primary/90"
                  : "bg-muted/80 text-foreground hover:bg-muted"
              )}
            >
              {btnLabel}
            </a>
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
        const sepStyle = String(props.separator_style || "dotted");

        return (
          <div className="w-full space-y-4 text-right">
            {items.map((it, idx) => (
              <div key={idx} className="space-y-1">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-xs font-bold text-foreground shrink-0">{it.title}</span>
                  {sepStyle !== "none" && (
                    <div className={cn(
                      "flex-1 border-b border-border/80 mx-1",
                      sepStyle === "dotted" && "border-dotted",
                      sepStyle === "dashed" && "border-dashed",
                      sepStyle === "solid" && "border-solid"
                    )} />
                  )}
                  <span className="text-xs font-black text-primary font-mono shrink-0">{it.price}</span>
                </div>
                {it.description && (
                  <p className="text-[11px] text-muted-foreground">{it.description}</p>
                )}
              </div>
            ))}
          </div>
        );
      }
      case "counter": {
        const title = String(props.title || "شمارنده");
        const starting = Number(props.starting_number ?? 0);
        const ending = Number(props.ending_number ?? 100);
        const prefix = String(props.prefix || "");
        const suffix = String(props.suffix || "");
        return (
          <div
            className="p-4 rounded-2xl border border-border/80 bg-card text-center space-y-1 shadow-sm w-full"
            data-starting-number={starting}
            data-ending-number={ending}
          >
            <div className="text-3xl font-black text-primary font-mono" dir="ltr">
              {prefix}{ending.toLocaleString("fa-IR")}{suffix}
            </div>
            <div className="text-xs font-semibold text-muted-foreground">{title}</div>
          </div>
        );
      }
      case "progress_bar": {
        const title = String(props.title || "پیشرفت کار");
        const pct = Math.max(0, Math.min(100, Number(props.percentage ?? 75)));
        const showPct = props.show_percentage !== false;
        return (
          <div className="space-y-1.5 w-full text-right">
            <div className="flex items-center justify-between text-xs font-semibold text-foreground">
              <span>{title}</span>
              {showPct && <span className="font-mono text-primary">{pct}%</span>}
            </div>
            <div className="h-3 w-full rounded-full bg-muted overflow-hidden">
              <div className="h-full bg-primary rounded-full transition-all duration-300" style={{ width: `${pct}%` }} />
            </div>
          </div>
        );
      }
      case "testimonial": {
        const author = String(props.author || "نام مشتری");
        const role = String(props.role || "سمت یا عنوان");
        const company = String(props.company || "");
        const quote = String(props.quote || "متن دیدگاه مشتری در اینجا نمایش داده می‌شود.");
        const avatar = String(props.avatar_url || "/placeholder-hero.svg");
        return (
          <div className="p-4 rounded-2xl border border-border/80 bg-card space-y-3 shadow-sm w-full text-right">
            <p className="text-xs text-muted-foreground leading-relaxed italic">«{quote}»</p>
            <div className="flex items-center gap-3 pt-2 border-t border-border/60">
              <img src={avatar} alt={author} className="w-9 h-9 rounded-full object-cover shrink-0" />
              <div>
                <div className="text-xs font-bold text-foreground">{author}</div>
                <div className="text-[10px] text-muted-foreground">{role}{company ? ` - ${company}` : ""}</div>
              </div>
            </div>
          </div>
        );
      }
      case "alert": {
        const title = String(props.title || "اعلان");
        const msg = String(props.message || "متن اعلان پیام");
        const aType = String(props.alert_type || "info");
        const bgMap: Record<string, string> = {
          info: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
          success: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
          warning: "bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/30",
          danger: "bg-destructive/10 text-destructive border-destructive/30",
        };
        return (
          <div className={cn("p-3.5 rounded-xl border text-right space-y-1 w-full", bgMap[aType] || bgMap.info)}>
            <div className="text-xs font-bold flex items-center gap-1.5">
              <span>{title}</span>
            </div>
            <div className="text-[11px] leading-relaxed opacity-90">{msg}</div>
          </div>
        );
      }
      case "call_to_action": {
        const title = String(props.title || "عنوان اقدام به عمل");
        const desc = String(props.description || "توضیحات مربوط به بنر تشویق به اقدام");
        const btnLabel = String(props.button_label || "شروع کنید");
        const badge = props.badge ? String(props.badge) : undefined;
        return (
          <div className="p-6 rounded-2xl border border-primary/20 bg-primary/5 text-center space-y-3 shadow-sm w-full">
            {badge && (
              <span className="inline-block px-2.5 py-0.5 rounded-full bg-primary text-primary-foreground text-[10px] font-bold">
                {badge}
              </span>
            )}
            <h3 className="text-lg font-bold text-foreground">{title}</h3>
            <p className="text-xs text-muted-foreground max-w-md mx-auto leading-relaxed">{desc}</p>
            <div>
              <button type="button" className="inline-flex items-center justify-center px-5 py-2.5 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow hover:bg-primary/90 transition">
                {btnLabel}
              </button>
            </div>
          </div>
        );
      }
      case "animated_headline": {
        const before = String(props.before_text || "");
        const highlight = String(props.highlighted_text || "تیتر متحرک");
        const after = String(props.after_text || "");
        return (
          <h2 className="text-2xl lg:text-3xl font-extrabold text-foreground text-center py-2 leading-relaxed">
            {before && <span className="me-2">{before}</span>}
            <span className="relative inline-block px-2 text-primary font-black underline decoration-primary/40 decoration-wavy decoration-2 underline-offset-8">
              {highlight}
            </span>
            {after && <span className="ms-2">{after}</span>}
          </h2>
        );
      }
      case "flip_box": {
        const frontTitle = String(props.front_title || "روی کارت");
        const frontDesc = String(props.front_desc || "توضیحات جلو");
        const backTitle = String(props.back_title || "پشت کارت");
        const backDesc = String(props.back_desc || "توضیحات پشت");
        const btnText = String(props.button_text || "مشاهده");
        return (
          <div className="group/flip w-full min-h-[220px] [perspective:1000px]">
            <div className="relative w-full h-full min-h-[220px] transition-transform duration-500 [transform-style:preserve-3d] group-hover/flip:[transform:rotateY(180deg)] rounded-2xl border border-border/80 shadow-sm">
              {/* Front Face */}
              <div className="absolute inset-0 w-full h-full p-6 flex flex-col items-center justify-center text-center space-y-2 [backface-visibility:hidden] bg-card rounded-2xl">
                <RotateCw className="w-8 h-8 text-primary mb-1" />
                <h4 className="text-base font-bold text-foreground">{frontTitle}</h4>
                <p className="text-xs text-muted-foreground">{frontDesc}</p>
              </div>
              {/* Back Face */}
              <div className="absolute inset-0 w-full h-full p-6 flex flex-col items-center justify-center text-center space-y-3 [backface-visibility:hidden] [transform:rotateY(180deg)] bg-primary text-primary-foreground rounded-2xl">
                <h4 className="text-base font-bold">{backTitle}</h4>
                <p className="text-xs opacity-90">{backDesc}</p>
                <button type="button" className="px-4 py-2 rounded-xl bg-white text-primary text-xs font-bold shadow hover:bg-white/90">
                  {btnText}
                </button>
              </div>
            </div>
          </div>
        );
      }
      case "social_links": {
        const links = (props.links as any[]) || [
          { platform: "اینستاگرام", url: "#" },
          { platform: "تلگرام", url: "#" },
        ];
        return (
          <div className="flex items-center gap-2 flex-wrap">
            {links.map((l, idx) => (
              <a
                key={idx}
                href={l.url || "#"}
                onClick={(e) => e.preventDefault()}
                className="p-2 rounded-xl bg-muted/60 hover:bg-primary hover:text-white transition text-xs font-bold flex items-center gap-1.5"
              >
                <Share2 className="w-3.5 h-3.5" />
                <span>{l.platform}</span>
              </a>
            ))}
          </div>
        );
      }
      case "image_box": {
        const imgUrl = String(props.image_url || props.url || "/placeholder-hero.svg");
        const title = String(props.title || "عنوان جعبه تصویر");
        const desc = String(props.description || "");
        const position = String(props.position || "top");
        const link = props.link ? String(props.link) : undefined;

        const isHorizontal = position === "left" || position === "right";
        return (
          <div className={cn(
            "w-full p-4 rounded-2xl border border-border/80 bg-card shadow-sm space-y-2",
            isHorizontal && "flex items-start gap-4 space-y-0",
            position === "right" && "flex-row-reverse"
          )}>
            <img
              src={imgUrl}
              alt={title}
              className={cn(
                "rounded-xl object-cover",
                position === "top" ? "w-full max-h-48" : "w-20 h-20 shrink-0"
              )}
            />
            <div className="space-y-1 text-right flex-1">
              <h4 className="font-bold text-sm text-foreground">{title}</h4>
              {desc && <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>}
              {link && <a href={link} className="inline-block text-xs text-primary font-bold hover:underline pt-1">اطلاعات بیشتر &larr;</a>}
            </div>
          </div>
        );
      }
      case "toggle": {
        const rawItems = Array.isArray(props.items) ? (props.items as any[]) : [];
        const items = rawItems.length > 0 ? rawItems : [
          { title: "سوال متداول شماره ۱", content: "پاسخ کامل و جامع به سوال اول کاربر در این قسمت قرار می‌گیرد.", is_open: true },
          { title: "سوال متداول شماره ۲", content: "توضیحات و پاسخ شفاف به پرسش دوم کاربر.", is_open: false },
        ];
        return (
          <div className="space-y-2 w-full text-right">
            {items.map((it, idx) => (
              <details
                key={idx}
                className="group rounded-xl border border-border/80 bg-card overflow-hidden shadow-xs"
                open={Boolean(it.is_open)}
              >
                <summary className="p-3.5 font-bold text-xs text-foreground cursor-pointer list-none flex items-center justify-between hover:bg-muted/40 transition select-none">
                  <span>{it.title || "آیتم تاشو"}</span>
                  <span className="transition-transform group-open:rotate-180 text-muted-foreground">▾</span>
                </summary>
                <div className="p-3.5 pt-0 text-xs text-muted-foreground border-t border-border/40 leading-relaxed">
                  {it.content}
                </div>
              </details>
            ))}
          </div>
        );
      }
      case "share_buttons": {
        const rawNets = Array.isArray(props.networks) ? (props.networks as string[]) : ["telegram", "whatsapp", "twitter", "linkedin"];
        const shape = String(props.shape || "rounded");
        const shapeCls = shape === "circle" ? "rounded-full" : (shape === "square" ? "rounded-none" : "rounded-xl");
        const netMap: Record<string, { label: string; bg: string }> = {
          telegram: { label: "تلگرام", bg: "bg-[#229ED9] text-white" },
          whatsapp: { label: "واتس‌اپ", bg: "bg-[#25D366] text-white" },
          twitter: { label: "توییتر (X)", bg: "bg-[#000000] text-white" },
          linkedin: { label: "لینکدین", bg: "bg-[#0077B5] text-white" },
          facebook: { label: "فیس‌بوک", bg: "bg-[#1877F2] text-white" },
        };
        return (
          <div className="flex flex-wrap items-center gap-2 w-full">
            {rawNets.map((net, idx) => {
              const info = netMap[net] || { label: net, bg: "bg-primary text-white" };
              return (
                <button
                  key={idx}
                  type="button"
                  className={cn("inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-bold transition shadow-xs", shapeCls, info.bg)}
                  onClick={(e) => e.preventDefault()}
                >
                  <Share2 className="w-3 h-3" />
                  <span>{info.label}</span>
                </button>
              );
            })}
          </div>
        );
      }
      case "progress_tracker": {
        const heightPx = Number(props.height) || 4;
        return (
          <div className="w-full bg-muted/60 overflow-hidden rounded-full my-2" style={{ height: `${heightPx}px` }}>
            <div className="h-full bg-primary rounded-full transition-all duration-150" style={{ width: "45%" }} />
          </div>
        );
      }
      case "table_of_contents": {
        const title = String(props.title || "فهرست محتوا");
        const rawItems = Array.isArray(props.items) ? (props.items as any[]) : [
          { text: "مقدمه و بررسی اولیه", level: 2 },
          { text: "امکانات و مزیت‌های شاخص", level: 2 },
          { text: "جمع‌بندی و راهنمای سفارش", level: 3 },
        ];
        return (
          <nav className="p-4 rounded-2xl border border-border/80 bg-card/60 space-y-2 text-right w-full">
            <h4 className="font-bold text-xs text-foreground pb-1 border-b border-border/60">{title}</h4>
            <ul className="space-y-1.5 pt-1">
              {rawItems.map((itm, idx) => (
                <li
                  key={idx}
                  className={cn(
                    "hover:text-primary transition",
                    Number(itm.level) > 2 ? "pr-4 text-xs font-medium text-muted-foreground" : "font-bold text-xs text-foreground"
                  )}
                >
                  <a href="#" onClick={(e) => e.preventDefault()}>• {itm.text}</a>
                </li>
              ))}
            </ul>
          </nav>
        );
      }
      case "hotspot": {
        const imgUrl = String(props.image_url || "/placeholder-hero.svg");
        const alt = String(props.alt || "تصویر با نقاط تعاملی");
        const spots = Array.isArray(props.spots) ? (props.spots as any[]) : [
          { x: 35, y: 40, title: "نقطه اول", content: "توضیحات نقطه اول" }
        ];
        return (
          <div className="relative inline-block rounded-2xl overflow-hidden max-w-full w-full">
            <img src={imgUrl} alt={alt} className="w-full h-auto block rounded-2xl" />
            {spots.map((s, idx) => {
              const x = Math.max(0, Math.min(100, Number(s.x) || 50));
              const y = Math.max(0, Math.min(100, Number(s.y) || 50));
              return (
                <div
                  key={idx}
                  className="absolute -translate-x-1/2 -translate-y-1/2 group/spot cursor-pointer"
                  style={{ left: `${x}%`, top: `${y}%` }}
                >
                  <span className="w-5 h-5 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-black shadow-md ring-4 ring-primary/30 animate-pulse">
                    +
                  </span>
                  <div className="absolute bottom-full right-1/2 translate-x-1/2 mb-2 hidden group-hover/spot:block w-44 p-2 bg-popover text-popover-foreground text-xs rounded-xl shadow-xl border border-border z-30 pointer-events-none">
                    <div className="font-bold text-[11px] mb-0.5">{s.title}</div>
                    <div className="text-[10px] text-muted-foreground leading-relaxed">{s.content}</div>
                  </div>
                </div>
              );
            })}
          </div>
        );
      }
      case "lottie": {
        const url = String(props.url || "animation.json");
        return (
          <div className="flex items-center justify-center p-3 w-full">
            <div className="w-36 h-36 rounded-2xl bg-muted/40 border border-border/80 flex flex-col items-center justify-center gap-1.5 text-muted-foreground text-xs font-mono">
              <span className="text-primary font-bold text-sm">✦ Lottie Animation</span>
              <span className="text-[10px] opacity-75 truncate max-w-[120px]">{url.split("/").pop()}</span>
            </div>
          </div>
        );
      }
      case "code_highlight": {
        const code = String(props.code || "console.log('محتوای کد نمونه');");
        const lang = String(props.language || "javascript");
        return (
          <div className="w-full my-2 rounded-2xl overflow-hidden border border-border/80 bg-zinc-950 text-zinc-100 font-mono text-xs text-left" dir="ltr">
            <div className="px-4 py-1.5 border-b border-zinc-800 bg-zinc-900/60 text-zinc-400 text-[10px] flex items-center justify-between">
              <span>{lang}</span>
              <span className="text-zinc-600">کد برنامه</span>
            </div>
            <pre className="p-3.5 overflow-x-auto text-[11px] leading-relaxed">
              <code>{code}</code>
            </pre>
          </div>
        );
      }
      case "contact_buttons": {
        const title = String(props.title || "نیاز به مشاوره دارید؟");
        const phone = String(props.phone || "۰۲۱-۸۸۸۸۹۹۹۹");
        const btnLabel = String(props.button_label || "تماس سریع");
        return (
          <div className="w-full p-4 rounded-2xl border border-primary/20 bg-primary/5 flex items-center justify-between gap-3 text-right">
            <div>
              <h4 className="font-bold text-xs text-foreground">{title}</h4>
              <span className="text-[11px] text-muted-foreground font-mono" dir="ltr">{phone}</span>
            </div>
            <button
              type="button"
              className="px-4 py-2 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-xs hover:bg-primary/90 transition shrink-0"
              onClick={(e) => e.preventDefault()}
            >
              {btnLabel}
            </button>
          </div>
        );
      }
      case "image_carousel": {
        const rawImages = Array.isArray(props.images) ? (props.images as any[]) : [];
        const images = rawImages.length > 0 ? rawImages : [
          { url: "/placeholder-hero.svg", alt: "تصویر ۱" },
          { url: "/placeholder.svg", alt: "تصویر ۲" },
        ];
        return (
          <div className="w-full flex items-center gap-3 overflow-x-auto py-2 no-scrollbar" dir="rtl">
            {images.map((img, idx) => (
              <div key={idx} className="min-w-[180px] aspect-video rounded-xl bg-muted/20 overflow-hidden flex items-center justify-center shrink-0 border border-border/60">
                <img src={img.url || img} alt={img.alt || "اسلاید"} className="w-full h-full object-cover" />
              </div>
            ))}
          </div>
        );
      }
      case "slides": {
        const rawSlides = Array.isArray(props.slides) ? (props.slides as any[]) : [];
        const slides = rawSlides.length > 0 ? rawSlides : [
          {
            title: "جشنواره فروش ویژه",
            description: "بهترین فرصت برای خرید با تخفیف استثنایی",
            button_label: "مشاهده محصولات",
            background_image: "/placeholder-hero.svg",
          },
        ];
        return (
          <div className="w-full space-y-3">
            {slides.map((s, idx) => (
              <div
                key={idx}
                className="relative w-full min-h-[260px] rounded-2xl overflow-hidden flex flex-col justify-center p-6 text-white bg-cover bg-center"
                style={{
                  backgroundImage: `linear-gradient(rgba(0,0,0,0.4), rgba(0,0,0,0.6)), url(${s.background_image || "/placeholder-hero.svg"})`,
                }}
              >
                <h3 className="text-xl font-black mb-1.5">{s.title}</h3>
                <p className="text-xs max-w-md opacity-90 leading-relaxed">{s.description}</p>
                {s.button_label && (
                  <div className="pt-2">
                    <span className="inline-block px-4 py-2 rounded-xl bg-primary text-primary-foreground font-bold text-xs shadow-sm">
                      {s.button_label}
                    </span>
                  </div>
                )}
              </div>
            ))}
          </div>
        );
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
      ref={elementRef}
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
        !previewMode && isDragOver && "outline-2 outline-emerald-500 bg-emerald-500/10 shadow-lg ring-2 ring-emerald-500/30",
        element.isHidden && "opacity-50",
        (element.styles?.animation || (element.styles as any)?.entranceAnimation) &&
          (element.styles?.animation || (element.styles as any)?.entranceAnimation) !== "none" &&
          `builder-animate-${element.styles?.animation || (element.styles as any)?.entranceAnimation}`,
        element.styles?.customCssClass
      )}
      id={element.styles?.customCssId || undefined}
      data-element-id={element.id}
      data-element-name={element.name}
      data-submit-url={element.widgetType === "form_container" ? String(element.widgetProps?.submit_url || "") : undefined}
      data-success-message={element.widgetType === "form_container" ? String(element.widgetProps?.success_message || "") : undefined}
      data-error-message={element.widgetType === "form_container" ? String(element.widgetProps?.error_message || "") : undefined}
      {...customAttrs}
    >
      {/* Scoped Custom CSS */}
      {(element.styles as any)?.customCss && (
        <style dangerouslySetInnerHTML={{ __html: String((element.styles as any).customCss) }} />
      )}
      {/* Background Overlay (Elementor Parity) */}
      {overlayStyle && (
        <div data-testid="background-overlay" style={overlayStyle} aria-hidden="true" />
      )}
      {/* Breakpoint Hidden Indicator */}
      {isHiddenOnActiveBreakpoint && !previewMode && (
        <div className="absolute top-1 end-1 z-30 pointer-events-none">
          <Badge variant="outline" className="bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-300 text-[9px] px-1.5 py-0 h-4 flex items-center gap-1 shadow-xs">
            <EyeOff className="w-2.5 h-2.5" />
            <span>مخفی در {activeBreakpoint === "mobile" ? "موبایل" : activeBreakpoint === "tablet" ? "تبلت" : "دسکتاپ"}</span>
          </Badge>
        </div>
      )}

      {/* Auth Visibility Indicator */}
      {(element.authVisibility || (element.styles as any)?.authVisibility) &&
        (element.authVisibility || (element.styles as any)?.authVisibility) !== "all" &&
        !previewMode && (
          <div className="absolute top-1 start-1 z-30 pointer-events-none">
            <Badge variant="outline" className="bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-300 text-[9px] px-1.5 py-0 h-4 flex items-center gap-1 shadow-xs">
              <Lock className="w-2.5 h-2.5" />
              <span>
                {(element.authVisibility || (element.styles as any)?.authVisibility) === "authenticated"
                  ? "فقط اعضا"
                  : "فقط مهمان"}
              </span>
            </Badge>
          </div>
        )}

      {/* Form Container Identifier */}
      {element.widgetType === "form_container" && !previewMode && (
        <div
          className="absolute top-1 start-1 z-20 pointer-events-none"
          data-submit-url={String(element.widgetProps?.submit_url || "")}
          data-success-message={String(element.widgetProps?.success_message || "")}
          data-error-message={String(element.widgetProps?.error_message || "")}
        >
          <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-300 text-[9px] px-1.5 py-0 h-4">
            فرم سازنده (Form Container)
          </Badge>
        </div>
      )}

      {/* Off-Canvas & Popup Identifiers */}
      {element.widgetType === "off_canvas" && !previewMode && (
        <div
          className="absolute top-1 start-1 z-20 pointer-events-none"
          data-drawer-title={String(element.widgetProps?.drawer_title || "")}
          data-position={String(element.widgetProps?.position || "right")}
        >
          <Badge variant="outline" className="bg-indigo-500/10 text-indigo-600 dark:text-indigo-400 border-indigo-300 text-[9px] px-1.5 py-0 h-4">
            کشوی جانبی: {String(element.widgetProps?.drawer_title || "Off-Canvas")} ({String(element.widgetProps?.position || "right")})
          </Badge>
        </div>
      )}

      {element.widgetType === "popup_builder" && !previewMode && (
        <div
          className="absolute top-1 start-1 z-20 pointer-events-none"
          data-popup-title={String(element.widgetProps?.popup_title || "")}
          data-trigger={String(element.widgetProps?.trigger || "exit_intent")}
        >
          <Badge variant="outline" className="bg-rose-500/10 text-rose-600 dark:text-rose-400 border-rose-300 text-[9px] px-1.5 py-0 h-4">
            پاپ‌آپ: {String(element.widgetProps?.popup_title || "Popup")} [{String(element.widgetProps?.trigger || "exit_intent")}]
          </Badge>
        </div>
      )}

      {isContainer && (
        <SaveTemplateDialog
          element={element}
          open={saveTemplateOpen}
          onOpenChange={setSaveTemplateOpen}
        />
      )}

      {/* Top Shape Divider (Elementor Parity) */}
      {isContainer && (element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) && (element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) !== "none" && (
        <div
          data-testid="shape-divider-top"
          className="absolute top-0 start-0 w-full overflow-hidden leading-none z-10 pointer-events-none"
          style={{ height: "48px" }}
        >
          {((element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) === "waves") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M421.9,6.5c22.6-2.5,51.5,0.4,75.5,5.3c23.6,4.9,70.9,23.5,100.5,35.7c75.8,32.2,133.7,44.5,192.6,49.7c23.6,2.1,48.7,3.5,103.4-2.5c54.7-6,106.2-25.6,106.2-25.6V0H0v30.3c0,0,72,32.6,158.4,30.5c39.2-0.7,92.8-6.7,134-22.4c21.2-8.1,52.2-18.2,79.7-24.2C399.3,7.9,411.6,7.5,421.9,6.5z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) === "curve") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M1000,4.3V0H0v4.3C0.9,23.1,126.7,99.2,500,100S1000,22.7,1000,4.3z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) === "triangle") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M500,98.9L0,6.1V0h1000v6.1L500,98.9z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerTop || (element.styles?.mobile as any)?.shapeDividerTop) === "tilt") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M0,6V0h1000v100L0,6z"
              />
            </svg>
          )}
        </div>
      )}

      {/* Bottom Shape Divider (Elementor Parity) */}
      {isContainer && (element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) && (element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) !== "none" && (
        <div
          data-testid="shape-divider-bottom"
          className="absolute bottom-0 start-0 w-full overflow-hidden leading-none z-10 pointer-events-none rotate-180"
          style={{ height: "48px" }}
        >
          {((element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) === "waves") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M421.9,6.5c22.6-2.5,51.5,0.4,75.5,5.3c23.6,4.9,70.9,23.5,100.5,35.7c75.8,32.2,133.7,44.5,192.6,49.7c23.6,2.1,48.7,3.5,103.4-2.5c54.7-6,106.2-25.6,106.2-25.6V0H0v30.3c0,0,72,32.6,158.4,30.5c39.2-0.7,92.8-6.7,134-22.4c21.2-8.1,52.2-18.2,79.7-24.2C399.3,7.9,411.6,7.5,421.9,6.5z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) === "curve") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M1000,4.3V0H0v4.3C0.9,23.1,126.7,99.2,500,100S1000,22.7,1000,4.3z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) === "triangle") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M500,98.9L0,6.1V0h1000v6.1L500,98.9z"
              />
            </svg>
          )}
          {((element.styles?.shapeDividerBottom || (element.styles?.mobile as any)?.shapeDividerBottom) === "tilt") && (
            <svg viewBox="0 0 1000 100" preserveAspectRatio="none" className="w-full h-full block">
              <path
                fill={element.styles?.shapeDividerColor || (element.styles?.mobile as any)?.shapeDividerColor || "#ffffff"}
                d="M0,6V0h1000v100L0,6z"
              />
            </svg>
          )}
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
            <div className="space-y-3 w-full">
              <ContainerPresetPicker containerId={element.id} />
              <div
                onClick={(e) => {
                  e.stopPropagation();
                  selectElement(element.id);
                  useBuilderStore.getState().setLeftTab("blocks");
                }}
                data-testid="empty-container-guide"
                className="flex flex-col items-center justify-center p-5 border-2 border-dashed border-primary/30 hover:border-primary/60 rounded-xl bg-card/40 hover:bg-primary/5 transition-all cursor-pointer text-center w-full min-h-[80px] shadow-xs group/empty"
              >
                <div className="flex items-center gap-2 text-xs font-bold text-foreground group-hover/empty:text-primary transition-colors">
                  <Plus className="w-4 h-4 text-primary" />
                  <span>افزودن بلوک به این بخش</span>
                </div>
              </div>
            </div>
          )
        )
      ) : (
        renderWidgetContent()
      )}
    </div>
  );
}

export const CanvasElement = React.memo(CanvasElementComponent);
