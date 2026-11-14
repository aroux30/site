"use client";

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
} from "react";
import { createPortal } from "react-dom";
import { useRouter } from "next/navigation";
import {
  Monitor,
  Tablet,
  Smartphone,
  Eye,
  Edit3,
  Plus,
  PlusCircle,
  Save,
  Check,
  X,
  ArrowRight,
  ChevronUp,
  ChevronDown,
  Trash2,
  Sparkles,
  Layers,
  Search,
  PanelRightClose,
  PanelRightOpen,
  Loader2,
  Info,
  ExternalLink,
  RefreshCw,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { useToast } from "@/components/ui/use-toast";
import { cmsPagesAdminApi } from "@/lib/api/content";
import { blogAdminApi } from "@/lib/api/blog";
import {
  blockPatternsApi,
  type BlockPattern,
  type BlockPatternCategoryGroup,
} from "@/lib/api/block-patterns";
import { useAuth } from "@/hooks/use-auth";
import { cn, toPersianDigits } from "@/lib/utils";
import { RemoteImage } from "@/components/shared/remote-image";
import cleanHtml from "@/lib/sanitize-html";

export interface VisualPageEditorProps {
  page: {
    id?: string;
    title: string;
    slug: string;
    body_html: string;
    excerpt?: string | null;
    cover_image_url?: string | null;
    seo_title?: string | null;
    seo_description?: string | null;
    updated_at?: string;
    status?: string;
  };
  contentType?: "page" | "post" | "showcase";
  onSave?: (finalHtml: string) => Promise<void>;
  onExit?: () => void;
}

interface SectionItem {
  id: string;
  html: string;
}

type ViewportMode = "desktop" | "tablet" | "mobile";
type EditorMode = "edit" | "preview";
type SidePanelTab = "navigator" | "patterns" | "info";

/**
 * Extracts sections or top-level HTML blocks from raw HTML.
 */
function parseSectionsFromHtml(rawHtml: string): SectionItem[] {
  if (typeof window === "undefined") {
    return [{ id: "sec-1", html: rawHtml || "" }];
  }

  const trimmed = (rawHtml || "").trim();
  if (!trimmed) {
    return [
      {
        id: "sec-default",
        html: `<section class="py-12 text-center" dir="rtl"><div class="container mx-auto px-4"><h2 class="text-2xl font-bold text-foreground">بخش آغازین</h2><p class="mt-3 text-muted-foreground">برای افزودن محتوا روی متن کلیک کرده و ویرایش کنید، یا از دکمه «افزودن الگو» استفاده نمایید.</p></div></section>`,
      },
    ];
  }

  const parser = new DOMParser();
  const doc = parser.parseFromString(trimmed, "text/html");
  const nodes = Array.from(doc.body.childNodes);
  const items: SectionItem[] = [];
  let textBuffer = "";

  for (const node of nodes) {
    if (!node) continue;
    if (node.nodeType === Node.ELEMENT_NODE) {
      if (textBuffer.trim()) {
        items.push({
          id: `sec-${items.length + 1}`,
          html: `<section class="py-6" dir="rtl">${textBuffer.trim()}</section>`,
        });
        textBuffer = "";
      }
      items.push({
        id: `sec-${items.length + 1}`,
        html: (node as Element).outerHTML,
      });
    } else if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) {
      textBuffer += node.textContent;
    }
  }

  if (textBuffer.trim()) {
    items.push({
      id: `sec-${items.length + 1}`,
      html: `<section class="py-6" dir="rtl">${textBuffer.trim()}</section>`,
    });
  }

  return items.length > 0
    ? items
    : [
        {
          id: "sec-fallback",
          html: trimmed,
        },
      ];
}

/**
 * Extracts a concise human-readable summary/heading from section HTML for the navigator.
 * Pure isomorphic regex ensures identical output on SSR and browser hydration.
 */
function getSectionSummary(html: string): string {
  if (!html) return "بخش محتوایی";
  try {
    const headingMatch = html.match(/<h[1-6][^>]*>([\s\S]*?)<\/h[1-6]>/i);
    if (headingMatch && headingMatch[1]) {
      const clean = headingMatch[1].replace(/<[^>]+>/g, "").trim();
      if (clean) return clean.slice(0, 32);
    }
    const pMatch = html.match(/<p[^>]*>([\s\S]*?)<\/p>/i);
    if (pMatch && pMatch[1]) {
      const clean = pMatch[1].replace(/<[^>]+>/g, "").trim();
      if (clean) return clean.slice(0, 32);
    }
    const clean = html.replace(/<[^>]+>/g, "").trim();
    if (clean) return clean.slice(0, 32);
    return "بخش محتوایی";
  } catch {
    return "بخش محتوایی";
  }
}

interface EditorCanvasFrameProps {
  viewport: ViewportMode;
  children: React.ReactNode;
  className?: string;
  onIframeReady?: (doc: Document) => void;
}

/**
 * Renders the editor canvas inside an isolated iframe.
 *
 * This guarantees that CSS `@media` queries evaluate against the actual device
 * frame width (e.g. 375px for mobile), matching real phones and Chrome DevTools
 * device mode with 100% fidelity without squishing desktop multi-column grids.
 */
function EditorCanvasFrame({
  viewport,
  children,
  className,
  onIframeReady,
}: EditorCanvasFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [mountNode, setMountNode] = useState<HTMLElement | null>(null);
  const [iframeDoc, setIframeDoc] = useState<Document | null>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const doc = iframe.contentDocument;
    if (!doc) return;

    if (!doc.getElementById("editor-canvas-mount")) {
      doc.open();
      doc.write(
        '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/></head><body class="bg-background text-foreground font-sans antialiased p-0 m-0 overflow-x-hidden min-h-full"><div id="editor-canvas-mount"></div></body></html>',
      );
      doc.close();
    }

    const mount = doc.getElementById("editor-canvas-mount");
    setMountNode(mount);
    setIframeDoc(doc);
    onIframeReady?.(doc);

    // Sync styles and classes from parent document
    const syncStyles = () => {
      if (!doc.head || !doc.documentElement) return;

      // Copy html attributes (dark theme, vazirmatn font variable, direction)
      doc.documentElement.className = document.documentElement.className;
      doc.documentElement.dir = document.documentElement.dir || "rtl";
      doc.documentElement.lang = document.documentElement.lang || "fa";

      const parentStyle = document.documentElement.getAttribute("style");
      if (parentStyle) {
        doc.documentElement.setAttribute("style", parentStyle);
      }

      // Sync stylesheets
      const existingHrefs = new Set(
        Array.from(doc.head.querySelectorAll("link[rel='stylesheet']")).map(
          (l) => (l as HTMLLinkElement).href,
        ),
      );

      document.querySelectorAll("link[rel='stylesheet']").forEach((link) => {
        const href = (link as HTMLLinkElement).href;
        if (href && !existingHrefs.has(href)) {
          const clone = link.cloneNode(true) as HTMLLinkElement;
          doc.head.appendChild(clone);
        }
      });

      // Sync style tags
      const existingStyleTexts = new Set(
        Array.from(doc.head.querySelectorAll("style")).map((s) => s.textContent),
      );
      document.querySelectorAll("style").forEach((style) => {
        if (style.textContent && !existingStyleTexts.has(style.textContent)) {
          const clone = style.cloneNode(true);
          doc.head.appendChild(clone);
        }
      });
    };

    syncStyles();

    // Observe theme toggles (dark/light)
    const themeObserver = new MutationObserver(() => {
      syncStyles();
    });
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "dir", "style"],
    });

    // Observe head changes (styles added dynamically by Next.js)
    const headObserver = new MutationObserver(() => {
      syncStyles();
    });
    headObserver.observe(document.head, {
      childList: true,
      subtree: true,
    });

    return () => {
      themeObserver.disconnect();
      headObserver.disconnect();
    };
  }, [onIframeReady]);

  // Dynamic height adjustment to avoid nested scrollbars
  useEffect(() => {
    if (!iframeRef.current || !iframeDoc) return;
    const iframe = iframeRef.current;
    const doc = iframeDoc;

    const updateHeight = () => {
      if (!iframe || !doc.body) return;
      const h = Math.max(
        doc.body.scrollHeight,
        doc.documentElement.scrollHeight,
        600,
      );
      iframe.style.height = `${h + 30}px`;
    };

    updateHeight();

    const ro = new ResizeObserver(() => {
      updateHeight();
    });

    if (doc.body) ro.observe(doc.body);
    if (doc.documentElement) ro.observe(doc.documentElement);

    return () => {
      ro.disconnect();
    };
  }, [iframeDoc, children, viewport]);

  return (
    <div className={cn("relative transition-all duration-300 w-full", className)}>
      <iframe
        ref={iframeRef}
        title="Elementor Canvas Viewport"
        className={cn(
          "border-0 block bg-transparent transition-all duration-300 mx-auto",
          viewport === "desktop" && "w-full",
          viewport === "tablet" && "w-[768px]",
          viewport === "mobile" && "w-[375px]",
        )}
        style={{ minHeight: "680px" }}
      />
      {mountNode && createPortal(children, mountNode)}
    </div>
  );
}

export function VisualPageEditor({
  page,
  contentType = "page",
  onSave,
  onExit,
}: VisualPageEditorProps) {
  const router = useRouter();
  const { toast } = useToast();
  const { user, isLoading: authLoading, isAuthenticated } = useAuth();

  // Mode and Viewport
  const [mode, setMode] = useState<EditorMode>("edit");
  const [viewport, setViewport] = useState<ViewportMode>("desktop");
  const [iframeDoc, setIframeDoc] = useState<Document | null>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    setSections(parseSectionsFromHtml(page.body_html));
  }, [page.body_html]);

  // Smooth scroll to target section (works across iframe boundary)
  const scrollToSection = useCallback(
    (id: string) => {
      const el = iframeDoc?.getElementById(id) || document.getElementById(id);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
      }
    },
    [iframeDoc],
  );

  // Prevent link navigation inside the canvas while in edit mode
  const handleCanvasClick = useCallback((e: React.MouseEvent) => {
    const target = (e.target as HTMLElement).closest("a");
    if (target) {
      e.preventDefault();
    }
  }, []);

  // Sections and edit state
  const [sections, setSections] = useState<SectionItem[]>(() =>
    parseSectionsFromHtml(page.body_html),
  );
  const [isDirty, setIsDirty] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  // Palette drawer
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [insertIndex, setInsertIndex] = useState<number | null>(null);
  const [paletteSearch, setPaletteSearch] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [patternGroups, setPatternGroups] = useState<BlockPatternCategoryGroup[]>([]);
  const [loadingPatterns, setLoadingPatterns] = useState(false);
  const [insertingSlug, setInsertingSlug] = useState<string | null>(null);

  // Floating/Docked Elementor side panel
  const [panelOpen, setPanelOpen] = useState(true);
  const [panelTab, setPanelTab] = useState<SidePanelTab>("navigator");

  // Live DOM references for contentEditable sections
  const sectionDomRefs = useRef<Record<string, HTMLDivElement | null>>({});

  // Load available block patterns
  const loadPatterns = useCallback(async () => {
    setLoadingPatterns(true);
    try {
      const groups = await blockPatternsApi.list();
      setPatternGroups(groups);
    } catch (err) {
      console.error("Failed to load block patterns:", err);
    } finally {
      setLoadingPatterns(false);
    }
  }, []);

  useEffect(() => {
    void loadPatterns();
  }, [loadPatterns]);

  // Handle exiting editor
  const handleExit = useCallback(() => {
    if (onExit) {
      onExit();
      return;
    }
    const cleanUrl = contentType === "post" ? `/blog/${page.slug}` : `/${page.slug}`;
    router.push(cleanUrl);
  }, [contentType, onExit, page.slug, router]);

  // Synchronize live DOM into sections array before reordering or saving
  const getLiveHtml = useCallback((): string => {
    return sections
      .map((sec) => {
        const dom = sectionDomRefs.current[sec.id];
        if (dom) {
          return dom.innerHTML.trim();
        }
        return sec.html.trim();
      })
      .filter(Boolean)
      .join("\n\n");
  }, [sections]);

  // Move section up
  const moveSectionUp = useCallback((index: number) => {
    if (index <= 0) return;
    setSections((prev) => {
      // Flush current dom to avoid losing uncommitted inline edits
      const updated = prev.map((s) => {
        const dom = sectionDomRefs.current[s.id];
        return dom ? { ...s, html: dom.innerHTML } : s;
      });
      const temp = updated[index];
      const prevItem = updated[index - 1];
      if (temp && prevItem) {
        updated[index] = prevItem;
        updated[index - 1] = temp;
      }
      return [...updated];
    });
    setIsDirty(true);
  }, []);

  // Move section down
  const moveSectionDown = useCallback((index: number) => {
    setSections((prev) => {
      if (index >= prev.length - 1) return prev;
      const updated = prev.map((s) => {
        const dom = sectionDomRefs.current[s.id];
        return dom ? { ...s, html: dom.innerHTML } : s;
      });
      const temp = updated[index];
      const nextItem = updated[index + 1];
      if (temp && nextItem) {
        updated[index] = nextItem;
        updated[index + 1] = temp;
      }
      return [...updated];
    });
    setIsDirty(true);
  }, []);

  // Delete section
  const removeSection = useCallback(
    (index: number) => {
      setSections((prev) => {
        const updated = prev.filter((_, i) => i !== index);
        return updated;
      });
      setIsDirty(true);
      toast({
        title: "بخش حذف شد",
        description: `بخش ${toPersianDigits(String(index + 1))} از صفحه برداشته شد.`,
      });
    },
    [toast],
  );

  // ContentEditable blur handler
  const handleSectionBlur = useCallback((id: string, el: HTMLDivElement) => {
    const newHtml = el.innerHTML;
    setSections((prev) =>
      prev.map((s) => (s.id === id ? { ...s, html: newHtml } : s)),
    );
    setIsDirty(true);
  }, []);

  // Open pattern palette targeting specific index
  const openPaletteAfter = useCallback((index: number) => {
    setInsertIndex(index + 1);
    setPaletteOpen(true);
  }, []);

  // Insert a block pattern
  const handleInsertPattern = useCallback(
    async (pattern: BlockPattern) => {
      setInsertingSlug(pattern.slug);
      try {
        const res = await blockPatternsApi.render(pattern.slug, {});
        const renderedHtml = res.html;
        const newSec: SectionItem = {
          id: `sec-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
          html: renderedHtml,
        };

        setSections((prev) => {
          // Flush live edits
          const flushed = prev.map((s) => {
            const dom = sectionDomRefs.current[s.id];
            return dom ? { ...s, html: dom.innerHTML } : s;
          });

          const target =
            insertIndex !== null && insertIndex <= flushed.length
              ? insertIndex
              : flushed.length;
          const updated = [...flushed];
          updated.splice(target, 0, newSec);
          return updated;
        });

        setIsDirty(true);
        setPaletteOpen(false);
        setInsertIndex(null);

        toast({
          title: "الگو افزوده شد",
          description: `الگوی «${pattern.title}» با موفقیت به برگه اضافه شد.`,
        });

        // Scroll to the newly added section
        setTimeout(() => {
          scrollToSection(newSec.id);
        }, 150);
      } catch (err) {
        console.error("Failed to render and insert pattern:", err);
        toast({
          title: "خطا در درج الگو",
          description: "ساخت HTML الگو ناموفق بود. لطفاً دوباره تلاش کنید.",
          variant: "destructive",
        });
      } finally {
        setInsertingSlug(null);
      }
    },
    [insertIndex, toast],
  );

  // Save and Publish
  const handleSave = useCallback(async () => {
    setIsSaving(true);
    try {
      const finalHtml = getLiveHtml();

      if (onSave) {
        await onSave(finalHtml);
      } else if (contentType === "post") {
        let postId = page.id;
        if (!postId) {
          const list = await blogAdminApi.listPosts({ search: page.slug });
          const found = list.items.find((p) => p.slug === page.slug);
          if (found) postId = found.id;
        }
        if (!postId) {
          throw new Error("شناسه نوشته یافت نشد");
        }
        await blogAdminApi.updatePost(postId, {
          content: finalHtml,
        });
      } else {
        let pageId = page.id;
        if (!pageId) {
          // Resolve page ID by slug
          const list = await cmsPagesAdminApi.listPages({ search: page.slug });
          const found = list.items.find((p) => p.slug === page.slug);
          if (found) {
            pageId = found.id;
          }
        }

        if (!pageId) {
          throw new Error("شناسه برگه یافت نشد");
        }

        await cmsPagesAdminApi.updatePage(pageId, {
          body_html: finalHtml,
        });
      }

      setIsDirty(false);
      toast({
        title: "ذخیره و انتشار موفق",
        description:
          contentType === "post"
            ? "تغییرات نوشته با موفقیت ذخیره و در سایت منتشر شد."
            : "تغییرات برگه با موفقیت ذخیره و در سایت منتشر شد.",
      });
    } catch (err) {
      console.error("Save error:", err);
      toast({
        title: "خطا در ذخیره‌سازی",
        description: "ذخیره تغییرات ناموفق بود. لطفاً ارتباط با سرور را بررسی کنید.",
        variant: "destructive",
      });
    } finally {
      setIsSaving(false);
    }
  }, [contentType, getLiveHtml, onSave, page.id, page.slug, toast]);

  // Filtered patterns for drawer
  const allPatterns = useMemo(() => {
    const list: BlockPattern[] = [];
    patternGroups.forEach((group) => {
      group.patterns.forEach((p) => {
        if (!list.some((item) => item.slug === p.slug)) {
          list.push(p);
        }
      });
    });
    return list;
  }, [patternGroups]);

  const categories = useMemo(() => {
    return patternGroups.map((g) => g.category);
  }, [patternGroups]);

  const filteredPatterns = useMemo(() => {
    const query = paletteSearch.trim().toLowerCase();
    return allPatterns.filter((pattern) => {
      const matchesCategory =
        selectedCategory === "all" || pattern.category === selectedCategory;
      if (!matchesCategory) return false;
      if (!query) return true;
      const haystack = [
        pattern.title,
        pattern.description,
        pattern.category,
        ...(pattern.keywords || []),
      ]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [allPatterns, paletteSearch, selectedCategory]);

  // Non-admin guard fallback: if auth is loaded and user is not admin, show clean view
  if (!authLoading && (!isAuthenticated || user?.role !== "admin")) {
    return (
      <article className="mx-auto max-w-3xl px-4 py-10" dir="rtl">
        {page.cover_image_url && (
          <div className="relative mb-8 h-56 w-full overflow-hidden rounded-2xl border border-border md:h-80">
            <RemoteImage
              src={page.cover_image_url}
              alt={page.title}
              className="h-full w-full object-cover"
              sizes="(max-width: 768px) 100vw, 768px"
              priority
            />
          </div>
        )}
        <header className="mb-8">
          <h1 className="text-3xl font-bold text-foreground">{page.title}</h1>
          {page.excerpt ? (
            <p className="mt-3 text-muted-foreground">{page.excerpt}</p>
          ) : null}
        </header>
        <div
          className="cms-content max-w-none leading-8 text-foreground"
          dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html) }}
        />
      </article>
    );
  }

  return (
    <div className="min-h-screen bg-muted/20 dark:bg-muted/5 font-sans" dir="rtl">
      {/* ── TOP TOOLBAR ─────────────────────────────────────────────────── */}
      <header className="fixed inset-x-0 top-0 z-50 flex h-14 items-center justify-between border-b border-border bg-background/95 px-3 sm:px-6 shadow-sm backdrop-blur">
        {/* Start / Right: Brand & Title & Mode Toggle */}
        <div className="flex items-center gap-2 sm:gap-4 overflow-x-auto">
          {/* Elementor Brand Badge */}
          <div className="flex items-center gap-2 rounded-lg bg-gradient-to-r from-purple-600 to-pink-600 px-2.5 py-1 text-white shadow-sm">
            <Sparkles className="h-4 w-4" />
            <span className="text-xs font-bold tracking-tight hidden sm:inline">
              {contentType === "post" ? "المنتور نوشته" : "المنتور برگه"}
            </span>
          </div>

          <span className="hidden md:inline text-xs font-semibold text-foreground truncate max-w-[140px] lg:max-w-[200px]">
            {page.title}
          </span>

          <span className="h-4 w-px bg-border hidden sm:inline" />

          {/* Toggle Edit Mode / Preview Mode */}
          <div className="flex items-center rounded-lg border border-border bg-muted/60 p-0.5">
            <button
              type="button"
              onClick={() => setMode("edit")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                mode === "edit"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Edit3 className="h-3.5 w-3.5 text-primary" />
              <span>ویرایش</span>
            </button>
            <button
              type="button"
              onClick={() => setMode("preview")}
              className={cn(
                "flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-all",
                mode === "preview"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Eye className="h-3.5 w-3.5 text-emerald-600" />
              <span>پیش‌نمایش</span>
            </button>
          </div>

          {/* Viewport Switcher */}
          <div className="flex items-center rounded-lg border border-border bg-muted/60 p-0.5">
            <button
              type="button"
              onClick={() => setViewport("desktop")}
              title="نمایش دسکتاپ (۱۰۰٪)"
              className={cn(
                "flex items-center justify-center rounded-md p-1.5 text-xs transition-all",
                viewport === "desktop"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Monitor className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setViewport("tablet")}
              title="نمایش تبلت (۷۶۸ پیکسل)"
              className={cn(
                "flex items-center justify-center rounded-md p-1.5 text-xs transition-all",
                viewport === "tablet"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Tablet className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => setViewport("mobile")}
              title="نمایش موبایل (۳۷۵ پیکسل)"
              className={cn(
                "flex items-center justify-center rounded-md p-1.5 text-xs transition-all",
                viewport === "mobile"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              <Smartphone className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>

        {/* Center / Actions: Add Pattern */}
        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            className="h-8 gap-1.5 border-dashed border-primary/50 text-xs font-semibold text-primary hover:bg-primary/10"
            onClick={() => {
              setInsertIndex(null);
              setPaletteOpen(true);
            }}
          >
            <PlusCircle className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">افزودن الگو</span>
          </Button>
        </div>

        {/* End / Left: Status & Cancel & Save */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Unsaved indicator */}
          <div className="hidden lg:flex items-center text-xs">
            {isDirty ? (
              <span className="flex items-center gap-1.5 text-amber-600 font-medium">
                <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                تغییرات ذخیره‌نشده
              </span>
            ) : (
              <span className="flex items-center gap-1.5 text-emerald-600 font-medium">
                <Check className="h-3.5 w-3.5" />
                ذخیره شده
              </span>
            )}
          </div>

          {/* لغو و بازگشت */}
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleExit}
            className="h-8 px-2 sm:px-3 text-xs text-muted-foreground hover:text-foreground"
          >
            <ArrowRight className="h-3.5 w-3.5 sm:me-1.5" />
            <span className="hidden sm:inline">لغو و بازگشت</span>
          </Button>

          {/* ذخیره و انتشار */}
          <Button
            type="button"
            size="sm"
            onClick={() => void handleSave()}
            disabled={isSaving}
            className="h-8 gap-1.5 bg-emerald-600 px-3 text-xs font-semibold text-white hover:bg-emerald-700 shadow-sm"
          >
            {isSaving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Save className="h-3.5 w-3.5" />
            )}
            <span>ذخیره و انتشار</span>
          </Button>
        </div>
      </header>

      {/* ── ELEMENTOR FLOATING / DOCKED SIDE PANEL (RTL-aware start-4) ─── */}
      {panelOpen ? (
        <aside
          className="fixed top-18 start-4 z-40 w-72 md:w-80 rounded-2xl border border-border bg-card/95 backdrop-blur-md shadow-2xl transition-all duration-300 flex flex-col max-h-[calc(100vh-5.5rem)] overflow-hidden"
          dir="rtl"
        >
          {/* Panel Header */}
          <div className="flex items-center justify-between border-b border-border/80 px-3.5 py-2.5 bg-muted/40">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-primary/10 text-primary">
                <Layers className="h-3.5 w-3.5" />
              </span>
              <span className="text-xs font-bold text-foreground">
                کنترل پنل المنتور
              </span>
            </div>
            <button
              type="button"
              onClick={() => setPanelOpen(false)}
              className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
              title="بستن پنل"
            >
              <PanelRightClose className="h-4 w-4" />
            </button>
          </div>

          {/* Panel Navigation Tabs */}
          <div className="flex border-b border-border/60 bg-muted/20 px-2 py-1 text-xs">
            <button
              type="button"
              onClick={() => setPanelTab("navigator")}
              className={cn(
                "flex-1 py-1.5 text-center font-medium rounded-md transition-all",
                panelTab === "navigator"
                  ? "bg-background text-primary shadow-sm font-semibold"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              لایه‌ها {mounted ? `(${toPersianDigits(String(sections.length))})` : ""}
            </button>
            <button
              type="button"
              onClick={() => setPanelTab("patterns")}
              className={cn(
                "flex-1 py-1.5 text-center font-medium rounded-md transition-all",
                panelTab === "patterns"
                  ? "bg-background text-primary shadow-sm font-semibold"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              الگوها
            </button>
            <button
              type="button"
              onClick={() => setPanelTab("info")}
              className={cn(
                "flex-1 py-1.5 text-center font-medium rounded-md transition-all",
                panelTab === "info"
                  ? "bg-background text-primary shadow-sm font-semibold"
                  : "text-muted-foreground hover:text-foreground",
              )}
            >
              اطلاعات
            </button>
          </div>

          {/* Panel Body */}
          <div className="flex-1 overflow-y-auto p-3 text-xs space-y-3">
            {/* TAB: NAVIGATOR */}
            {panelTab === "navigator" && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-muted-foreground">
                  <span className="text-[11px]">ترتیب و ساختار بخش‌ها:</span>
                  <button
                    type="button"
                    onClick={() => {
                      setInsertIndex(sections.length);
                      setPaletteOpen(true);
                    }}
                    className="flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
                  >
                    <Plus className="h-3 w-3" />
                    افزودن بخش
                  </button>
                </div>

                {!mounted ? (
                  <div className="py-6 flex justify-center text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                  </div>
                ) : sections.length === 0 ? (
                  <p className="py-6 text-center text-muted-foreground">
                    هیچ بخشی در برگه وجود ندارد.
                  </p>
                ) : (
                  <div className="space-y-1.5">
                    {sections.map((sec, idx) => (
                      <div
                        key={sec.id}
                        className="group flex items-center justify-between gap-1.5 rounded-lg border border-border/60 bg-background/80 p-2 hover:border-primary/50 hover:bg-muted/40 transition-colors"
                      >
                        <button
                          type="button"
                          onClick={() => scrollToSection(sec.id)}
                          className="flex items-center gap-2 text-start flex-1 truncate"
                        >
                          <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-primary/10 text-[10px] font-bold text-primary">
                            {toPersianDigits(String(idx + 1))}
                          </span>
                          <span className="truncate text-xs font-medium text-foreground">
                            {getSectionSummary(sec.html)}
                          </span>
                        </button>

                        <div className="flex items-center gap-0.5 shrink-0">
                          <button
                            type="button"
                            disabled={idx === 0}
                            onClick={() => moveSectionUp(idx)}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
                            title="انتقال به بالا"
                          >
                            <ChevronUp className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            disabled={idx === sections.length - 1}
                            onClick={() => moveSectionDown(idx)}
                            className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-30"
                            title="انتقال به پایین"
                          >
                            <ChevronDown className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => removeSection(idx)}
                            className="rounded p-1 text-destructive/70 hover:bg-destructive/10 hover:text-destructive"
                            title="حذف بخش"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* TAB: PATTERNS QUICK LIST */}
            {panelTab === "patterns" && (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] text-muted-foreground">
                    الگوهای پرکاربرد:
                  </span>
                  <button
                    type="button"
                    onClick={() => {
                      setInsertIndex(null);
                      setPaletteOpen(true);
                    }}
                    className="text-[11px] font-semibold text-primary hover:underline"
                  >
                    نمایش کامل
                  </button>
                </div>

                <div className="space-y-1.5 max-h-[320px] overflow-y-auto pe-1">
                  {allPatterns.slice(0, 8).map((p) => (
                    <div
                      key={p.slug}
                      className="flex items-center justify-between gap-2 rounded-lg border border-border/60 bg-background/80 p-2 hover:border-primary/50"
                    >
                      <div className="truncate">
                        <p className="font-semibold text-foreground text-xs truncate">
                          {p.title}
                        </p>
                        <p className="text-[10px] text-muted-foreground truncate">
                          {p.category}
                        </p>
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        variant="secondary"
                        disabled={insertingSlug === p.slug}
                        onClick={() => void handleInsertPattern(p)}
                        className="h-6 px-2 text-[11px] shrink-0"
                      >
                        {insertingSlug === p.slug ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          "درج"
                        )}
                      </Button>
                    </div>
                  ))}
                </div>

                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setInsertIndex(null);
                    setPaletteOpen(true);
                  }}
                  className="w-full text-xs gap-1.5"
                >
                  <PlusCircle className="h-3.5 w-3.5" />
                  کتابخانه تمام الگوها
                </Button>
              </div>
            )}

            {/* TAB: PAGE INFO */}
            {panelTab === "info" && (
              <div className="space-y-2.5">
                <div className="rounded-lg border border-border/60 bg-background/80 p-2.5 space-y-1.5">
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">عنوان برگه:</span>
                    <span className="font-semibold text-foreground">
                      {page.title}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">نامک (Slug):</span>
                    <span className="font-mono text-foreground" dir="ltr">
                      /{page.slug}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">تعداد بخش‌ها:</span>
                    <span className="font-semibold text-primary">
                      {mounted ? toPersianDigits(String(sections.length)) : "..."}
                    </span>
                  </div>
                  {page.updated_at && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">آخرین تغییر:</span>
                      <span className="text-foreground">
                        {toPersianDigits(page.updated_at.slice(0, 10))}
                      </span>
                    </div>
                  )}
                </div>

                <div className="text-[11px] text-muted-foreground leading-5 p-2 bg-muted/40 rounded-lg">
                  💡 <strong>نکته ویرایش:</strong> در حالت «ویرایش»، روی هر متن یا
                  عنوان مستقیماً کلیک کنید تا آن را تغییر دهید.
                </div>
              </div>
            )}
          </div>
        </aside>
      ) : (
        /* Collapsed Panel Pill (start-4) */
        <button
          type="button"
          onClick={() => setPanelOpen(true)}
          className="fixed top-18 start-4 z-40 flex items-center gap-2 rounded-xl border border-border bg-card/95 px-3 py-2 text-xs font-semibold text-foreground shadow-xl backdrop-blur-md hover:bg-muted transition-all"
          title="باز کردن پنل المنتور"
        >
          <Sparkles className="h-4 w-4 text-purple-600" />
          <span>پنل المنتور</span>
          <PanelRightOpen className="h-3.5 w-3.5 text-muted-foreground" />
        </button>
      )}

      {/* ── CANVAS & VIEWPORT CONTAINER ─────────────────────────────────── */}
      <main
        className={cn(
          "pt-18 pb-24 transition-all duration-300 min-h-screen",
          // Give padding on start side when panel is open on desktop
          panelOpen ? "lg:ps-88" : "ps-4",
          "pe-4",
        )}
      >
        <div
          className={cn(
            "transition-all duration-300 mx-auto",
            viewport === "desktop" && "w-full max-w-4xl",
            viewport === "tablet" &&
              "w-[800px] rounded-2xl border-2 border-border/80 bg-background shadow-2xl p-4 my-6 overflow-hidden min-h-[850px]",
            viewport === "mobile" &&
              "w-[395px] rounded-3xl border-4 border-muted-foreground/30 bg-background shadow-2xl p-2.5 my-6 overflow-hidden min-h-[680px]",
          )}
        >
          {/* Device viewport frame header indicator */}
          {viewport !== "desktop" && (
            <div className="mb-3 flex items-center justify-between rounded-lg bg-muted/60 px-3 py-1.5 text-[11px] text-muted-foreground">
              <span className="font-semibold">
                {viewport === "tablet" ? "تبلت (۷۶۸px)" : "موبایل (۳۷۵px)"}
              </span>
              <span className="font-mono" dir="ltr">
                {viewport === "tablet" ? "768 × 1024" : "375 × 812"}
              </span>
            </div>
          )}

          <EditorCanvasFrame
            viewport={viewport}
            onIframeReady={(doc) => setIframeDoc(doc)}
          >
            <div onClick={handleCanvasClick} className="p-2 sm:p-4 min-h-full">
              {/* Hero Cover Image */}
          {page.cover_image_url && (
            <div className="relative mb-8 h-48 w-full overflow-hidden rounded-2xl border border-border md:h-72">
              <RemoteImage
                src={page.cover_image_url}
                alt={page.title}
                className="h-full w-full object-cover"
                sizes="(max-width: 768px) 100vw, 768px"
                priority
              />
            </div>
          )}

          {/* Page Title & Excerpt */}
          <header className="mb-8">
            <h1 className="text-3xl font-bold text-foreground">{page.title}</h1>
            {page.excerpt ? (
              <p className="mt-3 text-muted-foreground">{page.excerpt}</p>
            ) : null}
          </header>

          {/* ── SECTIONS LIST ─────────────────────────────────────────── */}
          {sections.length === 0 ? (
            <div className="my-12 rounded-2xl border-2 border-dashed border-border p-12 text-center bg-card/40">
              <Sparkles className="mx-auto h-8 w-8 text-primary/60 mb-3" />
              <h3 className="text-lg font-bold text-foreground">
                این برگه هنوز هیچ بخشی ندارد
              </h3>
              <p className="mt-1 text-sm text-muted-foreground">
                یک الگوی آماده انتخاب کنید تا ساخت برگه آغاز شود.
              </p>
              <Button
                type="button"
                className="mt-4 gap-2"
                onClick={() => {
                  setInsertIndex(0);
                  setPaletteOpen(true);
                }}
              >
                <PlusCircle className="h-4 w-4" />
                افزودن اولین الگو
              </Button>
            </div>
          ) : (
            <div className="space-y-6">
              {sections.map((sec, index) => (
                <section
                  key={sec.id}
                  id={sec.id}
                  className={cn(
                    "relative transition-all duration-200 group/sec",
                    mode === "edit"
                      ? "rounded-2xl border-2 border-dashed border-primary/25 hover:border-primary/70 bg-card/40 p-3 sm:p-5"
                      : "",
                  )}
                >
                  {/* Section Action Bar (Edit Mode Only) */}
                  {mode === "edit" && (
                    <div
                      contentEditable={false}
                      className="mb-3 flex items-center justify-between gap-1.5 rounded-xl border border-border bg-card/95 px-2.5 py-1.5 shadow-sm backdrop-blur"
                    >
                      {/* Section label and summary */}
                      <div className="flex items-center gap-1.5 min-w-0">
                        <span className="flex h-5 items-center justify-center rounded bg-primary/15 px-1.5 font-mono text-[11px] font-bold text-primary shrink-0">
                          بخش {toPersianDigits(String(index + 1))}
                        </span>
                        <span className="text-[11px] text-muted-foreground truncate max-w-[110px] sm:max-w-[200px]">
                          {getSectionSummary(sec.html)}
                        </span>
                      </div>

                      {/* Action buttons: [🔼 بالا] [🔽 پایین] [➕ الگو] [🗑️ حذف] */}
                      <div className="flex items-center gap-0.5 sm:gap-1 shrink-0">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={index === 0}
                          onClick={() => moveSectionUp(index)}
                          className="h-7 px-1.5 sm:px-2 text-xs text-foreground hover:bg-muted"
                          title="انتقال به بالا"
                        >
                          <ChevronUp className="h-3.5 w-3.5 text-primary" />
                          <span className="hidden sm:inline ms-1">بالا</span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          disabled={index === sections.length - 1}
                          onClick={() => moveSectionDown(index)}
                          className="h-7 px-1.5 sm:px-2 text-xs text-foreground hover:bg-muted"
                          title="انتقال به پایین"
                        >
                          <ChevronDown className="h-3.5 w-3.5 text-primary" />
                          <span className="hidden sm:inline ms-1">پایین</span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => openPaletteAfter(index)}
                          className="h-7 px-1.5 sm:px-2 text-xs text-primary hover:bg-primary/10 font-semibold"
                          title="افزودن الگو بعد از این بخش"
                        >
                          <Plus className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline ms-1">افزودن الگو</span>
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          onClick={() => removeSection(index)}
                          className="h-7 px-1.5 sm:px-2 text-xs text-destructive hover:bg-destructive/10"
                          title="حذف این بخش"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                          <span className="hidden sm:inline ms-1">حذف</span>
                        </Button>
                      </div>
                    </div>
                  )}

                  {/* Section Content (Editable Inline) */}
                  <div
                    ref={(el) => {
                      sectionDomRefs.current[sec.id] = el;
                    }}
                    contentEditable={mode === "edit"}
                    suppressContentEditableWarning
                    onInput={() => setIsDirty(true)}
                    onBlur={(e) => handleSectionBlur(sec.id, e.currentTarget)}
                    dangerouslySetInnerHTML={{ __html: sec.html }}
                    className={cn(
                      "cms-content max-w-none leading-8 text-foreground outline-none",
                      mode === "edit" &&
                        "focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 rounded-xl p-1 transition-all",
                    )}
                  />

                  {/* Inter-section Add button in Edit Mode */}
                  {mode === "edit" && index < sections.length - 1 && (
                    <div
                      contentEditable={false}
                      className="my-3 flex justify-center opacity-0 group-hover/sec:opacity-100 transition-opacity"
                    >
                      <button
                        type="button"
                        onClick={() => openPaletteAfter(index)}
                        className="flex items-center gap-1 rounded-full border border-dashed border-primary/60 bg-background px-3 py-1 text-[11px] font-semibold text-primary shadow-sm hover:bg-primary/10"
                      >
                        <Plus className="h-3 w-3" />
                        درج الگو در اینجا
                      </button>
                    </div>
                  )}
                </section>
              ))}
            </div>
          )}
            </div>
          </EditorCanvasFrame>
        </div>
      </main>

      {/* ── BLOCK PATTERN PALETTE DRAWER ─────────────────────────────────── */}
      <Sheet open={paletteOpen} onOpenChange={setPaletteOpen}>
        <SheetContent side="right" className="w-full sm:max-w-md p-0 flex flex-col" dir="rtl">
          <SheetHeader className="border-b border-border p-4 text-start">
            <SheetTitle className="text-base font-bold flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              کتابخانه الگوهای آماده
            </SheetTitle>
            <SheetDescription className="text-xs">
              یک کلیک روی هر الگو برای درج مستقیم در برگه (
              {insertIndex !== null
                ? `بعد از بخش ${toPersianDigits(String(insertIndex))}`
                : "در انتهای برگه"}
              )
            </SheetDescription>
          </SheetHeader>

          {/* Drawer Search & Category Filters */}
          <div className="border-b border-border/80 p-3 space-y-2.5 bg-muted/20">
            <div className="relative">
              <Search className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                value={paletteSearch}
                onChange={(e) => setPaletteSearch(e.target.value)}
                placeholder="جستجو در الگوها (عنوان، ویژگی، برچسب)…"
                className="ps-9 text-xs h-9"
              />
            </div>

            {/* Category Pills */}
            <div className="flex gap-1.5 overflow-x-auto pb-1 text-xs">
              <button
                type="button"
                onClick={() => setSelectedCategory("all")}
                className={cn(
                  "rounded-full px-2.5 py-1 text-xs font-medium shrink-0 transition-colors",
                  selectedCategory === "all"
                    ? "bg-primary text-primary-foreground font-semibold"
                    : "bg-muted text-muted-foreground hover:bg-muted/80",
                )}
              >
                همه ({toPersianDigits(String(allPatterns.length))})
              </button>
              {categories.map((cat) => (
                <button
                  key={cat}
                  type="button"
                  onClick={() => setSelectedCategory(cat)}
                  className={cn(
                    "rounded-full px-2.5 py-1 text-xs font-medium shrink-0 transition-colors",
                    selectedCategory === cat
                      ? "bg-primary text-primary-foreground font-semibold"
                      : "bg-muted text-muted-foreground hover:bg-muted/80",
                  )}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Patterns Grid */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {loadingPatterns ? (
              <div className="flex flex-col items-center justify-center py-16 gap-3 text-muted-foreground">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
                <span className="text-xs">در حال بارگذاری الگوها…</span>
              </div>
            ) : filteredPatterns.length === 0 ? (
              <div className="text-center py-16 text-muted-foreground text-xs">
                الگویی مطابق جستجوی شما پیدا نشد.
              </div>
            ) : (
              filteredPatterns.map((pattern) => (
                <div
                  key={pattern.slug}
                  onClick={() => void handleInsertPattern(pattern)}
                  className="group relative cursor-pointer rounded-xl border border-border/70 bg-card p-3.5 transition-all hover:border-primary/80 hover:shadow-md"
                >
                  <div className="flex items-start justify-between gap-2 mb-1.5">
                    <h4 className="font-bold text-foreground text-sm group-hover:text-primary transition-colors">
                      {pattern.title}
                    </h4>
                    <Badge variant="secondary" className="text-[10px] shrink-0">
                      {pattern.category}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground line-clamp-2 leading-5">
                    {pattern.description}
                  </p>
                  <div className="mt-3 flex items-center justify-between text-xs">
                    <span className="text-[11px] text-muted-foreground">
                      {toPersianDigits(String(pattern.variables.length))} فیلد
                      قابل‌تنظیم
                    </span>
                    <Button
                      type="button"
                      size="sm"
                      variant="default"
                      disabled={insertingSlug === pattern.slug}
                      className="h-7 text-xs gap-1"
                    >
                      {insertingSlug === pattern.slug ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <Plus className="h-3 w-3" />
                      )}
                      درج در برگه
                    </Button>
                  </div>
                </div>
              ))
            )}
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
