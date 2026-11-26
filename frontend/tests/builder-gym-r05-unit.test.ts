import { describe, it, expect } from "vitest";
import { BASIC_BLOCK_DEFINITIONS, createPatternElement } from "@/lib/builder/block-registry";
import { cleanBuilderHtml } from "@/lib/sanitize-html";
import { useBuilderStore } from "@/stores/builder-store";

const ALL_28_SLUGS = [
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

describe("Builder Gym Round 05 Regression (Extra5, Patterns & Global Styles)", () => {
  it("registers extra5 widgets including product_title and nav_menu default layout", () => {
    const prodTitle = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "product_title");
    const navMenu = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "nav_menu");
    const codeHl = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "code_highlight");
    const crumbs = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "breadcrumbs");
    const searchBar = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "search_bar");

    expect(prodTitle).toBeDefined();
    expect(navMenu).toBeDefined();
    expect(codeHl).toBeDefined();
    expect(crumbs).toBeDefined();
    expect(searchBar).toBeDefined();

    expect((navMenu!.createDefaultElement().widgetProps as any)?.layout).toBe("horizontal");
    expect((prodTitle!.createDefaultElement().widgetProps as any)?.fallback_title).toBe("عنوان محصول");
  });

  it("converts all 28 patterns with zero broken placeholder assets and clean hero/histogram/category structures", () => {
    expect(ALL_28_SLUGS).toHaveLength(28);
    for (const slug of ALL_28_SLUGS) {
      const node = createPatternElement({ slug, title: slug, category: "عمومی" }, `<section>${slug}</section>`);
      const serialized = JSON.stringify(node);
      expect(serialized).not.toContain("/placeholder-avatar.svg");
      expect(serialized).not.toContain('"/placeholder.svg"');
      expect(node.children.length).toBeGreaterThan(0);
    }

    const hero = createPatternElement({ slug: "hero-banner", title: "هیرو", category: "هیرو" }, "");
    const heroJson = JSON.stringify(hero);
    expect(heroJson).toContain("text-primary-foreground");
    expect(heroJson).toContain("bg-primary-foreground px-6 py-3 font-semibold text-primary");

    const hist = createPatternElement({ slug: "review-histogram", title: "نمودار", category: "محصولات" }, "");
    const barsGroup = hist.children.find((c) => c.type === "container");
    expect(barsGroup?.children.length).toBe(5);
    expect(barsGroup?.children.every((c) => c.widgetType === "progress_bar")).toBe(true);

    const mega = createPatternElement({ slug: "mega-menu-categories", title: "دسته‌ها", category: "ناوبری" }, "");
    expect(JSON.stringify(mega)).toContain("whitespace-normal");
  });

  it("filters empty/undefined global style tokens cleanly and preserves SSR CSS variable styles in cleanBuilderHtml", () => {
    const store = useBuilderStore.getState();
    store.initPage("r05-gs", null, "R05", "r05");
    store.updateGlobalStyles({
      primaryColor: "#dc2626",
      secondaryColor: "#0284c7",
      backgroundColor: "#fefce8",
      textColor: "#1e293b",
      borderRadius: "16px",
      fontFamily: "system-ui",
    });
    expect(useBuilderStore.getState().ast.globalStyles?.primaryColor).toBe("#dc2626");

    store.updateGlobalStyles({
      primaryColor: undefined,
      backgroundColor: undefined,
    });
    expect("primaryColor" in (useBuilderStore.getState().ast.globalStyles || {})).toBe(false);
    expect(useBuilderStore.getState().ast.globalStyles?.secondaryColor).toBe("#0284c7");

    const sampleSsr =
      '<div class="builder-document" dir="rtl" style="background-color: #fefce8; color: #1e293b;">' +
      '<style data-builder-responsive="1">.builder-document { --primary: 0 72% 51%; --primary-hex: #dc2626; --secondary: 199 98% 39%; }</style>' +
      '<pre><code>fetch(\'/api/v1/products\')</code></pre></div>';
    const cleaned = cleanBuilderHtml(sampleSsr);
    expect(cleaned).toContain("--primary: 0 72% 51%");
    expect(cleaned).toContain("--primary-hex: #dc2626");
    expect(cleaned).not.toContain("&amp;#x27;");
  });
});
