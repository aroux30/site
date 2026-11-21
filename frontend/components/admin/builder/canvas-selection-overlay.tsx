"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
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
import { useToast } from "@/components/ui/use-toast";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { SaveTemplateDialog } from "./save-template-dialog";

interface CanvasSelectionOverlayProps {
  doc: Document | null;
  onContextMenu?: (e: React.MouseEvent, elementId: string) => void;
}

/**
 * Independent Selection & Hover Overlay Portal at canvas root (Elementor Parity).
 *
 * Renders selection outlines, hover highlights, and the floating action toolbar
 * at the root of the iframe document (`#builder-canvas-overlay-mount`), ensuring:
 * 1. Zero clipping by ancestor `overflow: hidden`, `clip`, or `border-radius`.
 * 2. Smart vertical flip when elements approach the top clearance threshold.
 * 3. Smooth tracking with ResizeObserver and window scroll listeners.
 * 4. Automatic `scrollIntoView` when off-screen elements are selected.
 */
export function CanvasSelectionOverlay({ doc, onContextMenu }: CanvasSelectionOverlayProps) {
  const { toast } = useToast();
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const hoveredElementId = useBuilderStore((s) => s.hoveredElementId);
  const previewMode = useBuilderStore((s) => s.previewMode);
  const ast = useBuilderStore((s) => s.ast);
  const activeBreakpoint = useBuilderStore((s) => s.activeBreakpoint);

  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const makeGlobalComponent = useBuilderStore((s) => s.makeGlobalComponent);

  const [selectedRect, setSelectedRect] = useState<DOMRect | null>(null);
  const [hoveredRect, setHoveredRect] = useState<DOMRect | null>(null);
  const [scrollPos, setScrollPos] = useState({ x: 0, y: 0 });
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const prevSelectedIdRef = useRef<string | null>(null);

  const selectedElement = selectedElementId
    ? findElementById(ast.rootElements, selectedElementId)
    : null;
  const isContainer = selectedElement?.type === "container";

  // Track selected element position and size
  const updateSelectedRect = useCallback(() => {
    if (!doc || !selectedElementId) {
      setSelectedRect(null);
      return;
    }
    const targetEl = doc.querySelector(`[data-element-id="${selectedElementId}"]`) as HTMLElement | null;
    if (!targetEl) {
      setSelectedRect(null);
      return;
    }
    const r = targetEl.getBoundingClientRect();
    const win = doc.defaultView || window;
    setSelectedRect(r);
    setScrollPos({ x: win.scrollX, y: win.scrollY });
  }, [doc, selectedElementId]);

  // Track hovered element position and size
  const updateHoveredRect = useCallback(() => {
    if (!doc || !hoveredElementId || hoveredElementId === selectedElementId) {
      setHoveredRect(null);
      return;
    }
    const targetEl = doc.querySelector(`[data-element-id="${hoveredElementId}"]`) as HTMLElement | null;
    if (!targetEl) {
      setHoveredRect(null);
      return;
    }
    const r = targetEl.getBoundingClientRect();
    setHoveredRect(r);
  }, [doc, hoveredElementId, selectedElementId]);

  useEffect(() => {
    updateSelectedRect();
    updateHoveredRect();
  }, [updateSelectedRect, updateHoveredRect, ast, activeBreakpoint]);

  // Listen for scroll, resize, and element selection changes
  useEffect(() => {
    if (!doc) return;
    const win = doc.defaultView || window;

    const onScrollOrResize = () => {
      updateSelectedRect();
      updateHoveredRect();
    };

    win.addEventListener("scroll", onScrollOrResize, { passive: true });
    win.addEventListener("resize", onScrollOrResize, { passive: true });

    let ro: ResizeObserver | null = null;
    if (selectedElementId) {
      const targetEl = doc.querySelector(`[data-element-id="${selectedElementId}"]`);
      if (targetEl) {
        ro = new ResizeObserver(() => updateSelectedRect());
        ro.observe(targetEl);
        if (doc.body) ro.observe(doc.body);

        // Auto scroll into view with top clearance if selected element is near or off-screen
        if (prevSelectedIdRef.current !== selectedElementId) {
          prevSelectedIdRef.current = selectedElementId;
          const rect = targetEl.getBoundingClientRect();
          if (rect.top < 45 || rect.bottom > win.innerHeight) {
            targetEl.scrollIntoView({ behavior: "instant", block: "center" });
            updateSelectedRect();
          }
        }
      }
    }

    return () => {
      win.removeEventListener("scroll", onScrollOrResize);
      win.removeEventListener("resize", onScrollOrResize);
      if (ro) ro.disconnect();
    };
  }, [doc, selectedElementId, updateSelectedRect, updateHoveredRect]);

  if (previewMode || (!selectedRect && !hoveredRect)) return null;

  const scrollX = scrollPos.x;
  const scrollY = scrollPos.y;
  const docWidth = doc?.documentElement?.clientWidth || doc?.body?.clientWidth || 760;

  // Compute smart vertical flip for toolbar
  let toolbarTop = 0;
  let toolbarLeft = 0;

  if (selectedRect) {
    // Place toolbar above element so it never covers child elements
    toolbarTop = selectedRect.top + scrollY - 32;
    if (toolbarTop < 4) toolbarTop = 4;

    // Strict horizontal boundary: toolbar width is up to ~380px.
    // Clamp so the toolbar and all its action buttons remain fully inside viewport.
    toolbarLeft = selectedRect.left + scrollX;
    if (toolbarLeft + 390 > docWidth) {
      toolbarLeft = Math.max(8, docWidth - 395);
    }
    if (toolbarLeft < 8) toolbarLeft = 8;
  }

  return (
    <>
      {/* ── Hover Highlight Box (Dashed sky outline) ─────────────────────── */}
      {hoveredRect && !selectedRect && (
        <div
          style={{
            position: "absolute",
            left: `${hoveredRect.left + scrollX}px`,
            top: `${hoveredRect.top + scrollY}px`,
            width: `${hoveredRect.width}px`,
            height: `${hoveredRect.height}px`,
            border: "1px dashed rgba(2, 132, 199, 0.85)",
            backgroundColor: "rgba(2, 132, 199, 0.04)",
            borderRadius: "4px",
            pointerEvents: "none",
            zIndex: 99980,
            transition: "all 0.05s ease-out",
          }}
        />
      )}

      {/* ── Selection Bounding Box (Solid primary ring) ─────────────────── */}
      {selectedRect && (
        <div
          style={{
            position: "absolute",
            left: `${selectedRect.left + scrollX}px`,
            top: `${selectedRect.top + scrollY}px`,
            width: `${selectedRect.width}px`,
            height: `${selectedRect.height}px`,
            boxShadow: "0 0 0 2px hsl(var(--primary)), 0 0 0 4px rgba(16, 185, 129, 0.2)",
            backgroundColor: "rgba(16, 185, 129, 0.03)",
            borderRadius: "4px",
            pointerEvents: "none",
            zIndex: 99990,
            transition: "all 0.05s ease-out",
          }}
        />
      )}

      {/* ── Floating Action Toolbar (Elementor Handles & Actions) ───────── */}
      {selectedRect && selectedElement && (
        <div
          data-testid="floating-toolbar"
          className="absolute flex items-center gap-1.5 bg-primary text-primary-foreground text-xs font-bold px-2.5 py-1 shadow-2xl rounded-lg border border-primary-foreground/20 transition-all pointer-events-auto select-none"
          style={{
            top: `${toolbarTop}px`,
            left: `${toolbarLeft}px`,
            zIndex: 99999,
            minWidth: "48px",
            minHeight: "28px",
          }}
          onClick={(e) => e.stopPropagation()}
          onContextMenu={(e) => {
            if (onContextMenu) {
              e.preventDefault();
              e.stopPropagation();
              onContextMenu(e, selectedElement.id);
            }
          }}
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

          <span className="pe-1 max-w-[120px] truncate">{selectedElement.name}</span>

          {selectedElement.isLocked && <Lock className="w-3.5 h-3.5 text-amber-200" />}
          {selectedElement.isHidden && <EyeOff className="w-3.5 h-3.5 text-primary-foreground/70" />}

          <div className="flex items-center gap-0.5 ms-1 border-s border-primary-foreground/30 ps-1">
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
              onClick={() => duplicateElement(selectedElement.id)}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="تکثیر"
            >
              <Copy className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={() => {
                useBuilderStore.getState().setLeftTab("blocks");
              }}
              className="p-1 hover:bg-primary-foreground/20 rounded transition"
              title="افزودن بلوک"
            >
              <Plus className="w-3.5 h-3.5" />
            </button>

            <button
              type="button"
              onClick={() => deleteElement(selectedElement.id)}
              className="p-1 hover:bg-destructive/80 rounded transition text-destructive-foreground"
              title="حذف"
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {selectedElement && isContainer && (
        <SaveTemplateDialog
          open={saveTemplateOpen}
          onOpenChange={setSaveTemplateOpen}
          element={selectedElement}
        />
      )}
    </>
  );
}
