"use client";

import React, { useEffect, useRef } from "react";
import {
  Copy,
  Clipboard,
  Palette,
  Trash2,
  BookmarkPlus,
  ArrowUp,
  ArrowDown,
  Lock,
  EyeOff,
  Plus,
} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { useBuilderStore, findElementById } from "@/stores/builder-store";

export interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  elementId: string | null;
}

interface BuilderContextMenuProps {
  menu: ContextMenuState;
  onClose: () => void;
  onSaveTemplate?: (elementId: string) => void;
}

export function BuilderContextMenu({
  menu,
  onClose,
  onSaveTemplate,
}: BuilderContextMenuProps) {
  const { toast } = useToast();
  const ast = useBuilderStore((s) => s.ast);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const pasteElement = useBuilderStore((s) => s.pasteElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const pasteStyles = useBuilderStore((s) => s.pasteStyles);
  const toggleLockElement = useBuilderStore((s) => s.toggleLockElement);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);

  const menuRef = useRef<HTMLDivElement>(null);

  const element = menu.elementId
    ? findElementById(ast.rootElements, menu.elementId)
    : null;
  const isContainer = element?.type === "container";

  // Close menu on click outside or escape key
  useEffect(() => {
    if (!menu.isOpen) return;

    const handleDown = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof KeyboardEvent && e.key === "Escape") {
        onClose();
        return;
      }
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    window.addEventListener("mousedown", handleDown);
    window.addEventListener("keydown", handleDown);
    return () => {
      window.removeEventListener("mousedown", handleDown);
      window.removeEventListener("keydown", handleDown);
    };
  }, [menu.isOpen, onClose]);

  if (!menu.isOpen || !element) return null;

  // Prevent menu from overflowing window
  const menuWidth = 220;
  const menuHeight = 320;
  const posX = Math.min(menu.x, window.innerWidth - menuWidth - 8);
  const posY = Math.min(menu.y, window.innerHeight - menuHeight - 8);

  return (
    <div
      ref={menuRef}
      data-testid="builder-context-menu"
      className="fixed z-[100000] min-w-[200px] rounded-xl border border-border/80 bg-popover/95 backdrop-blur-md p-1.5 shadow-2xl text-popover-foreground text-xs select-none animate-in fade-in zoom-in-95 duration-100"
      style={{
        left: `${posX}px`,
        top: `${posY}px`,
      }}
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="px-2 py-1 text-[11px] font-bold text-muted-foreground border-b border-border/60 mb-1 flex items-center justify-between">
        <span className="truncate">{element.name}</span>
        <span className="font-mono text-[9px] text-muted-foreground/80">{element.id}</span>
      </div>

      <div className="space-y-0.5">
        <button
          type="button"
          onClick={() => {
            duplicateElement(element.id);
            toast({ title: "المان تکثیر شد" });
            onClose();
          }}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <div className="flex items-center gap-2">
            <Plus className="w-3.5 h-3.5 text-primary" />
            <span>تکثیر (Duplicate)</span>
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">Ctrl+D</span>
        </button>

        <button
          type="button"
          onClick={() => {
            copyElement(element.id);
            toast({ title: "المان کپی شد", description: "در کلیپ‌بورد قرار گرفت." });
            onClose();
          }}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
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
            pasteElement(isContainer ? element.id : undefined);
            toast({ title: "المان درج شد" });
            onClose();
          }}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <div className="flex items-center gap-2">
            <Clipboard className="w-3.5 h-3.5 text-muted-foreground" />
            <span>چسباندن (Paste)</span>
          </div>
          <span className="text-[10px] text-muted-foreground font-mono">Ctrl+V</span>
        </button>

        <div className="h-px bg-border/60 my-1" />

        <button
          type="button"
          onClick={() => {
            copyStyles(element.id);
            toast({ title: "استایل‌ها کپی شد" });
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <Palette className="w-3.5 h-3.5 text-muted-foreground" />
          <span>کپی استایل‌ها</span>
        </button>

        <button
          type="button"
          onClick={() => {
            pasteStyles(element.id);
            toast({ title: "استایل‌ها اعمال شد" });
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <Palette className="w-3.5 h-3.5 text-primary" />
          <span>چسباندن استایل‌ها</span>
        </button>

        <div className="h-px bg-border/60 my-1" />

        <button
          type="button"
          onClick={() => {
            reorderElement(element.id, "up");
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <ArrowUp className="w-3.5 h-3.5 text-muted-foreground" />
          <span>انتقال به بالا</span>
        </button>

        <button
          type="button"
          onClick={() => {
            reorderElement(element.id, "down");
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <ArrowDown className="w-3.5 h-3.5 text-muted-foreground" />
          <span>انتقال به پایین</span>
        </button>

        {isContainer && onSaveTemplate && (
          <button
            type="button"
            onClick={() => {
              onSaveTemplate(element.id);
              onClose();
            }}
            className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-amber-500 text-start transition font-medium"
          >
            <BookmarkPlus className="w-3.5 h-3.5" />
            <span>ذخیره به عنوان قالب...</span>
          </button>
        )}

        <button
          type="button"
          onClick={() => {
            toggleLockElement(element.id);
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <Lock className="w-3.5 h-3.5 text-muted-foreground" />
          <span>{element.isLocked ? "باز کردن قفل" : "قفل کردن المان"}</span>
        </button>

        <button
          type="button"
          onClick={() => {
            toggleHideElement(element.id);
            onClose();
          }}
          className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg hover:bg-muted/80 text-start transition"
        >
          <EyeOff className="w-3.5 h-3.5 text-muted-foreground" />
          <span>{element.isHidden ? "نمایش المان" : "مخفی کردن المان"}</span>
        </button>

        <div className="h-px bg-border/60 my-1" />

        <button
          type="button"
          onClick={() => {
            deleteElement(element.id);
            toast({ title: "المان حذف شد", variant: "destructive" });
            onClose();
          }}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-destructive/10 text-destructive text-start transition font-semibold"
        >
          <div className="flex items-center gap-2">
            <Trash2 className="w-3.5 h-3.5" />
            <span>حذف (Delete)</span>
          </div>
          <span className="text-[10px] text-destructive/70 font-mono">Del</span>
        </button>
      </div>
    </div>
  );
}
