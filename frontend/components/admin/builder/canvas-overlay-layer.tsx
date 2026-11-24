"use client";

import React, { useEffect, useState, useRef, useCallback } from "react";
import {
  GripVertical,
  Plus,
  Trash2,
  Copy,
  ArrowUp,
  ArrowDown,
  Palette,
  Globe,
  BookmarkPlus,
  Lock,
  EyeOff,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";
import { SaveTemplateDialog } from "./save-template-dialog";
import type { BuilderElement } from "@/types/builder";

interface ElementRect {
  top: number;
  left: number;
  width: number;
  height: number;
}

export function CanvasOverlayLayer({
  doc,
}: {
  doc: Document | null;
}) {
  const { toast } = useToast();
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const selectedElementIds = useBuilderStore((s) => s.selectedElementIds);
  const hoveredElementId = useBuilderStore((s) => s.hoveredElementId);
  const previewMode = useBuilderStore((s) => s.previewMode);
  const ast = useBuilderStore((s) => s.ast);

  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const deleteSelectedElements = useBuilderStore((s) => s.deleteSelectedElements);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const makeGlobalComponent = useBuilderStore((s) => s.makeGlobalComponent);

  const [selectedRect, setSelectedRect] = useState<ElementRect | null>(null);
  const [multiRects, setMultiRects] = useState<{ id: string; rect: ElementRect }[]>([]);
  const [hoveredRect, setHoveredRect] = useState<ElementRect | null>(null);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);

  const selectedElement: BuilderElement | null = selectedElementId
    ? findElementById(ast.rootElements, selectedElementId)
    : null;

  // Measure DOM node in the iframe
  const updateRects = useCallback(() => {
    if (!doc || previewMode) {
      setSelectedRect(null);
      setHoveredRect(null);
      return;
    }

    const win = doc.defaultView || window;
    const scrollX = win.scrollX || 0;
    const scrollY = win.scrollY || 0;

    // 1. Measure selected element & multi-selection
    if (selectedElementIds.length > 1) {
      const rects: { id: string; rect: ElementRect }[] = [];
      for (const id of selectedElementIds) {
        const el = doc.querySelector(`[data-element-id="${id}"]`);
        if (el) {
          const b = el.getBoundingClientRect();
          rects.push({
            id,
            rect: {
              top: b.top + scrollY,
              left: b.left + scrollX,
              width: b.width,
              height: b.height,
            },
          });
        }
      }
      setMultiRects(rects);
    } else {
      setMultiRects([]);
    }

    if (selectedElementId) {
      const el = doc.querySelector(`[data-element-id="${selectedElementId}"]`);
      if (el) {
        const b = el.getBoundingClientRect();
        setSelectedRect({
          top: b.top + scrollY,
          left: b.left + scrollX,
          width: b.width,
          height: b.height,
        });
      } else {
        setSelectedRect(null);
      }
    } else {
      setSelectedRect(null);
    }

    // 2. Measure hovered element
    if (hoveredElementId && hoveredElementId !== selectedElementId) {
      const el = doc.querySelector(`[data-element-id="${hoveredElementId}"]`);
      if (el) {
        const b = el.getBoundingClientRect();
        setHoveredRect({
          top: b.top + scrollY,
          left: b.left + scrollX,
          width: b.width,
          height: b.height,
        });
      } else {
        setHoveredRect(null);
      }
    } else {
      setHoveredRect(null);
    }
  }, [doc, previewMode, selectedElementId, hoveredElementId]);

  // Auto scroll into view on selection change
  useEffect(() => {
    if (!doc || !selectedElementId || previewMode) return;
    const targetEl = doc.querySelector(`[data-element-id="${selectedElementId}"]`);
    if (targetEl) {
      const b = targetEl.getBoundingClientRect();
      const win = doc.defaultView || window;
      const viewHeight = win.innerHeight;
      const isOutOfView = b.top < 0 || b.bottom > viewHeight;
      if (isOutOfView) {
        targetEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  }, [doc, selectedElementId, previewMode]);

  // Keep overlay rects in sync with scroll, resize, and DOM mutations
  useEffect(() => {
    if (!doc) return;
    const win = doc.defaultView || window;

    updateRects();

    let animFrame: number;
    const handleScrollOrResize = () => {
      cancelAnimationFrame(animFrame);
      animFrame = requestAnimationFrame(updateRects);
    };

    win.addEventListener("scroll", handleScrollOrResize, { passive: true, capture: true });
    win.addEventListener("resize", handleScrollOrResize, { passive: true });

    const ro = new ResizeObserver(updateRects);
    if (doc.body) ro.observe(doc.body);

    const mo = new MutationObserver(updateRects);
    if (doc.body) {
      mo.observe(doc.body, { attributes: true, childList: true, subtree: true });
    }

    return () => {
      cancelAnimationFrame(animFrame);
      win.removeEventListener("scroll", handleScrollOrResize, true);
      win.removeEventListener("resize", handleScrollOrResize);
      ro.disconnect();
      mo.disconnect();
    };
  }, [doc, updateRects]);

  if (previewMode || !doc) return null;

  const win = doc.defaultView || window;
  const docWidth = doc.documentElement?.clientWidth || win.innerWidth || 1200;

  // Toolbar position calculation
  let toolbarTop = 0;
  let toolbarLeft = 0;
  const TOOLBAR_HEIGHT = 36;
  const TOOLBAR_WIDTH = 420;

  if (selectedRect) {
    const scrollY = win.scrollY || 0;
    const viewportTop = selectedRect.top - scrollY;
    const viewportBottom = viewportTop + selectedRect.height;

    // Sticky / Tall Section Clearance:
    // If element is tall and its top has scrolled past or is at the very top edge,
    // position toolbar inside the top of the visible area so it never vanishes below or gets clipped.
    if (viewportTop < TOOLBAR_HEIGHT + 4) {
      if (selectedRect.height > 250 && viewportBottom > TOOLBAR_HEIGHT + 40) {
        toolbarTop = Math.max(selectedRect.top + 8, scrollY + 8);
      } else if (selectedRect.top < TOOLBAR_HEIGHT + 4) {
        toolbarTop = selectedRect.top + selectedRect.height + 4;
      } else {
        toolbarTop = Math.max(2, selectedRect.top - TOOLBAR_HEIGHT - 4);
      }
    } else {
      toolbarTop = Math.max(2, selectedRect.top - TOOLBAR_HEIGHT - 4);
    }

    // In RTL, align toolbar with the start of the element, strictly clamped within document bounds
    toolbarLeft = Math.max(16, Math.min(selectedRect.left, docWidth - TOOLBAR_WIDTH - 16));
  }

  const isContainer = selectedElement?.type === "container";

  return (
    <>
      {/* 1. Hover Box */}
      {hoveredRect && (
        <div
          data-testid="overlay-hover-box"
          style={{
            position: "absolute",
            top: hoveredRect.top,
            left: hoveredRect.left,
            width: hoveredRect.width,
            height: hoveredRect.height,
            pointerEvents: "none",
            zIndex: 99990,
          }}
          className="outline-dashed outline-1 outline-sky-500/80 bg-sky-500/5 transition-all duration-75 rounded-sm"
        />
      )}

      {/* 2. Selection Box */}
      {selectedRect && selectedElement && (
        <>
          <div
            data-testid="overlay-selection-box"
            style={{
              position: "absolute",
              top: selectedRect.top,
              left: selectedRect.left,
              width: selectedRect.width,
              height: selectedRect.height,
              pointerEvents: "none",
              zIndex: 99995,
            }}
            className="outline outline-2 outline-primary ring-2 ring-primary/20 bg-primary/5 transition-all duration-75 rounded-sm shadow-sm"
          />

          {/* Additional Multi-Selection Boxes */}
          {multiRects.map((mr) => (
            <div
              key={mr.id}
              data-testid="overlay-multi-box"
              style={{
                position: "absolute",
                top: mr.rect.top,
                left: mr.rect.left,
                width: mr.rect.width,
                height: mr.rect.height,
                pointerEvents: "none",
                zIndex: 99994,
              }}
              className="outline outline-2 outline-sky-500 ring-2 ring-sky-500/20 bg-sky-500/5 transition-all duration-75 rounded-sm shadow-sm"
            />
          ))}

          {/* 3. Independent Floating Action Toolbar */}
          <div
            data-testid="floating-toolbar"
            style={{
              position: "absolute",
              top: toolbarTop,
              left: toolbarLeft,
              zIndex: 100000,
              pointerEvents: "auto",
            }}
            className="flex items-center gap-1.5 bg-primary text-primary-foreground text-xs font-bold px-2.5 py-1.5 rounded-lg shadow-2xl border border-primary-foreground/20 transition-all select-none animate-in fade-in zoom-in-95 duration-100"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Native HTML5 drag handle */}
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
              className="cursor-grab active:cursor-grabbing p-1 hover:bg-primary-foreground/20 rounded shrink-0"
              title="جابه‌جایی"
            >
              <GripVertical className="w-3.5 h-3.5" />
            </span>

            <span className="pe-1 max-w-[120px] truncate">{selectedElement.name}</span>

            {selectedElement.isLocked && <Lock className="w-3.5 h-3.5 text-amber-200 shrink-0" />}
            {selectedElement.isHidden && <EyeOff className="w-3.5 h-3.5 text-primary-foreground/70 shrink-0" />}

            <div className="flex items-center gap-0.5 ms-1 border-s border-primary-foreground/30 ps-1.5">
              {selectedElement.globalComponentId ? (
                <span className="flex items-center gap-1 text-[10px] text-emerald-300 font-bold px-1" title="کامپوننت سراسری همگام">
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
                data-testid="overlay-duplicate-btn"
                onClick={() => duplicateElement(selectedElement.id)}
                className="p-1 hover:bg-primary-foreground/20 rounded transition"
                title="تکثیر (Duplicate)"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                data-testid="overlay-delete-btn"
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
              element={selectedElement}
              open={saveTemplateOpen}
              onOpenChange={setSaveTemplateOpen}
            />
          )}
        </>
      )}
    </>
  );
}
