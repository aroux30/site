"use client";

import React, { useEffect } from "react";
import {
  Copy,
  Scissors,
  Clipboard,
  Trash2,
  Plus,
  ArrowUp,
  ArrowDown,
  Palette,
  BookmarkPlus,
  Edit,
  Eye,
  EyeOff,
  Lock,
} from "lucide-react";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";
import type { BuilderElement } from "@/types/builder";

export interface ContextMenuState {
  isOpen: boolean;
  x: number;
  y: number;
  elementId: string | null;
}

interface BuilderContextMenuProps {
  state: ContextMenuState;
  onClose: () => void;
  onOpenSaveTemplate?: (el: BuilderElement) => void;
}

export function BuilderContextMenu({
  state,
  onClose,
  onOpenSaveTemplate,
}: BuilderContextMenuProps) {
  const { toast } = useToast();
  const ast = useBuilderStore((s) => s.ast);
  const clipboard = useBuilderStore((s) => s.clipboard);

  const selectElement = useBuilderStore((s) => s.selectElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const reorderElement = useBuilderStore((s) => s.reorderElement);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const pasteElement = useBuilderStore((s) => s.pasteElement);
  const copyStyles = useBuilderStore((s) => s.copyStyles);
  const pasteStyles = useBuilderStore((s) => s.pasteStyles);
  const toggleHideElement = useBuilderStore((s) => s.toggleHideElement);
  const toggleLockElement = useBuilderStore((s) => s.toggleLockElement);

  // Close on outside click or Escape
  useEffect(() => {
    if (!state.isOpen) return;

    const handlePointerDown = (e: MouseEvent) => {
      const menuEl = document.getElementById("builder-context-menu");
      if (menuEl && !menuEl.contains(e.target as Node)) {
        onClose();
      }
    };

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    window.addEventListener("pointerdown", handlePointerDown, true);
    window.addEventListener("keydown", handleKeyDown, true);
    return () => {
      window.removeEventListener("pointerdown", handlePointerDown, true);
      window.removeEventListener("keydown", handleKeyDown, true);
    };
  }, [state.isOpen, onClose]);

  if (!state.isOpen || !state.elementId) return null;

  const targetEl = findElementById(ast.rootElements, state.elementId);
  if (!targetEl) return null;

  const isContainer = targetEl.type === "container";
  const hasClipboardElement = Boolean(clipboard.element);
  const hasClipboardStyles = Boolean(clipboard.styles);

  return (
    <div
      id="builder-context-menu"
      data-testid="builder-context-menu"
      className="fixed z-[99999] bg-card text-foreground border border-border shadow-2xl rounded-xl p-1.5 min-w-[200px] text-xs font-medium space-y-0.5 select-none animate-in fade-in zoom-in-95 duration-100"
      style={{
        top: `${Math.min(state.y, window.innerHeight - 340)}px`,
        left: `${Math.min(state.x, window.innerWidth - 220)}px`,
      }}
      dir="rtl"
      onClick={(e) => e.stopPropagation()}
      onContextMenu={(e) => e.preventDefault()}
    >
      <div className="px-2 py-1 text-[10px] font-bold text-muted-foreground border-b border-border/60 mb-1 flex items-center justify-between">
        <span className="truncate max-w-[140px]">{targetEl.name}</span>
        <span className="font-mono text-[9px] opacity-70">{targetEl.type}</span>
      </div>

      {/* Edit / Select */}
      <button
        type="button"
        onClick={() => {
          selectElement(targetEl.id);
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <Edit className="w-3.5 h-3.5" />
          <span>ویرایش در بازرس</span>
        </span>
      </button>

      {/* Duplicate */}
      <button
        type="button"
        onClick={() => {
          duplicateElement(targetEl.id);
          toast({ title: "تکثیر شد", description: `المان «${targetEl.name}» تکثیر شد.` });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <Plus className="w-3.5 h-3.5" />
          <span>تکثیر</span>
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Ctrl+D</span>
      </button>

      {/* Copy */}
      <button
        type="button"
        onClick={() => {
          copyElement(targetEl.id);
          toast({ title: "کپی شد", description: "المان در کلیپ‌بورد کپی شد." });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <Copy className="w-3.5 h-3.5" />
          <span>کپی المان</span>
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Ctrl+C</span>
      </button>

      {/* Paste */}
      <button
        type="button"
        disabled={!hasClipboardElement}
        onClick={() => {
          pasteElement(isContainer ? targetEl.id : undefined);
          toast({ title: "درج شد", description: "المان از کلیپ‌بورد درج شد." });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary disabled:opacity-40 disabled:pointer-events-none transition text-right"
      >
        <span className="flex items-center gap-2">
          <Clipboard className="w-3.5 h-3.5" />
          <span>پیست المان</span>
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Ctrl+V</span>
      </button>

      <div className="h-px bg-border/60 my-1" />

      {/* Copy Styles */}
      <button
        type="button"
        onClick={() => {
          copyStyles(targetEl.id);
          toast({ title: "استایل‌ها کپی شد", description: "استایل‌ها در حافظه موقت قرار گرفتند." });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <Palette className="w-3.5 h-3.5" />
          <span>کپی استایل‌ها</span>
        </span>
      </button>

      {/* Paste Styles */}
      <button
        type="button"
        disabled={!hasClipboardStyles}
        onClick={() => {
          pasteStyles(targetEl.id);
          toast({ title: "استایل‌ها اعمال شد", description: "استایل‌ها بر روی المان اعمال شدند." });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary disabled:opacity-40 disabled:pointer-events-none transition text-right"
      >
        <span className="flex items-center gap-2">
          <Palette className="w-3.5 h-3.5 text-primary" />
          <span>پیست استایل‌ها</span>
        </span>
      </button>

      <div className="h-px bg-border/60 my-1" />

      {/* Reorder Up / Down */}
      <button
        type="button"
        onClick={() => {
          reorderElement(targetEl.id, "up");
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <ArrowUp className="w-3.5 h-3.5" />
          <span>انتقال به بالا</span>
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Alt+↑</span>
      </button>

      <button
        type="button"
        onClick={() => {
          reorderElement(targetEl.id, "down");
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-primary/10 hover:text-primary transition text-right"
      >
        <span className="flex items-center gap-2">
          <ArrowDown className="w-3.5 h-3.5" />
          <span>انتقال به پایین</span>
        </span>
        <span className="font-mono text-[10px] text-muted-foreground">Alt+↓</span>
      </button>

      {/* Save Template if container */}
      {isContainer && onOpenSaveTemplate && (
        <button
          type="button"
          onClick={() => {
            onOpenSaveTemplate(targetEl);
            onClose();
          }}
          className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-amber-500/15 hover:text-amber-600 transition text-right"
        >
          <span className="flex items-center gap-2 text-amber-600 dark:text-amber-400">
            <BookmarkPlus className="w-3.5 h-3.5" />
            <span>ذخیره به عنوان قالب</span>
          </span>
        </button>
      )}

      {/* Toggle Hide */}
      <button
        type="button"
        onClick={() => {
          toggleHideElement(targetEl.id);
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-muted transition text-right text-muted-foreground"
      >
        <span className="flex items-center gap-2">
          {targetEl.isHidden ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
          <span>{targetEl.isHidden ? "نمایش المان" : "مخفی‌سازی"}</span>
        </span>
      </button>

      <div className="h-px bg-border/60 my-1" />

      {/* Delete */}
      <button
        type="button"
        onClick={() => {
          deleteElement(targetEl.id);
          toast({ title: "حذف شد", description: "المان از صفحه حذف گردید." });
          onClose();
        }}
        className="w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg hover:bg-destructive/10 text-destructive transition text-right font-bold"
      >
        <span className="flex items-center gap-2">
          <Trash2 className="w-3.5 h-3.5" />
          <span>حذف</span>
        </span>
        <span className="font-mono text-[10px] opacity-70">Delete</span>
      </button>
    </div>
  );
}
