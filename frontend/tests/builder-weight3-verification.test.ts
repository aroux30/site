import { describe, it, expect } from "vitest";
import { useBuilderStore } from "@/stores/builder-store";
import { DEFAULT_THEME_TOKENS } from "@/lib/builder/theme-schema";
import { createPatternAST } from "@/lib/builder/pattern-converter";

describe("Weight 3: Block Patterns, Palette Tabs & Global Styles Dialog", () => {
  it("manages global styles design tokens and resets to site theme", () => {
    const store = useBuilderStore.getState();
    store.initPage("w3-test", null, "تست استایل سراسری", "w3-test");

    // 1. Update Global Tokens
    store.updateGlobalStyles({
      primaryColor: "#2563eb",
      secondaryColor: "#7c3aed",
      borderRadius: "16px",
      fontFamily: "system-ui",
      textColor: "#1e293b",
      backgroundColor: "#f8fafc",
    });

    let currentGs = useBuilderStore.getState().ast.globalStyles;
    expect(currentGs?.primaryColor).toBe("#2563eb");
    expect(currentGs?.secondaryColor).toBe("#7c3aed");
    expect(currentGs?.borderRadius).toBe("16px");
    expect(currentGs?.fontFamily).toBe("system-ui");

    // 2. Reset to Site Theme
    store.updateGlobalStyles({
      primaryColor: undefined,
      secondaryColor: undefined,
      borderRadius: undefined,
      fontFamily: undefined,
      textColor: undefined,
      backgroundColor: undefined,
    });

    currentGs = useBuilderStore.getState().ast.globalStyles;
    expect(currentGs?.primaryColor).toBeUndefined();
    expect(currentGs?.secondaryColor).toBeUndefined();
    expect(currentGs?.borderRadius).toBeUndefined();
  });

  it("verifies default theme token schema values", () => {
    expect(DEFAULT_THEME_TOKENS.primitive).toBeDefined();
    expect(DEFAULT_THEME_TOKENS.primitive.color?.emerald?.[500]?.$value).toBe("#10b981");
    expect(DEFAULT_THEME_TOKENS.primitive.dimension?.radius?.lg?.$value).toBe("14px");
  });

  it("converts lead-capture-form pattern into a specialized form_container with submit_url", () => {
    const pattern = {
      slug: "lead-capture-form",
      title: "فرم دریافت سرنخ",
      category: "تعاملی",
    };
    const ast = createPatternAST(pattern, "<section></section>");

    expect(ast.type).toBe("container");
    expect(ast.widgetType).toBe("form_container");
    expect(ast.widgetProps?.submit_url).toBe("/api/forms/submit");
    expect(ast.children.length).toBeGreaterThan(0);
  });

  it("converts comparison-table pattern with valid table widget", () => {
    const pattern = {
      slug: "comparison-table",
      title: "جدول مقایسه",
      category: "محتوا",
    };
    const ast = createPatternAST(pattern, "<section></section>");

    expect(ast.type).toBe("container");
    const tableEl = ast.children.find((c) => c.widgetType === "table");
    expect(tableEl).toBeDefined();
    expect((tableEl?.widgetProps as any)?.headers?.length).toBe(3);
    expect((tableEl?.widgetProps as any)?.rows?.length).toBe(4);
  });

  it("converts all 28 block patterns into valid AST without exceptions", () => {
    const slugs = [
      "hero-banner",
      "feature-grid",
      "product-showcase-cta",
      "testimonials",
      "faq-accordion",
      "image-text",
      "countdown-offer",
      "star-rating-display",
      "review-histogram",
      "product-card-grid",
      "text-marquee",
      "stats-counter",
      "image-gallery-showcase",
      "discount-badge-banner",
      "mega-menu-categories",
      "pricing-table",
      "price-list",
      "icon-box-grid",
      "author-bio",
      "pull-quote",
      "support-callout",
      "comparison-table",
      "process-steps",
      "lead-capture-form",
      "alert-banner",
      "floating-contact-bar",
      "brand-logo-carousel",
      "product-highlights",
    ];

    expect(slugs.length).toBe(28);

    for (const slug of slugs) {
      const pattern = {
        slug,
        title: `الگوی تست ${slug}`,
        category: "عمومی",
      };
      const ast = createPatternAST(pattern, "<section></section>");
      expect(ast.id).toBeDefined();
      expect(ast.type).toBe("container");
      expect(ast.children.length).toBeGreaterThan(0);
    }
  });

  it("filters patterns with multi-token queries and safe keyword spreads", () => {
    const mockPatterns = [
      { slug: "p1", title: "کالکشن جدید لباس", description: "لباس‌های تابستانی", category: "فروشگاهی", keywords: ["تخفیف", "فروش"] },
      { slug: "p2", title: "فرم تماس و مشاوره", description: "ارتباط با ما", category: "تعاملی", keywords: undefined as any },
    ];

    function filterMock(patterns: typeof mockPatterns, query: string, cat: string) {
      const q = query.trim().toLowerCase();
      const tokens = q.split(/\s+/).filter(Boolean);
      return patterns.filter((p) => {
        const matchCat = cat === "all" || p.category === cat;
        if (!matchCat) return false;
        if (tokens.length === 0) return true;
        const haystack = [p.title, p.description, p.category, ...(p.keywords || [])].join(" ").toLowerCase();
        return tokens.every((tok) => haystack.includes(tok));
      });
    }

    // 1. Multi-token match across title and description
    const res1 = filterMock(mockPatterns, "کالکشن تابستانی", "all");
    expect(res1.length).toBe(1);
    expect(res1[0]?.slug).toBe("p1");

    // 2. Safe with undefined keywords
    const res2 = filterMock(mockPatterns, "مشاوره ارتباط", "all");
    expect(res2.length).toBe(1);
    expect(res2[0]?.slug).toBe("p2");
  });
});

