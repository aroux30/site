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
import { Badge } from "@/components/ui/badge";
import { useCartStore } from "@/stores/cart-store";
import { useToast } from "@/components/ui/use-toast";
import { normalizeCssColor } from "@/lib/builder/color-utils";
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
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const makeGlobalComponent = useBuilderStore((s) => s.makeGlobalComponent);
  const previewMode = useBuilderStore((s) => s.previewMode);

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
        styleObj.backgroundImage = `linear-gradient(${bgObj.gradient.direction.replace("to-", "to ")}, ${bgObj.gradient.fromColor}, ${bgObj.gradient.toColor})`;
      } else if (bgObj.type === "image" && bgObj.imageUrl) {
        styleObj.backgroundImage = `url(${bgObj.imageUrl})`;
        styleObj.backgroundPosition = bgObj.position || "center";
        styleObj.backgroundSize = bgObj.size || "cover";
      }
    }

    // Animation styles
    if (res.animation && res.animation !== "none") {
      if (res.animationDuration) styleObj.animationDuration = `${res.animationDuration}s`;
      if (res.animationDelay) styleObj.animationDelay = `${res.animationDelay}s`;
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

    return styleObj;
  }, [element.styles, activeBreakpoint]);

  const isHiddenOnActiveBreakpoint = useMemo(() => {
    if (activeBreakpoint === "desktop" && element.visibleOnDesktop === false) return true;
    if (activeBreakpoint === "tablet" && element.visibleOnTablet === false) return true;
    if (activeBreakpoint === "mobile" && element.visibleOnMobile === false) return true;
    return false;
  }, [activeBreakpoint, element.visibleOnDesktop, element.visibleOnTablet, element.visibleOnMobile]);

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
          <Tag className="font-bold tracking-tight text-foreground m-0 break-words [overflow-wrap:anywhere]">
            {String(props.text || "عنوان سرتیتر")}
          </Tag>
        );
      }
      case "text_editor": {
        return (
          <div
            className="prose dark:prose-invert max-w-none text-foreground/90 leading-relaxed break-words [overflow-wrap:anywhere]"
            dangerouslySetInnerHTML={{
              __html: String(props.content || "<p>متن پاراگراف را بنویسید...</p>"),
            }}
          />
        );
      }
      case "button": {
        const customClass = String(props.customCssClass || element.styles?.customCssClass || "");
        return (
          <div className="inline-block">
            <span
              className={cn(
                "inline-flex items-center justify-center rounded-xl bg-primary px-6 py-3 font-semibold text-primary-foreground shadow-sm transition",
                customClass
              )}
            >
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
      case "product_grid": {
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
                  onClick={() => setActiveGridFilter(f.key)}
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
        return (
          <div className="w-full">
            <RecentlyViewed limit={Number(props.limit) || 4} />
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
        return (
          <div className="p-4 rounded-2xl border border-border/80 bg-card space-y-3 shadow-sm w-full max-w-sm">
            <div className="flex items-center justify-between border-b pb-2">
              <span className="text-xs font-bold text-foreground">خلاصه سبد خرید</span>
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
            <button
              type="button"
              className="w-full py-2.5 rounded-xl bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs transition shadow"
            >
              ادامه فرآیند خرید
            </button>
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
        return (
          <div className="space-y-1 w-full text-right pointer-events-none">
            {label && <label className="block text-xs font-semibold text-foreground">{label}</label>}
            <input
              type={inputType}
              placeholder={placeholder}
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
        return (
          <div className="space-y-1 w-full text-right pointer-events-none">
            {label && <label className="block text-xs font-semibold text-foreground">{label}</label>}
            <textarea
              placeholder={placeholder}
              rows={rowsNum}
              readOnly
              className="w-full rounded-xl border border-input bg-background p-3 text-sm"
            />
          </div>
        );
      }
      case "form_select": {
        const label = String(props.label || "");
        const options = (props.options as string[]) || ["گزینه ۱", "گزینه ۲"];
        return (
          <div className="space-y-1 w-full text-right pointer-events-none">
            {label && <label className="block text-xs font-semibold text-foreground">{label}</label>}
            <select className="w-full rounded-xl border border-input bg-background px-4 py-2.5 text-sm" disabled>
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
        return (
          <div className="p-4 rounded-2xl bg-card border border-border/80 text-center space-y-3 shadow-sm w-full">
            <h3 className="font-bold text-sm text-foreground">{title}</h3>
            <div className="flex items-center justify-center gap-2 text-center" dir="ltr">
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">۰۲</span>
                <span className="text-[10px] text-muted-foreground">روز</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">۱۴</span>
                <span className="text-[10px] text-muted-foreground">ساعت</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">۳۵</span>
                <span className="text-[10px] text-muted-foreground">دقیقه</span>
              </div>
              <span className="font-bold text-primary">:</span>
              <div className="bg-muted/60 p-2 rounded-xl min-w-[50px]">
                <span className="block text-lg font-black text-primary">۴۸</span>
                <span className="text-[10px] text-muted-foreground">ثانیه</span>
              </div>
            </div>
          </div>
        );
      }
      case "icon_box": {
        const title = String(props.title || "ارسال سریع و مطمئن");
        const desc = String(props.description || "تحویل در کمترین زمان ممکن با بسته‌بندی ویژه به سراسر کشور");
        return (
          <div className="p-4 rounded-2xl border border-border/80 bg-card flex items-start gap-3 shadow-sm w-full">
            <div className="w-10 h-10 rounded-xl bg-primary/10 text-primary flex items-center justify-center shrink-0">
              <Sparkles className="w-5 h-5" />
            </div>
            <div className="space-y-1 text-right">
              <h4 className="font-bold text-xs text-foreground">{title}</h4>
              <p className="text-[11px] text-muted-foreground leading-relaxed">{desc}</p>
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
        !previewMode && "outline outline-1 outline-transparent transition-all",
        !previewMode && isHovered && "outline-dashed outline-sky-500/80 bg-sky-500/5",
        !previewMode && isSelected && "outline-2 outline-primary ring-2 ring-primary/20 bg-primary/5 shadow-md z-40 relative",
        !previewMode && isDragOver && "outline-2 outline-emerald-500 bg-emerald-500/10 shadow-lg ring-2 ring-emerald-500/30",
        element.isHidden && "opacity-50",
        element.styles?.animation && element.styles.animation !== "none" && `builder-animate-${element.styles.animation}`,
        element.styles?.customCssClass
      )}
      data-element-id={element.id}
    >
      {/* Floating Action Toolbar on Selected Element */}
      {!previewMode && isSelected && (
        <div
          data-testid="floating-toolbar"
          className={cn(
            "absolute start-0 flex items-center gap-1.5 bg-primary text-primary-foreground text-xs font-bold px-2.5 py-1 shadow-xl z-50 pointer-events-auto border border-primary-foreground/20 transition-all",
            isNearTop ? "top-full mt-1.5 rounded-lg" : "-top-8 rounded-t-lg"
          )}
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
            className="cursor-grab active:cursor-grabbing p-1 hover:bg-primary-foreground/20 rounded"
            title="جابه‌جایی"
          >
            <GripVertical className="w-3.5 h-3.5" />
          </span>

          <span className="pe-1">{element.name}</span>

          {element.isLocked && <Lock className="w-3.5 h-3.5 text-amber-200" />}
          {element.isHidden && <EyeOff className="w-3.5 h-3.5 text-primary-foreground/70" />}

          <div className="flex items-center gap-0.5 ms-2 border-s border-primary-foreground/30 ps-1.5">
            {element.globalComponentId ? (
              <span className="flex items-center gap-1 text-[10px] text-emerald-300 font-bold px-1" title="کامپوننت سراسری همگام">
                <Globe className="w-3.5 h-3.5 animate-pulse" />
                <span>همگام</span>
              </span>
            ) : (
              <button
                type="button"
                onClick={() => {
                  makeGlobalComponent(element.id);
                  toast({
                    title: "کامپوننت سراسری ایجاد شد",
                    description: "این المان اکنون در سراسر برگه به عنوان کامپوننت همگام شناخته می‌شود.",
                  });
                }}
                className="p-1 hover:bg-primary-foreground/20 rounded transition text-emerald-300 hover:text-white"
                title="تبدیل به کامپوننت همگام سراسری (Global Component)"
              >
                <Globe className="w-3.5 h-3.5" />
              </button>
            )}

            <button
              type="button"
              onClick={() => {
                copyElement(element.id);
                toast({
                  title: "المان کپی شد",
                  description: "المان در کلیپ‌بورد ذخیره شد. برای درج از Ctrl+V استفاده نمایید.",
                });
              }}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="کپی المان (Ctrl+C)"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={() => {
                copyStyles(element.id);
                toast({
                  title: "استایل‌ها کپی شد",
                  description: "استایل‌های المان در کلیپ‌بورد قرار گرفت.",
                });
              }}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="کپی استایل‌ها (Copy Styles)"
            >
              <Palette className="w-3.5 h-3.5" />
            </button>

            {isContainer && (
              <button
                type="button"
                onClick={() => setSaveTemplateOpen(true)}
                className="p-1 hover:bg-primary-foreground/20 rounded transition text-amber-200 hover:text-white"
                title="ذخیره به عنوان قالب (Save as Template)"
              >
                <BookmarkPlus className="w-3.5 h-3.5" />
              </button>
            )}
            <button
              type="button"
              onClick={() => duplicateElement(element.id)}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="تکثیر (Duplicate)"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={() => deleteElement(element.id)}
              className="p-1 hover:bg-destructive hover:text-white rounded transition text-destructive-foreground"
              title="حذف"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
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

      {/* Form Container Identifier */}
      {element.widgetType === "form_container" && !previewMode && (
        <div className="absolute top-1 start-1 z-20 pointer-events-none">
          <Badge variant="outline" className="bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-300 text-[9px] px-1.5 py-0 h-4">
            فرم سازنده (Form Container)
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
            <div
              onClick={(e) => {
                e.stopPropagation();
                selectElement(element.id);
                useBuilderStore.getState().setLeftTab("blocks");
              }}
              data-testid="empty-container-guide"
              className="flex flex-col items-center justify-center p-6 border-2 border-dashed border-primary/40 hover:border-primary/80 rounded-2xl bg-card/60 hover:bg-primary/5 transition-all cursor-pointer text-center w-full min-h-[96px] my-1 shadow-xs group/empty"
            >
              <div className="w-8 h-8 rounded-full bg-primary/10 text-primary flex items-center justify-center mb-1.5 group-hover/empty:bg-primary group-hover/empty:text-primary-foreground transition-colors shadow-xs">
                <Plus className="w-4 h-4" />
              </div>
              <span className="text-xs font-bold text-foreground group-hover/empty:text-primary transition-colors">
                + افزودن بلوک به این بخش
              </span>
              <span className="text-[10px] text-muted-foreground mt-0.5">
                کانتینر آماده درج محتوا است (برای انتخاب و افزودن کلیک کنید)
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

export const CanvasElement = React.memo(CanvasElementComponent);
