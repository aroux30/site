"use client";

import React, { useEffect } from "react";
import {
  ArrowRight,
  Smartphone,
  Tablet,
  Monitor,
  Undo2,
  Redo2,
  Eye,
  EyeOff,
  Save,
  Send,
  Loader2,
  Layers,
  Sparkles,
  Check,
  AlertCircle,
  Paintbrush,
  Bookmark,
  Keyboard,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { useBuilderStore, type Breakpoint } from "@/stores/builder-store";
import { GlobalStylesDialog } from "./global-styles-dialog";
import { SavePageTemplateDialog } from "./save-page-template-dialog";
import { KeyboardShortcutsDialog } from "./keyboard-shortcuts-dialog";

interface BuilderToolbarProps {
  onSaveDraft: () => Promise<void>;
  onPublish: () => Promise<void>;
  onExit: () => void;
  pageStatus?: string;
  autosaveStatus?: "idle" | "saving" | "saved" | "error";
  lastSavedAt?: string | null;
}

export function BuilderToolbar({
  onSaveDraft,
  onPublish,
  onExit,
  pageStatus = "draft",
  autosaveStatus = "idle",
  lastSavedAt,
}: BuilderToolbarProps) {
  const ast = useBuilderStore((s) => s.ast);
  const activeBreakpoint = useBuilderStore((s) => s.activeBreakpoint);
  const setBreakpoint = useBuilderStore((s) => s.setBreakpoint);
  const previewMode = useBuilderStore((s) => s.previewMode);
  const setPreviewMode = useBuilderStore((s) => s.setPreviewMode);
  const isDirty = useBuilderStore((s) => s.isDirty);
  const isSaving = useBuilderStore((s) => s.isSaving);
  const history = useBuilderStore((s) => s.history);
  const undo = useBuilderStore((s) => s.undo);
  const redo = useBuilderStore((s) => s.redo);
  const copyElement = useBuilderStore((s) => s.copyElement);
  const pasteElement = useBuilderStore((s) => s.pasteElement);
  const duplicateElement = useBuilderStore((s) => s.duplicateElement);
  const deleteElement = useBuilderStore((s) => s.deleteElement);
  const deleteSelectedElements = useBuilderStore((s) => s.deleteSelectedElements);
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const selectedElementIds = useBuilderStore((s) => s.selectedElementIds);
  const [globalStylesOpen, setGlobalStylesOpen] = React.useState(false);
  const [savePageTemplateOpen, setSavePageTemplateOpen] = React.useState(false);
  const [shortcutsOpen, setShortcutsOpen] = React.useState(false);

  const canUndo = history.past.length > 0;
  const canRedo = history.future.length > 0;

  // Keyboard shortcut listener for Undo/Redo/Copy/Paste/Delete/Duplicate/Save/Help
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      const isInput = targetTag === "input" || targetTag === "textarea" || (e.target as HTMLElement)?.isContentEditable;
      if (isInput) return;

      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") {
        if (e.shiftKey) {
          e.preventDefault();
          redo();
        } else {
          e.preventDefault();
          undo();
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") {
        e.preventDefault();
        redo();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "d") {
        e.preventDefault();
        if (selectedElementId) {
          duplicateElement(selectedElementId);
        }
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void onSaveDraft();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "c") {
        e.preventDefault();
        copyElement();
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "v") {
        e.preventDefault();
        pasteElement();
      } else if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setShortcutsOpen((prev) => !prev);
      } else if (e.altKey && (e.key === "ArrowUp" || e.key === "ArrowDown")) {
        e.preventDefault();
        if (selectedElementId) {
          useBuilderStore.getState().reorderElement(selectedElementId, e.key === "ArrowUp" ? "up" : "down");
        }
      } else if (e.key === "Escape") {
        useBuilderStore.getState().selectElement(null as any);
      } else if (e.key === "Delete") {
        e.preventDefault();
        if (selectedElementIds.length > 0) {
          deleteSelectedElements();
        } else if (selectedElementId) {
          deleteElement(selectedElementId);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [undo, redo, copyElement, pasteElement, duplicateElement, deleteElement, deleteSelectedElements, selectedElementId, selectedElementIds, onSaveDraft]);

  return (
    <header className="h-14 bg-card border-b border-border px-4 flex items-center justify-between select-none z-40 relative">
      {/* Right Side (in RTL): Exit button & Page Title */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          onClick={onExit}
          className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
        >
          <ArrowRight className="w-4 h-4" />
          <span>خروج</span>
        </Button>

        <div className="h-4 w-px bg-border/80" />

        <div className="flex items-center gap-2">
          <span className="text-xs font-bold text-foreground max-w-[200px] truncate">
            {ast.title || "برگه بدون عنوان"}
          </span>
          <Badge
            variant={pageStatus === "published" ? "default" : "secondary"}
            className="text-[10px] px-1.5 py-0 h-4"
          >
            {pageStatus === "published" ? "منتشرشده" : "پیش‌نویس"}
          </Badge>

          {/* Autosave Status Indicator */}
          {autosaveStatus === "saving" && (
            <span className="flex items-center gap-1 text-[11px] text-muted-foreground animate-pulse">
              <Loader2 className="w-3 h-3 animate-spin text-primary" />
              <span>ذخیره خودکار...</span>
            </span>
          )}
          {autosaveStatus === "saved" && !isDirty && (
            <span className="flex items-center gap-1 text-[11px] text-emerald-600 dark:text-emerald-400">
              <Check className="w-3 h-3" />
              <span>ذخیره شد</span>
            </span>
          )}
          {autosaveStatus === "error" && (
            <span className="flex items-center gap-1 text-[11px] text-destructive">
              <AlertCircle className="w-3 h-3" />
              <span>خطای ذخیره خودکار</span>
            </span>
          )}
          {isDirty && autosaveStatus !== "saving" && (
            <span className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" title="تغییرات ذخیره‌نشده" />
          )}
        </div>
      </div>

      {/* Center: Responsive Breakpoint Switcher */}
      <div className="flex items-center bg-muted/60 p-1 rounded-xl border border-border/80 gap-1">
        <button
          type="button"
          onClick={() => setBreakpoint("desktop")}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
            activeBreakpoint === "desktop"
              ? "bg-background text-foreground shadow-sm font-bold"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Monitor className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">دسکتاپ</span>
        </button>

        <button
          type="button"
          onClick={() => setBreakpoint("tablet")}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
            activeBreakpoint === "tablet"
              ? "bg-background text-foreground shadow-sm font-bold"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Tablet className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">تبلت (۷۶۸)</span>
        </button>

        <button
          type="button"
          onClick={() => setBreakpoint("mobile")}
          className={`flex items-center gap-1.5 px-3 py-1 rounded-lg text-xs font-medium transition ${
            activeBreakpoint === "mobile"
              ? "bg-background text-foreground shadow-sm font-bold"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Smartphone className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">موبایل (۳۷۵)</span>
        </button>
      </div>

      {/* Left Side (in RTL): Undo/Redo, Preview, Save, Publish */}
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-0.5 bg-muted/40 p-0.5 rounded-lg border border-border/60">
          <Button
            variant="ghost"
            size="sm"
            onClick={undo}
            disabled={!canUndo}
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground disabled:opacity-30"
            title="بازگشت (Ctrl+Z)"
          >
            <Undo2 className="w-3.5 h-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={redo}
            disabled={!canRedo}
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground disabled:opacity-30"
            title="انجام مجدد (Ctrl+Y)"
          >
            <Redo2 className="w-3.5 h-3.5" />
          </Button>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSavePageTemplateOpen(true)}
          className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          title="ذخیره کل برگه به عنوان قالب"
        >
          <Bookmark className="w-3.5 h-3.5 text-primary" />
          <span className="hidden sm:inline">قالب برگه</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setGlobalStylesOpen(true)}
          className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          title="استایل‌های سراسری برگه"
        >
          <Paintbrush className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">استایل سراسری</span>
        </Button>

        <Button
          variant={previewMode ? "secondary" : "ghost"}
          size="sm"
          onClick={() => setPreviewMode(!previewMode)}
          className="h-8 gap-1.5 text-xs"
        >
          {previewMode ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          <span className="hidden sm:inline">{previewMode ? "ویرایش" : "پیش‌نمایش"}</span>
        </Button>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setShortcutsOpen(true)}
          className="h-8 gap-1.5 text-xs text-muted-foreground hover:text-foreground"
          title="کلیدهای میانبر (؟)"
          data-testid="shortcuts-help-btn"
        >
          <Keyboard className="w-3.5 h-3.5" />
          <span className="hidden sm:inline">میانبرها</span>
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={onSaveDraft}
          disabled={isSaving}
          className="h-8 gap-1.5 text-xs"
        >
          {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
          <span>ذخیره پیش‌نویس</span>
        </Button>

        <Button
          size="sm"
          onClick={onPublish}
          disabled={isSaving}
          className="h-8 gap-1.5 text-xs bg-emerald-600 hover:bg-emerald-700 text-white"
        >
          {isSaving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Send className="w-3.5 h-3.5" />}
          <span>انتشار برگه</span>
        </Button>
      </div>

      <GlobalStylesDialog open={globalStylesOpen} onOpenChange={setGlobalStylesOpen} />
      <SavePageTemplateDialog open={savePageTemplateOpen} onOpenChange={setSavePageTemplateOpen} />
      <KeyboardShortcutsDialog open={shortcutsOpen} onOpenChange={setShortcutsOpen} />
    </header>
  );
}
