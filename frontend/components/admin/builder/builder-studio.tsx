"use client";

import React, { useEffect, useCallback, useRef, useState } from "react";
import { Layers, PlusSquare, AlertTriangle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Button } from "@/components/ui/button";
import { cmsPagesAdminApi, type CmsPage } from "@/lib/api/content";
import { blogAdminApi } from "@/lib/api/blog";
import { PageASTSchema } from "@/lib/builder/schema";
import { useBuilderStore } from "@/stores/builder-store";
import { usePageEditingLock } from "@/hooks/use-page-editing-lock";
import { BuilderToolbar } from "./builder-toolbar";
import { BlocksPalette } from "./blocks-palette";
import { LayersTree } from "./layers-tree";
import { CanvasFrame } from "./canvas-frame";
import { CanvasDndLayer } from "./canvas-dnd-layer";
import { InspectorPanel } from "./inspector-panel";

export interface BuilderStudioProps {
  page: CmsPage;
  onExit?: () => void;
}

export function BuilderStudio({ page, onExit }: BuilderStudioProps) {
  const { toast } = useToast();

  const ast = useBuilderStore((s) => s.ast);
  const initPage = useBuilderStore((s) => s.initPage);
  const activeBreakpoint = useBuilderStore((s) => s.activeBreakpoint);
  const activeLeftTab = useBuilderStore((s) => s.activeLeftTab);
  const setLeftTab = useBuilderStore((s) => s.setLeftTab);
  const previewMode = useBuilderStore((s) => s.previewMode);
  const moveElement = useBuilderStore((s) => s.moveElement);
  const addElement = useBuilderStore((s) => s.addElement);
  const setIsSaving = useBuilderStore((s) => s.setIsSaving);
  const markClean = useBuilderStore((s) => s.markClean);
  const isDirty = useBuilderStore((s) => s.isDirty);

  // Invalidate this page's cached storefront render so a reload right after a
  // save shows the new tree instead of a copy up to 300s old. Best-effort: a
  // failed revalidation only delays visibility until the ISR window lapses.
  const revalidatePage = useCallback(async () => {
    try {
      await fetch(`/api/cms-revalidate?slug=${encodeURIComponent(page.slug)}`, {
        method: "POST",
      });
    } catch {
      /* non-fatal */
    }
  }, [page.slug]);

  // ── Concurrent Editing Lock ───────────────────────────────────────────────
  const { lockedByOther, takeOver, release } = usePageEditingLock(page.id, "pages");

  // ── Autosave Management ───────────────────────────────────────────────────
  const [autosaveStatus, setAutosaveStatus] = useState<"idle" | "saving" | "saved" | "error">("idle");
  const [lastSavedAt, setLastSavedAt] = useState<string | null>(null);
  const isAutosavingRef = useRef(false);
  const inFlightMutationVersion = useRef(0);

  // Initialize store on mount
  useEffect(() => {
    initPage(page.id, page.builder_data, page.title, page.slug);
  }, [page.id, page.builder_data, page.title, page.slug, initPage]);

  // Clean up lock on unmount
  useEffect(() => {
    return () => {
      void release();
    };
  }, [release]);

  // 1.5s Debounced In-flight Safe Autosave
  useEffect(() => {
    if (!isDirty || !page.id) return;

    const timer = setTimeout(async () => {
      if (isAutosavingRef.current) return;
      isAutosavingRef.current = true;
      inFlightMutationVersion.current = useBuilderStore.getState().mutationVersion;
      setAutosaveStatus("saving");

      try {
        const validated = PageASTSchema.parse(useBuilderStore.getState().ast);

        // Update page draft in PostgreSQL
        // No status field: autosave edits content only. Sending "draft" here
        // unpublishes a live page — a save must never change publication.
        await cmsPagesAdminApi.updatePage(page.id, {
          builder_data: validated,
        });

        // Save Redis snapshot for rapid crash recovery
        void blogAdminApi.saveAutosave(page.id, validated, "pages").catch(() => undefined);
        void revalidatePage();

        setLastSavedAt(new Date().toLocaleTimeString("fa-IR"));

        // Only mark clean if no new edits arrived while in-flight
        if (useBuilderStore.getState().mutationVersion === inFlightMutationVersion.current) {
          markClean();
          setAutosaveStatus("saved");
        } else {
          setAutosaveStatus("idle");
        }
      } catch (err) {
        console.error("Autosave error:", err);
        setAutosaveStatus("error");
      } finally {
        isAutosavingRef.current = false;
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [isDirty, ast, page.id, markClean, revalidatePage]);

  // Manual Save Draft Action
  const handleSaveDraft = useCallback(async () => {
    setIsSaving(true);
    try {
      const validated = PageASTSchema.parse(ast);

      // Explicit draft save (the toolbar button is labelled "ذخیره پیش‌نویس").
      await cmsPagesAdminApi.updatePage(page.id, {
        builder_data: validated,
        status: "draft",
      });

      markClean();
      setAutosaveStatus("saved");
      setLastSavedAt(new Date().toLocaleTimeString("fa-IR"));
      void revalidatePage();
      toast({
        title: "پیش‌نویس ذخیره شد",
        description: "تغییرات صفحه با موفقیت در دیتابیس ثبت شد.",
      });
    } catch (err) {
      console.error("Save draft error:", err);
      toast({
        title: "خطا در ذخیره‌سازی",
        description: "اعتبارسنجی ساختار صفحه با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  }, [ast, page.id, markClean, setIsSaving, toast]);

  // Publish Page Action
  const handlePublish = useCallback(async () => {
    setIsSaving(true);
    try {
      const validated = PageASTSchema.parse(ast);

      await cmsPagesAdminApi.updatePage(page.id, {
        builder_data: validated,
        status: "published",
      });

      markClean();
      setAutosaveStatus("saved");
      setLastSavedAt(new Date().toLocaleTimeString("fa-IR"));
      void revalidatePage();
      toast({
        title: "صفحه منتشر شد",
        description: "این برگه اکنون با خروجی بهینه‌شده در دسترس کاربران است.",
      });
    } catch (err) {
      console.error("Publish error:", err);
      toast({
        title: "خطا در انتشار",
        description: "امکان انتشار صفحه به دلیل خطای اعتبارسنجی میسر نشد.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  }, [ast, page.id, markClean, setIsSaving, toast]);

  const handleExit = useCallback(() => {
    void release();
    if (onExit) {
      onExit();
    } else {
      window.location.href = `/${page.slug}`;
    }
  }, [onExit, page.slug, release]);

  const rootElementIds = ast.rootElements.map((el) => el.id);

  return (
    <div className="fixed inset-0 z-50 flex flex-col h-screen w-screen overflow-hidden bg-background font-sans" dir="rtl">
      {/* Concurrent Editing Lock Alert Banner */}
      {lockedByOther && (
        <div className="bg-amber-500/15 border-b border-amber-500/30 text-amber-900 dark:text-amber-200 px-4 py-2 text-xs flex items-center justify-between z-50 shrink-0">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>
              این برگه در حال حاضر توسط <strong>{lockedByOther}</strong> در حال ویرایش است. ذخیره‌سازی ممکن است تغییرات ایشان را بازنویسی کند.
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={takeOver}
            className="h-7 text-xs border-amber-600/40 hover:bg-amber-500/20 text-amber-900 dark:text-amber-200"
          >
            در اختیار گرفتن قفل ویرایش
          </Button>
        </div>
      )}

      {/* Top Navigation Toolbar */}
      <BuilderToolbar
        onSaveDraft={handleSaveDraft}
        onPublish={handlePublish}
        onExit={handleExit}
        pageStatus={page.status}
        autosaveStatus={autosaveStatus}
        lastSavedAt={lastSavedAt}
      />

      {/* Main 3-Column Studio Workspace */}
      <div className="flex-1 flex overflow-hidden relative">
        {/* Left Column: Blocks Palette & Layers Tree */}
        {!previewMode && (
          <aside className="w-80 bg-card border-e border-border flex flex-col shrink-0 z-20 shadow-sm">
            {/* Sidebar Tab Switcher */}
            <div className="grid grid-cols-2 p-1.5 m-2.5 rounded-xl bg-muted/60 border border-border/60">
              <button
                type="button"
                onClick={() => setLeftTab("blocks")}
                className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeLeftTab === "blocks"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <PlusSquare className="w-3.5 h-3.5" />
                <span>افزودن بلوک</span>
              </button>
              <button
                type="button"
                onClick={() => setLeftTab("layers")}
                className={`flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-semibold transition ${
                  activeLeftTab === "layers"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                <Layers className="w-3.5 h-3.5" />
                <span>لایه‌ها</span>
              </button>
            </div>

            {/* Sidebar Tab Content */}
            <div className="flex-1 overflow-hidden">
              {activeLeftTab === "blocks" ? <BlocksPalette /> : <LayersTree />}
            </div>
          </aside>
        )}

        {/* Center: Canvas Viewport Workspace */}
        <main
          className="flex-1 overflow-y-auto relative flex flex-col items-center bg-muted/30"
          onDragOver={(e) => {
            e.preventDefault();
            if (e.dataTransfer) {
              e.dataTransfer.dropEffect = "copy";
            }
          }}
        >
          {/* DnD lives INSIDE the iframe (CanvasDndLayer). A DndContext in this
              document never receives pointer moves fired inside the canvas
              document, so drags silently failed to start. */}
          <CanvasFrame viewport={activeBreakpoint}>
            <CanvasDndLayer
              elements={ast.rootElements}
              activeBreakpoint={activeBreakpoint}
            />
          </CanvasFrame>
        </main>

        {/* Right Column: Element Inspector & Controls */}
        {!previewMode && (
          <aside className="w-80 bg-card border-s border-border shrink-0 z-20 shadow-sm">
            <InspectorPanel />
          </aside>
        )}
      </div>
    </div>
  );
}
