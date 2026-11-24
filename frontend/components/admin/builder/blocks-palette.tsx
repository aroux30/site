"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { Search, Sparkles, Layout, Box, Loader2, Bookmark, FolderHeart, Eye, Pencil, Trash2, Copy, Plus } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import {
  BASIC_BLOCK_DEFINITIONS,
  createPatternElement,
  type BlockDefinition,
} from "@/lib/builder/block-registry";
import {
  blockPatternsApi,
  type BlockPattern,
  type BlockPatternCategoryGroup,
} from "@/lib/api/block-patterns";
import { pageTemplatesAdminApi } from "@/lib/api/content";
import type { PageTemplate } from "@/types/builder";
import { useBuilderStore, cloneElementWithNewIds, findElementById } from "@/stores/builder-store";
import { useToast } from "@/components/ui/use-toast";

type PaletteTab = "basic" | "patterns" | "templates";

export function BlocksPalette() {
  const { toast } = useToast();
  const [activeTab, setActiveTab] = useState<PaletteTab>("basic");
  const [search, setSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [patternGroups, setPatternGroups] = useState<BlockPatternCategoryGroup[]>([]);
  const [loadingPatterns, setLoadingPatterns] = useState(false);
  const [renderingSlug, setRenderingSlug] = useState<string | null>(null);

  const [savedTemplates, setSavedTemplates] = useState<PageTemplate[]>([]);
  const [loadingTemplates, setLoadingTemplates] = useState(false);
  const [previewTemplate, setPreviewTemplate] = useState<PageTemplate | null>(null);
  const [editTemplate, setEditTemplate] = useState<PageTemplate | null>(null);
  const [editTplTitle, setEditTplTitle] = useState("");
  const [editTplCat, setEditTplCat] = useState("عمومی");
  const [savingEdit, setSavingEdit] = useState(false);

  const addElement = useBuilderStore((s) => s.addElement);
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const ast = useBuilderStore((s) => s.ast);

  // Load all templates (page & section) when templates tab is selected
  const [tplTypeFilter, setTplTypeFilter] = useState<"all" | "page" | "section">("all");

  const fetchTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const data = await pageTemplatesAdminApi.list();
      setSavedTemplates(data);
    } catch (err) {
      console.error("Failed to load templates:", err);
    } finally {
      setLoadingTemplates(false);
    }
  }, []);

  useEffect(() => {
    if (activeTab === "templates") {
      fetchTemplates();
    }
  }, [activeTab, fetchTemplates]);

  // Load 28 block patterns from backend API
  useEffect(() => {
    let cancelled = false;
    setLoadingPatterns(true);
    blockPatternsApi
      .list()
      .then((groups) => {
        if (!cancelled) setPatternGroups(groups);
      })
      .catch((err) => {
        console.error("Failed to load block patterns:", err);
      })
      .finally(() => {
        if (!cancelled) setLoadingPatterns(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Filter basic blocks
  const filteredBasicBlocks = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return BASIC_BLOCK_DEFINITIONS;
    const tokens = q.split(/\s+/).filter(Boolean);
    return BASIC_BLOCK_DEFINITIONS.filter((b) => {
      const searchTarget = `${b.name} ${b.description} ${b.type}`.toLowerCase();
      return tokens.every((tok) => searchTarget.includes(tok));
    });
  }, [search]);

  const layoutBlocks = filteredBasicBlocks.filter((b) => b.category === "layout");
  const basicBlocks = filteredBasicBlocks.filter((b) => b.category === "basic");

  // Flatten all patterns from groups
  const allPatterns = useMemo(() => {
    const list: BlockPattern[] = [];
    for (const g of patternGroups) {
      list.push(...g.patterns);
    }
    return list;
  }, [patternGroups]);

  // Unique categories list
  const categories = useMemo(() => {
    return patternGroups.map((g) => g.category);
  }, [patternGroups]);

  // Filter patterns by search & category
  const filteredPatterns = useMemo(() => {
    const q = search.trim().toLowerCase();
    return allPatterns.filter((p) => {
      const matchCat =
        selectedCategory === "all" || p.category === selectedCategory;
      if (!matchCat) return false;
      if (!q) return true;
      const haystack = [p.title, p.description, p.category, ...p.keywords]
        .join(" ")
        .toLowerCase();
      return haystack.includes(q);
    });
  }, [allPatterns, search, selectedCategory]);

  const getTargetContainerId = useCallback(() => {
    if (!selectedElementId) return undefined;
    const selectedEl = findElementById(ast.rootElements, selectedElementId);
    return selectedEl?.type === "container" ? selectedEl.id : undefined;
  }, [ast.rootElements, selectedElementId]);

  const handleAddBasicBlock = (def: BlockDefinition) => {
    const newEl = def.createDefaultElement();
    addElement(newEl, getTargetContainerId());
  };

  const handleInsertPattern = async (pattern: BlockPattern) => {
    setRenderingSlug(pattern.slug);
    try {
      const vars = Object.fromEntries(
        pattern.variables.map((v) => [v.name, v.default])
      );
      let html = "";
      try {
        const res = await blockPatternsApi.render(pattern.slug, {});
        html = res.html;
      } catch {
        html = `<section class="pattern-${pattern.slug}"><h2>${pattern.title}</h2></section>`;
      }
      const newEl = createPatternElement(pattern, html, vars);
      // Patterns are top-level sections: always insert at root level
      addElement(newEl);
      toast({
        title: "الگو افزوده شد",
        description: `الگوی «${pattern.title}» به برگه اضافه شد.`,
        duration: 2000,
      });
    } catch (err) {
      console.error("Failed to render pattern:", err);
      toast({
        title: "خطا در افزودن الگو",
        description: "رندر الگوی انتخابی با خطا مواجه شد.",
        variant: "destructive",
        duration: 3000,
      });
    } finally {
      setRenderingSlug(null);
    }
  };

  const handleInsertTemplate = (tpl: PageTemplate) => {
    const bData = (tpl as any).builder_data || tpl.builderData;
    const rootEls = bData?.rootElements || (bData as any)?.root_elements || [];
    if (rootEls.length === 0) return;
    const cloned = rootEls.map((el: any) => cloneElementWithNewIds(el, false));
    useBuilderStore.getState().addElements(cloned, getTargetContainerId());
    toast({
      title: "قالب افزوده شد",
      description: `قالب «${tpl.title}» به بوم اضافه شد.`,
      duration: 2000,
    });
  };

  const handleApplyPageTemplate = (tpl: PageTemplate) => {
    const bData = (tpl as any).builder_data || tpl.builderData;
    const rootEls = bData?.rootElements || (bData as any)?.root_elements || [];
    if (rootEls.length === 0) return;
    const clonedRoots = rootEls.map((el: any) => cloneElementWithNewIds(el, false));
    const currentAst = useBuilderStore.getState().ast;
    useBuilderStore.getState().replacePageAST({
      ...currentAst,
      globalStyles: bData?.globalStyles || currentAst.globalStyles,
      rootElements: clonedRoots,
    });
    toast({
      title: "قالب برگه اعمال شد",
      description: `محتوا و استایل‌های برگه با قالب «${tpl.title}» جایگزین شدند.`,
    });
  };

  const handleDuplicateTemplate = async (tpl: PageTemplate, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const bData = (tpl as any).builder_data || tpl.builderData;
      const slug = `tpl-${Math.random().toString(36).slice(2, 10)}`;
      await pageTemplatesAdminApi.create({
        title: `${tpl.title} (کپی)`,
        slug,
        template_type: tpl.templateType || (tpl as any).template_type || "section",
        category: tpl.category || "عمومی",
        builder_data: bData,
      });
      toast({
        title: "قالب کپی شد",
        description: `نسخه کپی از «${tpl.title}» ایجاد گردید.`,
      });
      fetchTemplates();
    } catch (err) {
      console.error("Duplicate template error:", err);
      toast({ title: "خطا در کلون قالب", variant: "destructive" });
    }
  };

  const handleDeleteTemplate = async (id: string, title: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await pageTemplatesAdminApi.delete(id);
      toast({
        title: "قالب حذف شد",
        description: `قالب «${title}» حذف گردید.`,
      });
      fetchTemplates();
    } catch (err) {
      console.error("Delete template error:", err);
      toast({
        title: "خطا",
        description: "حذف قالب با خطا مواجه شد.",
        variant: "destructive",
      });
    }
  };

  const handleOpenEditTemplate = (tpl: PageTemplate, e: React.MouseEvent) => {
    e.stopPropagation();
    setEditTemplate(tpl);
    setEditTplTitle(tpl.title);
    setEditTplCat(tpl.category || "عمومی");
  };

  const handleSaveEditTemplate = async () => {
    if (!editTemplate || !editTplTitle.trim()) return;
    setSavingEdit(true);
    try {
      await pageTemplatesAdminApi.update(editTemplate.id, {
        title: editTplTitle.trim(),
        category: editTplCat,
      });
      toast({
        title: "قالب ویرایش شد",
        description: "مشخصات قالب با موفقیت به‌روزرسانی شد.",
      });
      setEditTemplate(null);
      fetchTemplates();
    } catch (err) {
      console.error("Update template error:", err);
      toast({
        title: "خطا",
        description: "ویرایش قالب با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setSavingEdit(false);
    }
  };

  const filteredSavedTemplates = useMemo(() => {
    const q = search.trim().toLowerCase();
    return savedTemplates.filter((t) => {
      if (tplTypeFilter !== "all") {
        const type = (t as any).template_type || t.templateType || "section";
        if (type !== tplTypeFilter) return false;
      }
      if (!q) return true;
      return t.title.toLowerCase().includes(q) || (t.category || "").toLowerCase().includes(q);
    });
  }, [savedTemplates, search, tplTypeFilter]);

  return (
    <div className="flex flex-col h-full min-h-0 space-y-3 p-3 select-none">
      {/* Sub-tab toggle: Basic Blocks vs Ready Patterns vs Saved Templates */}
      <div className="grid grid-cols-3 p-1 rounded-xl bg-muted/60 border border-border/70 text-xs shrink-0 gap-1">
        <button
          type="button"
          data-testid="blocks-palette-basic-tab-btn"
          onClick={() => setActiveTab("basic")}
          className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-[11px] font-semibold transition ${
            activeTab === "basic"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Box className="w-3 h-3 shrink-0" />
          <span className="truncate">بلوک‌ها ({filteredBasicBlocks.length})</span>
        </button>

        <button
          type="button"
          data-testid="patterns-tab-btn"
          onClick={() => setActiveTab("patterns")}
          className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-[11px] font-semibold transition ${
            activeTab === "patterns"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Sparkles className="w-3 h-3 text-amber-500 shrink-0" />
          <span className="truncate">الگوها ({allPatterns.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("templates")}
          className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-[11px] font-semibold transition ${
            activeTab === "templates"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <FolderHeart className="w-3 h-3 text-primary shrink-0" />
          <span className="truncate">قالب‌های من ({savedTemplates.length})</span>
        </button>
      </div>

      {/* Search Input */}
      <div className="relative shrink-0">
        <Search className="absolute start-2.5 top-2.5 h-3.5 w-3.5 text-muted-foreground" />
        <Input
          placeholder={
            activeTab === "basic"
              ? "جستجوی بلوک پایه..."
              : activeTab === "patterns"
              ? "جستجو در ۲۸ الگوی آماده..."
              : "جستجو در قالب‌های من..."
          }
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ps-8 h-8 text-xs"
        />
      </div>

      {/* Category chips when in Patterns tab */}
      {activeTab === "patterns" && categories.length > 0 && (
        <div className="flex flex-wrap gap-1.5 pb-1 shrink-0" data-category-chips="">
          <button
            type="button"
            onClick={() => setSelectedCategory("all")}
            className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 whitespace-nowrap transition ${
              selectedCategory === "all"
                ? "bg-primary text-primary-foreground font-bold shadow-xs"
                : "bg-muted/70 text-muted-foreground hover:text-foreground"
            }`}
          >
            همه ({allPatterns.length})
          </button>
          {categories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setSelectedCategory(cat)}
              className={`px-2.5 py-1 rounded-lg text-[11px] font-medium shrink-0 whitespace-nowrap transition ${
                selectedCategory === cat
                  ? "bg-primary text-primary-foreground font-bold shadow-xs"
                  : "bg-muted/70 text-muted-foreground hover:text-foreground"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Main Tab Content */}
      <div className="flex-1 min-h-0 overflow-y-auto space-y-4 pe-1 builder-scrollbar">
        {activeTab === "basic" ? (
          <>
            {/* Layout Blocks */}
            {layoutBlocks.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider px-1">
                  طرح‌بندی و ساختار
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  {layoutBlocks.map((block) => {
                    const Icon = block.icon;
                    return (
                      <button
                        key={block.type}
                        type="button"
                        data-block-type={block.type}
                        draggable={true}
                        onDragStart={(e) => {
                          e.dataTransfer.setData(
                            "application/json",
                            JSON.stringify({ type: "block_def", blockType: block.type })
                          );
                          e.dataTransfer.effectAllowed = "all";
                        }}
                        onClick={() => handleAddBasicBlock(block)}
                        className="flex flex-col items-start justify-between p-2.5 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-start transition shadow-xs group cursor-grab active:cursor-grabbing relative"
                        title="کلیک برای درج فوری، یا کشیدن با ماوس به داخل بوم"
                      >
                        <div className="flex items-center justify-between w-full mb-1">
                          <div className="p-1.5 rounded-lg bg-muted/80 text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                            <Icon className="w-4 h-4" />
                          </div>
                          <span
                            className="p-1 rounded-md bg-muted/80 text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground transition-all shadow-xs"
                            title="درج فوری در بوم"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </span>
                        </div>
                        <span className="text-xs font-bold text-foreground line-clamp-1 w-full mt-1">
                          {(block.name.split("(")[0] ?? block.name).trim()}
                        </span>
                        <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1 w-full">
                          {block.description}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {/* Basic Content Blocks */}
            {basicBlocks.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-[11px] font-bold text-muted-foreground uppercase tracking-wider px-1">
                  عناصر محتوایی
                </h4>
                <div className="grid grid-cols-2 gap-2">
                  {basicBlocks.map((block) => {
                    const Icon = block.icon;
                    return (
                      <button
                        key={block.type}
                        type="button"
                        data-block-type={block.type}
                        draggable={true}
                        onDragStart={(e) => {
                          e.dataTransfer.setData(
                            "application/json",
                            JSON.stringify({ type: "block_def", blockType: block.type })
                          );
                          e.dataTransfer.effectAllowed = "all";
                        }}
                        onClick={() => handleAddBasicBlock(block)}
                        className="flex flex-col items-start justify-between p-2.5 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-start transition shadow-xs group cursor-grab active:cursor-grabbing relative"
                        title="کلیک برای درج فوری، یا کشیدن با ماوس به داخل بوم"
                      >
                        <div className="flex items-center justify-between w-full mb-1">
                          <div className="p-1.5 rounded-lg bg-muted/80 text-muted-foreground group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                            <Icon className="w-4 h-4" />
                          </div>
                          <span
                            className="p-1 rounded-md bg-muted/80 text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground transition-all shadow-xs"
                            title="درج فوری در بوم"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </span>
                        </div>
                        <span className="text-xs font-bold text-foreground line-clamp-1 w-full mt-1">
                          {(block.name.split("(")[0] ?? block.name).trim()}
                        </span>
                        <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1 w-full">
                          {block.description}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </>
        ) : activeTab === "patterns" ? (
          /* Ready Patterns Tab */
          <div className="space-y-2">
            {loadingPatterns ? (
              <div className="flex items-center justify-center py-12 text-xs text-muted-foreground gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span>در حال بارگذاری ۲۸ الگوی آماده...</span>
              </div>
            ) : filteredPatterns.length === 0 ? (
              <div className="text-center py-8 text-xs text-muted-foreground">
                الگویی با این مشخصات یافت نشد.
              </div>
            ) : (
              <div className="space-y-2">
                {filteredPatterns.map((pattern) => {
                  const isRendering = renderingSlug === pattern.slug;
                  return (
                    <div
                      key={pattern.slug}
                      data-pattern-slug={pattern.slug}
                      data-testid={`pattern-card-${pattern.slug}`}
                      draggable={true}
                      onDragStart={(e) => {
                        const vars = Object.fromEntries(
                          pattern.variables.map((v) => [v.name, v.default])
                        );
                        e.dataTransfer.setData(
                          "application/json",
                          JSON.stringify({
                            type: "pattern_def",
                            patternSlug: pattern.slug,
                            title: pattern.title,
                            category: pattern.category,
                            variables: vars,
                          })
                        );
                        e.dataTransfer.effectAllowed = "all";
                      }}
                      onClick={() => handleInsertPattern(pattern)}
                      className="p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/40 hover:border-primary/50 transition cursor-grab active:cursor-grabbing shadow-sm space-y-1.5 group"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-bold text-foreground group-hover:text-primary transition-colors">
                          {pattern.title}
                        </span>
                        <div className="flex items-center gap-1.5">
                          <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                            {pattern.category}
                          </Badge>
                          <span
                            className="p-1 rounded-md bg-muted/80 text-muted-foreground group-hover:bg-primary group-hover:text-primary-foreground transition-all shadow-xs"
                            title="درج فوری الگو در بوم"
                          >
                            <Plus className="w-3.5 h-3.5" />
                          </span>
                        </div>
                      </div>
                      <p className="text-[11px] text-muted-foreground line-clamp-2 leading-relaxed">
                        {pattern.description}
                      </p>
                      <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[10px] text-muted-foreground">
                        <span>{pattern.variables.length} متغیر قابل تنظیم</span>
                        <span className="text-primary font-semibold flex items-center gap-1">
                          {isRendering ? (
                            <>
                              <Loader2 className="w-3 h-3 animate-spin" />
                              <span>در حال درج...</span>
                            </>
                          ) : (
                            <span>کلیک یا درگ ↵</span>
                          )}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        ) : (
          /* Saved Templates Tab */
          <div className="space-y-2">
            {/* Template Type Filter: All vs Page vs Section */}
            <div className="flex gap-1 pb-1 shrink-0 no-scrollbar">
              <button
                type="button"
                onClick={() => setTplTypeFilter("all")}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                  tplTypeFilter === "all"
                    ? "bg-primary text-primary-foreground font-bold"
                    : "bg-muted/70 text-muted-foreground hover:text-foreground"
                }`}
              >
                همه ({savedTemplates.length})
              </button>
              <button
                type="button"
                onClick={() => setTplTypeFilter("page")}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                  tplTypeFilter === "page"
                    ? "bg-purple-600 text-white font-bold"
                    : "bg-muted/70 text-muted-foreground hover:text-foreground"
                }`}
              >
                قالب برگه ({savedTemplates.filter((t: any) => (t.template_type || t.templateType) === "page").length})
              </button>
              <button
                type="button"
                onClick={() => setTplTypeFilter("section")}
                className={`px-2 py-0.5 rounded-md text-[11px] font-medium transition ${
                  tplTypeFilter === "section"
                    ? "bg-blue-600 text-white font-bold"
                    : "bg-muted/70 text-muted-foreground hover:text-foreground"
                }`}
              >
                قالب بخش ({savedTemplates.filter((t: any) => ((t.template_type || t.templateType) || "section") === "section").length})
              </button>
            </div>

            {loadingTemplates ? (
              <div className="flex items-center justify-center py-12 text-xs text-muted-foreground gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span>در حال بارگذاری قالب‌های من...</span>
              </div>
            ) : filteredSavedTemplates.length === 0 ? (
              <div className="text-center py-10 px-3 border border-dashed rounded-xl border-border/80 text-muted-foreground space-y-2">
                <Bookmark className="w-8 h-8 opacity-30 mx-auto" />
                <p className="text-xs font-semibold text-foreground">قالبی یافت نشد</p>
                <p className="text-[11px] leading-relaxed">
                  می‌توانید کل برگه را با دکمه «قالب برگه» در نوار بالا یا هر سکشن را با «ذخیره به عنوان قالب» ذخیره کنید.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredSavedTemplates.map((tpl) => {
                  const isPage = ((tpl as any).template_type || tpl.templateType) === "page";
                  const bData = (tpl as any).builder_data || tpl.builderData;
                  const rootEls = bData?.rootElements || (bData as any)?.root_elements || [];

                  return (
                    <div
                      key={tpl.id}
                      draggable={!isPage}
                      onDragStart={(e) => {
                        if (isPage) return;
                        e.dataTransfer.setData(
                          "application/json",
                          JSON.stringify({
                            type: "template_def",
                            templateId: tpl.id,
                            title: tpl.title,
                            elements: rootEls,
                          })
                        );
                        e.dataTransfer.effectAllowed = "all";
                      }}
                      onClick={() => (isPage ? handleApplyPageTemplate(tpl) : handleInsertTemplate(tpl))}
                      className={`p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/40 transition shadow-sm space-y-2 group ${
                        isPage ? "cursor-pointer hover:border-purple-500/60" : "cursor-grab active:cursor-grabbing hover:border-primary/50"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-bold text-foreground group-hover:text-primary transition-colors truncate flex-1" title={tpl.title}>
                          {tpl.title}
                        </span>
                        {isPage ? (
                          <Badge className="text-[9px] px-1.5 py-0 h-4 shrink-0 bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20">
                            قالب برگه
                          </Badge>
                        ) : (
                          <Badge className="text-[9px] px-1.5 py-0 h-4 shrink-0 bg-blue-500/10 text-blue-600 dark:text-blue-400 border border-blue-500/20">
                            قالب بخش
                          </Badge>
                        )}
                      </div>

                      <div className="flex items-center justify-between pt-1.5 border-t border-border/40 text-[10px] text-muted-foreground">
                        <div className="flex items-center gap-1.5">
                          <span>{tpl.category || "عمومی"}</span>
                          <span>•</span>
                          <span>{rootEls.length || 1} بخش</span>
                        </div>
                        <div className="flex items-center gap-2">
                          {isPage ? (
                            <span className="text-purple-600 dark:text-purple-400 font-semibold">اعمال روی برگه ↵</span>
                          ) : (
                            <span className="text-primary font-semibold">کلیک یا درگ ↵</span>
                          )}
                          <div className="flex items-center gap-0.5 bg-muted/60 rounded p-0.5 border border-border/50" onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                setPreviewTemplate(tpl);
                              }}
                              className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                              title="پیش‌نمایش ساختار قالب"
                            >
                              <Eye className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => handleDuplicateTemplate(tpl, e)}
                              className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                              title="تکثیر / کپی قالب"
                            >
                              <Copy className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => handleOpenEditTemplate(tpl, e)}
                              className="p-1 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                              title="ویرایش عنوان و دسته‌بندی"
                            >
                              <Pencil className="w-3 h-3" />
                            </button>
                            <button
                              type="button"
                              onClick={(e) => handleDeleteTemplate(tpl.id, tpl.title, e)}
                              className="p-1 hover:bg-destructive/10 rounded text-destructive"
                              title="حذف قالب"
                            >
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Preview Template Structure Dialog */}
      <Dialog open={Boolean(previewTemplate)} onOpenChange={(open) => !open && setPreviewTemplate(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Eye className="w-4 h-4 text-primary" />
              <span>پیش‌نمایش ساختار قالب «{previewTemplate?.title}»</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <div className="flex items-center justify-between p-2.5 rounded-lg bg-muted/40 border">
              <span className="text-muted-foreground">دسته‌بندی:</span>
              <Badge variant="outline">{previewTemplate?.category || "عمومی"}</Badge>
            </div>
            <div className="p-3 rounded-lg border bg-card space-y-2">
              <span className="font-semibold block text-foreground">المان‌های موجود در قالب:</span>
              <ul className="space-y-1 text-muted-foreground list-disc ps-4">
                {((previewTemplate as any)?.builder_data?.rootElements || previewTemplate?.builderData?.rootElements || []).map((el: any) => (
                  <li key={el.id} className="font-mono text-[11px]">
                    {el.name} ({el.type === "container" ? "کانتینر چیدمان" : el.widgetType || "ویجت"})
                  </li>
                ))}
              </ul>
            </div>
          </div>

          <DialogFooter className="flex items-center justify-between gap-2">
            <Button variant="outline" size="sm" onClick={() => setPreviewTemplate(null)}>
              بستن
            </Button>
            {previewTemplate && (
              <Button
                size="sm"
                className={((previewTemplate as any)?.template_type || previewTemplate?.templateType) === "page" ? "bg-purple-600 hover:bg-purple-700 text-white" : ""}
                onClick={() => {
                  const isPage = ((previewTemplate as any)?.template_type || previewTemplate?.templateType) === "page";
                  if (isPage) {
                    handleApplyPageTemplate(previewTemplate);
                  } else {
                    handleInsertTemplate(previewTemplate);
                  }
                  setPreviewTemplate(null);
                }}
              >
                {((previewTemplate as any)?.template_type || previewTemplate?.templateType) === "page"
                  ? "اعمال این قالب روی برگه"
                  : "درج این قالب در بوم"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Template Title/Category Dialog */}
      <Dialog open={Boolean(editTemplate)} onOpenChange={(open) => !open && setEditTemplate(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Pencil className="w-4 h-4 text-primary" />
              <span>ویرایش مشخصات قالب</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs">
            <div className="space-y-1.5">
              <Label className="text-xs">عنوان قالب</Label>
              <Input
                value={editTplTitle}
                onChange={(e) => setEditTplTitle(e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">دسته‌بندی قالب</Label>
              <Input
                value={editTplCat}
                onChange={(e) => setEditTplCat(e.target.value)}
                className="h-8 text-xs"
              />
            </div>
          </div>

          <DialogFooter className="flex items-center justify-end gap-2">
            <Button variant="outline" size="sm" onClick={() => setEditTemplate(null)}>
              انصراف
            </Button>
            <Button size="sm" onClick={handleSaveEditTemplate} disabled={savingEdit}>
              {savingEdit ? "در حال ثبت..." : "ذخیره تغییرات"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
