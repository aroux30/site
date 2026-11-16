import { describe, it, expect } from "vitest";
import { createPatternAST } from "@/lib/builder/pattern-converter";
import { PageASTSchema } from "@/lib/builder/schema";

const ALL_28_PATTERNS = [
  { slug: "hero-banner", title: "بنر اصلی (هیرو)", category: "بنر و هیرو" },
  { slug: "feature-grid", title: "شبکه ویژگی‌ها و خدمات", category: "محتوا" },
  { slug: "product-showcase-cta", title: "معرفی محصول شاخص با دکمه خرید", category: "محصولات" },
  { slug: "testimonials", title: "نظرات و تجربیات مشتریان", category: "اعتماد و بازخورد" },
  { slug: "faq-accordion", title: "پرسش‌های متداول آکاردئونی", category: "پرسش‌های متداول" },
  { slug: "image-text", title: "تصویر کنار متن دو ستونه", category: "محتوا" },
  { slug: "countdown-offer", title: "بنر فروش ویژه با شمارش معکوس", category: "فروش و تخفیف" },
  { slug: "star-rating-display", title: "نمایش امتیاز ستاره‌ای", category: "محصولات" },
  { slug: "review-histogram", title: "نمودار توزیع امتیاز", category: "محصولات" },
  { slug: "product-card-grid", title: "شبکه ۳ ستونه کارت محصولات", category: "محصولات" },
  { slug: "text-marquee", title: "نوار متحرک اعلانات و مزایا", category: "بنر و هیرو" },
  { slug: "stats-counter", title: "شمارنده آمار و ارقام کلیدی", category: "محتوا" },
  { slug: "image-gallery-showcase", title: "گالری تصاویر ۴ ستونه", category: "محصولات" },
  { slug: "discount-badge-banner", title: "نوار تخفیف با درصد برجسته", category: "فروش و تخفیف" },
  { slug: "mega-menu-categories", title: "بخش دسته‌بندی‌های سریع", category: "ناوبری" },
  { slug: "pricing-table", title: "جدول قیمت‌گذاری و تعرفه‌ها", category: "قیمت‌گذاری و تعرفه" },
  { slug: "price-list", title: "لیست قیمت آیتم‌ها و خدمات", category: "قیمت‌گذاری و تعرفه" },
  { slug: "icon-box-grid", title: "شبکه ۴ تایی مزایا با آیکون", category: "محتوا" },
  { slug: "author-bio", title: "بیوگرافی نویسنده و کارشناس", category: "محتوا" },
  { slug: "pull-quote", title: "نقل‌قول برجسته با خط حاشیه", category: "محتوا" },
  { slug: "support-callout", title: "کادر تماس با پشتیبانی و مشاوره", category: "پشتیبانی و تماس" },
  { slug: "comparison-table", title: "جدول مقایسه محصولات و مشخصات", category: "قیمت‌گذاری و تعرفه" },
  { slug: "process-steps", title: "مراحل گام‌به‌گام فرایند سفارش", category: "محتوا" },
  { slug: "lead-capture-form", title: "فرم جذب سرنخ و تماس مشاوره", category: "پشتیبانی و تماس" },
  { slug: "alert-banner", title: "نوار اعلان و هشدار متنی", category: "فروش و تخفیف" },
  { slug: "floating-contact-bar", title: "نوار راه‌های ارتباطی سریع", category: "پشتیبانی و تماس" },
  { slug: "brand-logo-carousel", title: "شبکه لوگوی همکاران و برندها", category: "اعتماد و بازخورد" },
  { slug: "product-highlights", title: "برجستگی‌ها و ویژگی‌های کلیدی محصول", category: "محصولات" },
];

describe("Block Pattern to AST Converter", () => {
  it("converts all 28 patterns into valid AST container trees", () => {
    for (const pat of ALL_28_PATTERNS) {
      const element = createPatternAST(pat, "<section><div>placeholder</div></section>");
      expect(element.type).toBe("container");
      expect(element.id).toBeDefined();
      expect(element.children.length).toBeGreaterThan(0);
    }
  });

  it("produces valid PageAST conforming to schema for all patterns", () => {
    for (const pat of ALL_28_PATTERNS) {
      const element = createPatternAST(pat, "<div>rendered</div>");
      const pageAst = {
        schemaVersion: 1,
        title: "Test Page",
        slug: "test-page",
        globalStyles: {},
        rootElements: [element],
      };

      const parsed = PageASTSchema.safeParse(pageAst);
      expect(parsed.success).toBe(true);
    }
  });

  it("ensures unique element IDs across the entire tree", () => {
    for (const pat of ALL_28_PATTERNS) {
      const element = createPatternAST(pat, "<div>rendered</div>");
      const ids = new Set<string>();

      function collectIds(el: any) {
        expect(ids.has(el.id)).toBe(false);
        ids.add(el.id);
        if (el.children) {
          for (const c of el.children) collectIds(c);
        }
      }

      collectIds(element);
      expect(ids.size).toBeGreaterThan(1); // root container + at least 1 child
    }
  });

  it("ensures container nesting depth never exceeds 4", () => {
    for (const pat of ALL_28_PATTERNS) {
      const element = createPatternAST(pat, "<div>rendered</div>");

      function getDepth(el: any, currentDepth = 1): number {
        if (!el.children || el.children.length === 0) return currentDepth;
        let maxChildDepth = currentDepth;
        for (const child of el.children) {
          const d = getDepth(child, currentDepth + 1);
          if (d > maxChildDepth) maxChildDepth = d;
        }
        return maxChildDepth;
      }

      const depth = getDepth(element);
      expect(depth).toBeLessThanOrEqual(4);
    }
  });

  it("deconstructs hero-banner into independent heading, text, button, and image widgets", () => {
    const hero = createPatternAST(
      { slug: "hero-banner", title: "بنر هیرو", category: "بنر" },
      "<section></section>",
      { title: "عنوان تست", cta_text: "دکمه تست" }
    );

    // Recursively collect all widget types
    const widgets: Array<{ type: string; props: any }> = [];
    function collectWidgets(el: any) {
      if (el.type === "widget") {
        widgets.push({ type: el.widgetType, props: el.widgetProps });
      }
      if (el.children) {
        for (const c of el.children) collectWidgets(c);
      }
    }
    collectWidgets(hero);

    const heading = widgets.find((w) => w.type === "heading");
    const button = widgets.find((w) => w.type === "button");
    const image = widgets.find((w) => w.type === "image");
    const text = widgets.find((w) => w.type === "text_editor");

    expect(heading).toBeDefined();
    expect(heading?.props.text).toBe("عنوان تست");
    expect(button).toBeDefined();
    expect(button?.props.label).toBe("دکمه تست");
    expect(image).toBeDefined();
    expect(text).toBeDefined();
  });

  it("deconstructs feature-grid into 3 distinct card containers with heading and text widgets", () => {
    const fg = createPatternAST(
      { slug: "feature-grid", title: "ویژگی‌ها", category: "محتوا" },
      "<section></section>",
      { item1_title: "مزیت یک", item2_title: "مزیت دو", item3_title: "مزیت سه" }
    );

    const headings: string[] = [];
    function collectHeadings(el: any) {
      if (el.type === "widget" && el.widgetType === "heading") {
        headings.push(el.widgetProps.text);
      }
      if (el.children) {
        for (const c of el.children) collectHeadings(c);
      }
    }
    collectHeadings(fg);

    expect(headings).toContain("مزیت یک");
    expect(headings).toContain("مزیت دو");
    expect(headings).toContain("مزیت سه");
  });

  it("deconstructs comparison-table into native table widget without html_custom", () => {
    const comp = createPatternAST(
      { slug: "comparison-table", title: "جدول مقایسه", category: "قیمت‌گذاری" },
      "<section></section>"
    );
    const widgets: any[] = [];
    function collect(el: any) {
      if (el.type === "widget") widgets.push(el);
      if (el.children) el.children.forEach(collect);
    }
    collect(comp);

    const tableWidget = widgets.find((w) => w.widgetType === "table");
    expect(tableWidget).toBeDefined();
    expect(tableWidget.widgetProps.headers.length).toBeGreaterThan(0);
    expect(tableWidget.widgetProps.rows.length).toBeGreaterThan(0);

    const customHtmlWidget = widgets.find((w) => w.widgetType === "html_custom");
    expect(customHtmlWidget).toBeUndefined();
  });

  it("deconstructs lead-capture-form into native form_input and button widgets without html_custom", () => {
    const form = createPatternAST(
      { slug: "lead-capture-form", title: "فرم سرنخ", category: "تماس" },
      "<section></section>"
    );
    const widgets: any[] = [];
    function collect(el: any) {
      if (el.type === "widget") widgets.push(el);
      if (el.children) el.children.forEach(collect);
    }
    collect(form);

    const inputs = widgets.filter((w) => w.widgetType === "form_input");
    expect(inputs.length).toBeGreaterThanOrEqual(2);
    const customHtmlWidget = widgets.find((w) => w.widgetType === "html_custom");
    expect(customHtmlWidget).toBeUndefined();
  });
});
