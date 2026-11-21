"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
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
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBuilderStore, findElementById, type Breakpoint } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";
import { SaveTemplateDialog } from "./save-template-dialog";
import type { BuilderElement } from "@/types/builder";

interface CanvasOverlayProps {
  activeBreakpoint: Breakpoint;
  canvasRootRef: React.RefObject<HTMLDivElement | null>;
}

export function CanvasOverlay({ activeBreakpoint, canvasRootRef }: CanvasOverlayProps) {
  const { toast } = useToast();
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const previewMode = useBuilderStore((s) => s.previewMode);
  const ast = useBuilderStore((s) => s.ast);

  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const makeGlobalComponent = useBuilderStore((s) => s.makeGlobalComponent);

  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [overlayRect, setOverlayRect] = useState<{
    top: number;
    left: number;
    width: number;
    height: number;
    isNearCeiling: boolean;
    viewportWidth: number;
  } | null>(null);

  const selectedElement = selectedElementId
    ? findElementById(ast.rootElements, selectedElementId)
    : null;

  const updatePosition = useCallback(() => {
    if (!selectedElementId || previewMode || !canvasRootRef.current) {
      setOverlayRect(null);
      return;
    }

    const doc = canvasRootRef.current.ownerDocument;
    const win = doc.defaultView || window;
    const domEl = doc.querySelector(`[data-element-id="${selectedElementId}"]`) as HTMLElement | null;
    if (!domEl) {
      setOverlayRect(null);
      return;
    }

    const elRect = domEl.getBoundingClientRect();
    const rootRect = canvasRootRef.current.getBoundingClientRect();
    const viewportWidth = doc.documentElement.clientWidth || win.innerWidth || 766;

    const top = elRect.top - rootRect.top;
    const left = elRect.left - rootRect.left;
    const width = elRect.width;
    const height = elRect.height;
    // Only flip when element itself is scrolled into the top 32px of the viewport
    const isNearCeiling = elRect.top < 32;

    setOverlayRect({
      top,
      left,
      width,
      height,
      isNearCeiling,
      viewportWidth,
    });
  }, [selectedElementId, previewMode, canvasRootRef]);

  // Track element bounding box changes, scroll, resize, mutation
  useEffect(() => {
    if (!selectedElementId || previewMode || !canvasRootRef.current) {
      setOverlayRect(null);
      return;
    }

    const doc = canvasRootRef.current.ownerDocument;
    const win = doc.defaultView || window;
    const domEl = doc.querySelector(`[data-element-id="${selectedElementId}"]`) as HTMLElement | null;

    updatePosition();

    // Auto-scroll into view if outside visible canvas area
    if (domEl) {
      const r = domEl.getBoundingClientRect();
      if (r.top < 0 || r.bottom > win.innerHeight) {
        domEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }

    let resizeObserver: ResizeObserver | null = null;
    if (domEl && typeof ResizeObserver !== "undefined") {
      resizeObserver = new ResizeObserver(() => {
        updatePosition();
      });
      resizeObserver.observe(domEl);
      if (canvasRootRef.current) {
        resizeObserver.observe(canvasRootRef.current);
      }
    }

    const handleScrollOrResize = () => {
      updatePosition();
    };

    win.addEventListener("scroll", handleScrollOrResize, true);
    win.addEventListener("resize", handleScrollOrResize, true);

    const mutationObserver = new MutationObserver(() => {
      updatePosition();
    });
    mutationObserver.observe(canvasRootRef.current, {
      childList: true,
      subtree: true,
      attributes: true,
    });

    return () => {
      if (resizeObserver) resizeObserver.disconnect();
      mutationObserver.disconnect();
      win.removeEventListener("scroll", handleScrollOrResize, true);
      win.removeEventListener("resize", handleScrollOrResize, true);
    };
  }, [selectedElementId, previewMode, canvasRootRef, ast, updatePosition]);

  if (!selectedElement || !overlayRect || previewMode) {
    return null;
  }

  const isContainer = selectedElement.type === "container";
  // Elementor-style handle positioning:
  // Default: Sits directly above the element top border (-34px).
  // Flip: Sits below the element bottom border (+6px) ONLY when the element's top touches the iframe ceiling (<= 32px).
  const toolbarTop = overlayRect.isNearCeiling
    ? overlayRect.top + overlayRect.height + 6
    : overlayRect.top - 34;

  // Clamp toolbar left so it never overflows off-screen
  const maxLeft = Math.max(4, overlayRect.viewportWidth - 370);
  const toolbarLeft = Math.min(Math.max(4, overlayRect.left), maxLeft);

  return (
    <div
      data-testid="canvas-overlay-portal"
      className="absolute inset-0 !m-0 pointer-events-none z-[9999] overflow-visible"
      style={{ margin: 0 }}
    >
      {/* 1. Selection Outline Box (Overlay) */}
      <div
        className="absolute border-2 border-primary ring-2 ring-primary/20 bg-primary/5 rounded transition-all pointer-events-none"
        style={{
          top: `${overlayRect.top}px`,
          left: `${overlayRect.left}px`,
          width: `${overlayRect.width}px`,
          height: `${overlayRect.height}px`,
        }}
      />

      {/* 2. Floating Action Toolbar (Overlay Portal) */}
      <div
        data-testid="floating-toolbar"
        className={cn(
          "absolute flex items-center gap-1.5 bg-primary text-primary-foreground text-xs font-bold px-2.5 py-1 shadow-2xl z-[10000] pointer-events-auto border border-primary-foreground/20 rounded-md transition-all select-none"
        )}
        style={{
          top: `${toolbarTop}px`,
          left: `${toolbarLeft}px`,
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Drag Handle */}
        <span
          draggable={!selectedElement.isLocked}
          onDragStart={(e) => {
            e.stopPropagation();
            e.dataTransfer.setData(
              "application/json",
              JSON.stringify({ type: "element", elementId: selectedElement.id })
            );
            e.dataTransfer.effectAllowed = "move";
          }}
          className="cursor-grab active:cursor-grabbing p-1 hover:bg-primary-foreground/20 rounded"
          title="جابه‌جایی"
        >
          <GripVertical className="w-3.5 h-3.5" />
        </span>

        <span className="pe-1 text-xs truncate max-w-[140px]">{selectedElement.name}</span>

        {selectedElement.isLocked && <Lock className="w-3.5 h-3.5 text-amber-200 shrink-0" />}
        {selectedElement.isHidden && <EyeOff className="w-3.5 h-3.5 text-primary-foreground/70 shrink-0" />}

        <div className="flex items-center gap-0.5 ms-2 border-s border-primary-foreground/30 ps-1.5 shrink-0">
          {selectedElement.globalComponentId ? (
            <span
              className="flex items-center gap-1 text-[10px] text-emerald-300 font-bold px-1"
              title="کامپوننت سراسری همگام"
            >
              <Globe className="w-3.5 h-3.5 animate-pulse" />
              <span>همگام</span>
            </span>
          ) : (
            <button
              type="button"
              onClick={() => {
                makeGlobalComponent(selectedElement.id);
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
              copyElement(selectedElement.id);
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
              copyStyles(selectedElement.id);
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
            onClick={() => reorderElement(selectedElement.id, "up")}
            className="p-1 hover:bg-primary-foreground/20 rounded transition"
            title="انتقال به بالا (Move Up)"
            data-testid="move-up-btn"
          >
            <ArrowUp className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => reorderElement(selectedElement.id, "down")}
            className="p-1 hover:bg-primary-foreground/20 rounded transition"
            title="انتقال به پایین (Move Down)"
            data-testid="move-down-btn"
          >
            <ArrowDown className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => duplicateElement(selectedElement.id)}
            className="p-1 hover:bg-primary-foreground/20 rounded transition"
            title="تکثیر (Duplicate)"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>

          <button
            type="button"
            onClick={() => deleteElement(selectedElement.id)}
            className="p-1 hover:bg-destructive hover:text-white rounded transition text-destructive-foreground"
            title="حذف"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {isContainer && (
        <SaveTemplateDialog
          open={saveTemplateOpen}
          onOpenChange={setSaveTemplateOpen}
          element={selectedElement}
        />
      )}
    </div>
  );
}
