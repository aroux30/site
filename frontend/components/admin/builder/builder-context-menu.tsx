"use client";

import React, { useEffect, useState, useCallback, useRef } from "react";
import {
  Copy,
  Plus,
  Trash2,
  ArrowUp,
  ArrowDown,
  Palette,
  ClipboardPaste,
  BookmarkPlus,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Edit2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";
import { SaveTemplateDialog } from "./save-template-dialog";
import type { BuilderElement } from "@/types/builder";

interface ContextMenuPosition {
  x: number;
  y: number;
  targetId: string;
}

export function BuilderContextMenu() {
  const { toast } = useToast();
  const [pos, setPos] = useState<ContextMenuPosition | null>(null);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const ast = useBuilderStore((s) => s.ast);
  const clipboard = useBuilderStore((s) => s.clipboard);
  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const pasteElement = useBuilderStore((s) => s.pasteElement);
  const pasteStyles = useBuilderStore((s) => s.pasteStyles);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const toggleLockElement = useBuilderStore((s) => s.toggleLockElement);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);

  const activeElement: BuilderElement | null = pos?.targetId
    ? findElementById(ast.rootElements, pos.targetId)
    : null;

  const closeMenu = useCallback(() => setPos(null), []);

  // Listen for contextmenu events on both window and iframe
  useEffect(() => {
    const handleContextMenu = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (!target) return;

      const elemContainer = target.closest("[data-element-id]");
      if (elemContainer) {
        e.preventDefault();
        e.stopPropagation();
        const targetId = elemContainer.getAttribute("data-element-id");
        if (targetId) {
          selectElement(targetId);
          // Clamp within window bounds
          const menuWidth = 240;
          const menuHeight = 360;
          const x = Math.min(e.clientX, window.innerWidth - menuWidth - 8);
          const y = Math.min(e.clientY, window.innerHeight - menuHeight - 8);
          setPos({ x, y, targetId });
        }
      }
    };

    const handleIframeMessage = (e: MessageEvent) => {
      if (e.data?.type === "builder:contextmenu" && e.data.targetId) {
        selectElement(e.data.targetId);
        const menuWidth = 240;
        const menuHeight = 360;
        const x = Math.min(e.data.clientX, window.innerWidth - menuWidth - 8);
        const y = Math.min(e.data.clientY, window.innerHeight - menuHeight - 8);
        setPos({ x, y, targetId: e.data.targetId });
      }
    };

    window.addEventListener("contextmenu", handleContextMenu);
    window.addEventListener("message", handleIframeMessage);
    window.addEventListener("click", closeMenu);
    window.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeMenu();
    });

    return () => {
      window.removeEventListener("contextmenu", handleContextMenu);
      window.removeEventListener("message", handleIframeMessage);
      window.removeEventListener("click", closeMenu);
    };
  }, [selectElement, closeMenu]);

  if (!pos || !activeElement) return null;

  const isContainer = activeElement.type === "container";
  const hasClipboardElement = Boolean(clipboard.element);
  const hasClipboardStyles = Boolean(clipboard.styles);

  return (
    <>
      <div
        ref={menuRef}
        data-testid="builder-context-menu"
        style={{
          position: "fixed",
          top: pos.y,
          left: pos.x,
          zIndex: 999999,
        }}
        className="w-56 bg-popover/95 backdrop-blur-md text-popover-foreground border border-border shadow-2xl rounded-xl py-1.5 text-xs select-none animate-in fade-in zoom-in-95 duration-100"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="px-3 py-1.5 border-b border-border/60 text-[11px] font-bold text-muted-foreground flex items-center justify-between">
          <span className="truncate">{activeElement.name}</span>
          <span className="text-[10px] uppercase font-mono">{activeElement.widgetType || activeElement.type}</span>
        </div>

        <div className="py-1">
          <button
            type="button"
            onClick={() => {
              duplicateElement(activeElement.id);
              closeMenu();
            }}
            className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            <div className="flex items-center gap-2">
              <Plus className="w-3.5 h-3.5 text-primary" />
              <span>تکثیر</span>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">Ctrl+D</span>
          </button>

          <button
            type="button"
            onClick={() => {
              copyElement(activeElement.id);
              toast({ title: "المان کپی شد", description: "آماده چسباندن با Ctrl+V" });
              closeMenu();
            }}
            className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            <div className="flex items-center gap-2">
              <Copy className="w-3.5 h-3.5 text-muted-foreground" />
              <span>کپی المان</span>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">Ctrl+C</span>
          </button>

          <button
            type="button"
            onClick={() => {
              copyStyles(activeElement.id);
              toast({ title: "استایل‌ها کپی شد", description: "آماده اعمال روی المان دیگر" });
              closeMenu();
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            <Palette className="w-3.5 h-3.5 text-muted-foreground" />
            <span>کپی استایل‌ها</span>
          </button>

          <button
            type="button"
            disabled={!hasClipboardElement}
            onClick={() => {
              pasteElement(isContainer ? activeElement.id : undefined);
              closeMenu();
            }}
            className={cn(
              "w-full flex items-center justify-between px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start",
              !hasClipboardElement && "opacity-50 cursor-not-allowed"
            )}
          >
            <div className="flex items-center gap-2">
              <ClipboardPaste className="w-3.5 h-3.5 text-muted-foreground" />
              <span>چسباندن المان</span>
            </div>
            <span className="text-[10px] text-muted-foreground font-mono">Ctrl+V</span>
          </button>

          <button
            type="button"
            disabled={!hasClipboardStyles}
            onClick={() => {
              pasteStyles(activeElement.id);
              closeMenu();
            }}
            className={cn(
              "w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start",
              !hasClipboardStyles && "opacity-50 cursor-not-allowed"
            )}
          >
            <Palette className="w-3.5 h-3.5 text-primary" />
            <span>چسباندن استایل‌ها</span>
          </button>
        </div>

        <div className="border-t border-border/60 py-1">
          <button
            type="button"
            onClick={() => {
              reorderElement(activeElement.id, "up");
              closeMenu();
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            <ArrowUp className="w-3.5 h-3.5 text-muted-foreground" />
            <span>انتقال به بالا</span>
          </button>

          <button
            type="button"
            onClick={() => {
              reorderElement(activeElement.id, "down");
              closeMenu();
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            <ArrowDown className="w-3.5 h-3.5 text-muted-foreground" />
            <span>انتقال به پایین</span>
          </button>

          {isContainer && (
            <button
              type="button"
              onClick={() => {
                setSaveTemplateOpen(true);
                closeMenu();
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start text-amber-500 font-semibold"
            >
              <BookmarkPlus className="w-3.5 h-3.5" />
              <span>ذخیره به عنوان قالب...</span>
            </button>
          )}

          <button
            type="button"
            onClick={() => {
              toggleLockElement(activeElement.id);
              closeMenu();
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            {activeElement.isLocked ? <Unlock className="w-3.5 h-3.5 text-amber-500" /> : <Lock className="w-3.5 h-3.5 text-muted-foreground" />}
            <span>{activeElement.isLocked ? "باز کردن قفل" : "قفل کردن المان"}</span>
          </button>

          <button
            type="button"
            onClick={() => {
              toggleHideElement(activeElement.id);
              closeMenu();
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 hover:bg-accent hover:text-accent-foreground transition text-start"
          >
            {activeElement.isHidden ? <Eye className="w-3.5 h-3.5 text-primary" /> : <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />}
            <span>{activeElement.isHidden ? "نمایش المان" : "مخفی کردن"}</span>
          </button>
        </div>

        <div className="border-t border-border/60 pt-1">
          <button
            type="button"
            onClick={() => {
              deleteElement(activeElement.id);
              closeMenu();
            }}
            className="w-full flex items-center justify-between px-3 py-1.5 hover:bg-destructive hover:text-destructive-foreground transition text-start text-destructive font-semibold"
          >
            <div className="flex items-center gap-2">
              <Trash2 className="w-3.5 h-3.5" />
              <span>حذف</span>
            </div>
            <span className="text-[10px] font-mono">Del</span>
          </button>
        </div>
      </div>

      {isContainer && (
        <SaveTemplateDialog
          element={activeElement}
          open={saveTemplateOpen}
          onOpenChange={setSaveTemplateOpen}
        />
      )}
    </>
  );
}
