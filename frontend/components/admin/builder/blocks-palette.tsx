"use client";

import React, { useState, useMemo, useEffect, useCallback } from "react";
import { Search, Sparkles, Layout, Box, Loader2, Bookmark, FolderHeart } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { useBuilderStore, cloneElementWithNewIds } from "@/stores/builder-store";
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

  const addElement = useBuilderStore((s) => s.addElement);
  const selectedElementId = useBuilderStore((s) => s.selectedElementId);
  const ast = useBuilderStore((s) => s.ast);

  // Load section templates when templates tab is selected
  const fetchTemplates = useCallback(async () => {
    setLoadingTemplates(true);
    try {
      const data = await pageTemplatesAdminApi.list("section");
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
    return BASIC_BLOCK_DEFINITIONS.filter(
      (b) =>
        b.name.toLowerCase().includes(q) ||
        b.description.toLowerCase().includes(q) ||
        b.type.toLowerCase().includes(q)
    );
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
    const selectedEl = selectedElementId
      ? ast.rootElements.find((r) => r.id === selectedElementId)
      : null;
    return selectedEl?.type === "container" ? selectedEl.id : undefined;
  }, [ast.rootElements, selectedElementId]);

  const handleAddBasicBlock = (def: BlockDefinition) => {
    const newEl = def.createDefaultElement();
    addElement(newEl, getTargetContainerId());
  };

  const handleInsertPattern = async (pattern: BlockPattern) => {
    setRenderingSlug(pattern.slug);
    try {
      const res = await blockPatternsApi.render(pattern.slug, {});
      const vars = Object.fromEntries(
        pattern.variables.map((v) => [v.name, v.default])
      );
      const newEl = createPatternElement(pattern, res.html, vars);
      addElement(newEl, getTargetContainerId());
      toast({
        title: "الگو افزوده شد",
        description: `الگوی «${pattern.title}» به برگه اضافه شد.`,
      });
    } catch (err) {
      console.error("Failed to render pattern:", err);
      toast({
        title: "خطا در افزودن الگو",
        description: "رندر الگوی انتخابی با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setRenderingSlug(null);
    }
  };

  const handleInsertTemplate = (tpl: PageTemplate) => {
    const bData = (tpl as any).builder_data || tpl.builderData;
    const rootEls = bData?.rootElements || (bData as any)?.root_elements || [];
    if (rootEls.length === 0) return;
    for (const el of rootEls) {
      const cloned = cloneElementWithNewIds(el);
      addElement(cloned, getTargetContainerId());
    }
    toast({
      title: "قالب افزوده شد",
      description: `قالب «${tpl.title}» به بوم اضافه شد.`,
    });
  };

  const filteredSavedTemplates = useMemo(() => {
    const q = search.trim().toLowerCase();
    return savedTemplates.filter((t) => {
      if (!q) return true;
      return t.title.toLowerCase().includes(q) || (t.category || "").toLowerCase().includes(q);
    });
  }, [savedTemplates, search]);

  return (
    <div className="flex flex-col h-full space-y-3 p-3 select-none">
      {/* Sub-tab toggle: Basic Blocks vs Ready Patterns vs Saved Templates */}
      <div className="grid grid-cols-3 p-1 rounded-xl bg-muted/60 border border-border/70 text-xs shrink-0 gap-1">
        <button
          type="button"
          onClick={() => setActiveTab("basic")}
          className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-[11px] font-semibold transition ${
            activeTab === "basic"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Box className="w-3 h-3 shrink-0" />
          <span className="truncate">بلوک‌های پایه ({filteredBasicBlocks.length})</span>
        </button>

        <button
          type="button"
          onClick={() => setActiveTab("patterns")}
          className={`flex items-center justify-center gap-1 py-1.5 rounded-lg text-[11px] font-semibold transition ${
            activeTab === "patterns"
              ? "bg-background text-foreground shadow-sm"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Sparkles className="w-3 h-3 text-amber-500 shrink-0" />
          <span className="truncate">الگوهای آماده ({allPatterns.length})</span>
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
          <span className="truncate">قالب‌های من</span>
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
        <div className="flex gap-1 overflow-x-auto pb-1 shrink-0 no-scrollbar">
          <button
            type="button"
            onClick={() => setSelectedCategory("all")}
            className={`px-2 py-0.5 rounded-md text-[11px] font-medium shrink-0 transition ${
              selectedCategory === "all"
                ? "bg-primary text-primary-foreground font-bold"
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
              className={`px-2 py-0.5 rounded-md text-[11px] font-medium shrink-0 transition ${
                selectedCategory === cat
                  ? "bg-primary text-primary-foreground font-bold"
                  : "bg-muted/70 text-muted-foreground hover:text-foreground"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Main Tab Content */}
      <div className="flex-1 overflow-y-auto space-y-4 pe-1">
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
                        draggable={true}
                        onDragStart={(e) => {
                          e.dataTransfer.setData(
                            "application/json",
                            JSON.stringify({ type: "block_def", blockType: block.type })
                          );
                          e.dataTransfer.effectAllowed = "all";
                        }}
                        onClick={() => handleAddBasicBlock(block)}
                        className="flex flex-col items-center justify-center p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-center transition shadow-sm group cursor-grab active:cursor-grabbing"
                        title="کلیک برای افزودن، یا کشیدن با ماوس به داخل بوم"
                      >
                        <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary mb-1.5 transition-colors" />
                        <span className="text-xs font-semibold text-foreground line-clamp-1">
                          {(block.name.split("(")[0] ?? block.name).trim()}
                        </span>
                        <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
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
                        draggable={true}
                        onDragStart={(e) => {
                          e.dataTransfer.setData(
                            "application/json",
                            JSON.stringify({ type: "block_def", blockType: block.type })
                          );
                          e.dataTransfer.effectAllowed = "all";
                        }}
                        onClick={() => handleAddBasicBlock(block)}
                        className="flex flex-col items-center justify-center p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/50 hover:border-primary/50 text-center transition shadow-sm group cursor-grab active:cursor-grabbing"
                        title="کلیک برای افزودن، یا کشیدن با ماوس به داخل بوم"
                      >
                        <Icon className="w-5 h-5 text-muted-foreground group-hover:text-primary mb-1.5 transition-colors" />
                        <span className="text-xs font-semibold text-foreground line-clamp-1">
                          {(block.name.split("(")[0] ?? block.name).trim()}
                        </span>
                        <span className="text-[10px] text-muted-foreground mt-0.5 line-clamp-1">
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
                        <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                          {pattern.category}
                        </Badge>
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
            {loadingTemplates ? (
              <div className="flex items-center justify-center py-12 text-xs text-muted-foreground gap-2">
                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                <span>در حال بارگذاری قالب‌های من...</span>
              </div>
            ) : filteredSavedTemplates.length === 0 ? (
              <div className="text-center py-10 px-3 border border-dashed rounded-xl border-border/80 text-muted-foreground space-y-2">
                <Bookmark className="w-8 h-8 opacity-30 mx-auto" />
                <p className="text-xs font-semibold text-foreground">هنوز قالبی ذخیره نکرده‌اید</p>
                <p className="text-[11px] leading-relaxed">
                  می‌توانید هر کانتینر یا بخش را از نوار ابزار شناور آن روی بوم با دکمه «ذخیره به عنوان قالب» ذخیره کنید تا در این بخش نمایش داده شود.
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredSavedTemplates.map((tpl) => (
                  <div
                    key={tpl.id}
                    draggable={true}
                    onDragStart={(e) => {
                      const bData = (tpl as any).builder_data || tpl.builderData;
                      const rootEls = bData?.rootElements || (bData as any)?.root_elements || [];
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
                    onClick={() => handleInsertTemplate(tpl)}
                    className="p-3 rounded-xl border border-border/80 bg-card hover:bg-muted/40 hover:border-primary/50 transition cursor-grab active:cursor-grabbing shadow-sm space-y-1.5 group"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-foreground group-hover:text-primary transition-colors">
                        {tpl.title}
                      </span>
                      <Badge variant="outline" className="text-[10px] px-1.5 py-0 h-4">
                        {tpl.category || "عمومی"}
                      </Badge>
                    </div>
                    <div className="flex items-center justify-between pt-1 border-t border-border/40 text-[10px] text-muted-foreground">
                      <span>{((tpl as any).builder_data?.rootElements || tpl.builderData?.rootElements || []).length || 1} بخش محتوایی</span>
                      <span className="text-primary font-semibold">کلیک یا درگ ↵</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
