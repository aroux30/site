import { describe, it, expect } from "vitest";
import {
  PageASTSchema,
  validateUniqueElementIds,
  validateTreeTopology,
  resolveResponsiveValue,
  BuilderValidationError,
} from "@/lib/builder/schema";
import type { PageAST, BuilderElement } from "@/types/builder";

describe("Visual Page Builder Zod Schema and AST Validation (Phase P0)", () => {
  const validAst: PageAST = {
    schemaVersion: 1,
    title: "برگه آزمایشی",
    slug: "test-builder-page",
    globalStyles: { contentMaxWidth: "1280px" },
    rootElements: [
      {
        id: "el_sec01",
        name: "بخش هیرو",
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "flex",
          direction: "column",
          justifyContent: "center",
          alignItems: "center",
          flexWrap: "nowrap",
          gap: { value: 24, unit: "px" },
          gridColumns: 3,
        },
        styles: {
          mobile: {
            padding: {
              top: { value: 16, unit: "px" },
              right: { value: 16, unit: "px" },
              bottom: { value: 16, unit: "px" },
              left: { value: 16, unit: "px" },
              isLinked: true,
            },
          },
          tablet: {
            padding: {
              top: { value: 24, unit: "px" },
              right: { value: 24, unit: "px" },
              bottom: { value: 24, unit: "px" },
              left: { value: 24, unit: "px" },
              isLinked: true,
            },
          },
          desktop: {
            padding: {
              top: { value: 40, unit: "px" },
              right: { value: 40, unit: "px" },
              bottom: { value: 40, unit: "px" },
              left: { value: 40, unit: "px" },
              isLinked: true,
            },
          },
        },
        children: [
          {
            id: "el_heading01",
            name: "سرتیتر اصلی",
            type: "widget",
            widgetType: "heading",
            widgetProps: { text: "فروشگاه آنلاین", tag: "h1" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
          {
            id: "el_btn01",
            name: "دکمه خرید",
            type: "widget",
            widgetType: "add_to_cart",
            widgetProps: { label: "افزودن به سبد", variantId: "var-123" },
            isLocked: false,
            isHidden: false,
            styles: { mobile: {} },
            children: [],
          },
        ],
      },
    ],
  };

  it("successfully parses and validates a valid PageAST document", () => {
    const parsed = PageASTSchema.parse(validAst);
    expect(parsed.title).toBe("برگه آزمایشی");
    expect(parsed.rootElements).toHaveLength(1);
    expect(parsed.rootElements[0]!.children).toHaveLength(2);
  });

  it("detects and throws on duplicate element IDs", () => {
    const rootEl = validAst.rootElements[0]!;
    const invalidAst: PageAST = {
      ...validAst,
      rootElements: [
        {
          ...rootEl,
          children: [
            ...rootEl.children,
            {
              id: "el_heading01", // Duplicate ID
              name: "عنوان تکراری",
              type: "widget",
              widgetType: "heading",
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
      ],
    };

    expect(() => validateUniqueElementIds(invalidAst)).toThrow(
      BuilderValidationError
    );
    expect(() => validateUniqueElementIds(invalidAst)).toThrow(
      "Duplicate element ID: 'el_heading01'"
    );
  });

  it("detects and throws on circular reference in element tree", () => {
    const rootNode: BuilderElement = {
      id: "el_rootNode",
      name: "ریشه",
      type: "container",
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    const childNode: BuilderElement = {
      id: "el_childNode",
      name: "فرزند",
      type: "container",
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [rootNode], // cycle
    };

    rootNode.children = [childNode];

    const cyclicAst: PageAST = {
      schemaVersion: 1,
      title: "تست حلقه",
      slug: "test-cycle",
      rootElements: [rootNode],
    };

    expect(() => validateTreeTopology(cyclicAst)).toThrow(
      BuilderValidationError
    );
    expect(() => validateTreeTopology(cyclicAst)).toThrow(
      "Circular reference detected"
    );
  });

  it("enforces maximum nesting depth limit of 5", () => {
    let deepNode: BuilderElement = {
      id: "el_deep07",
      name: "عمق ۷",
      type: "widget",
      widgetType: "heading",
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    for (let depth = 6; depth >= 1; depth--) {
      deepNode = {
        id: `el_cont0${depth}`,
        name: `کانتینر ${depth}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        styles: { mobile: {} },
        children: [deepNode],
      };
    }

    const deepAst: PageAST = {
      schemaVersion: 1,
      title: "تست عمق",
      slug: "test-depth",
      rootElements: [deepNode],
    };

    expect(() => validateTreeTopology(deepAst, 5)).toThrow(
      BuilderValidationError
    );
    expect(() => validateTreeTopology(deepAst, 5)).toThrow(
      "Max nesting depth of 5 exceeded"
    );
  });

  it("prohibits widgets from containing child elements", () => {
    const widgetWithChild: PageAST = {
      schemaVersion: 1,
      title: "ویجت با فرزند",
      slug: "widget-child",
      rootElements: [
        {
          id: "el_wParent",
          name: "ویجت والد",
          type: "widget",
          widgetType: "heading",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [
            {
              id: "el_wChild",
              name: "فرزند نامجاز",
              type: "widget",
              widgetType: "button",
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
      ],
    };

    expect(() => validateTreeTopology(widgetWithChild)).toThrow(
      BuilderValidationError
    );
    expect(() => validateTreeTopology(widgetWithChild)).toThrow(
      "cannot have child elements"
    );
  });

  it("correctly executes Mobile-First responsive resolution cascade", () => {
    // Case 1: only mobile is defined -> mobile applies everywhere
    expect(
      resolveResponsiveValue({ mobile: "16px" }, "mobile")
    ).toBe("16px");
    expect(
      resolveResponsiveValue({ mobile: "16px" }, "tablet")
    ).toBe("16px");
    expect(
      resolveResponsiveValue({ mobile: "16px" }, "desktop")
    ).toBe("16px");

    // Case 2: mobile + tablet override -> desktop inherits tablet
    expect(
      resolveResponsiveValue({ mobile: "16px", tablet: "24px" }, "mobile")
    ).toBe("16px");
    expect(
      resolveResponsiveValue({ mobile: "16px", tablet: "24px" }, "tablet")
    ).toBe("24px");
    expect(
      resolveResponsiveValue({ mobile: "16px", tablet: "24px" }, "desktop")
    ).toBe("24px");

    // Case 3: mobile + tablet + desktop overrides
    const fullValues = { mobile: "16px", tablet: "24px", desktop: "40px" };
    expect(resolveResponsiveValue(fullValues, "mobile")).toBe("16px");
    expect(resolveResponsiveValue(fullValues, "tablet")).toBe("24px");
    expect(resolveResponsiveValue(fullValues, "desktop")).toBe("40px");
  });

  it("validates Elementor Wave 1 transform and mask schema attributes", () => {
    const elementWithTransform: BuilderElement = {
      id: "el_tf_test",
      name: "عنصر تبدیل",
      type: "widget",
      widgetType: "heading",
      widgetProps: { text: "تست" },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          transform: {
            rotate: 45,
            scale: 1.2,
            skewX: 10,
            skewY: 5,
            translateX: 20,
            translateY: -10,
            flipX: true,
            flipY: false,
          },
          typography: {
            textShadow: "0 2px 4px rgba(0,0,0,0.5)",
          },
          mask: {
            shape: "flower",
            size: "contain",
            position: "center",
            repeat: "no-repeat",
          },
        },
      },
      children: [],
    };

    const astWithTransform: PageAST = {
      schemaVersion: 1,
      title: "تست ترنسفورم",
      slug: "test-tf",
      rootElements: [elementWithTransform],
    };

    const parsed = PageASTSchema.safeParse(astWithTransform);
    expect(parsed.success).toBe(true);
    if (parsed.success && parsed.data.rootElements[0]) {
      const el = parsed.data.rootElements[0];
      expect(el.styles.mobile.transform?.rotate).toBe(45);
      expect(el.styles.mobile.transform?.scale).toBe(1.2);
      expect(el.styles.mobile.transform?.flipX).toBe(true);
      expect(el.styles.mobile.mask?.shape).toBe("flower");
      expect(el.styles.mobile.typography?.textShadow).toBe("0 2px 4px rgba(0,0,0,0.5)");
    }
  });

  it("validates Elementor Grid Container with gridAutoFlow", () => {
    const gridContainer: BuilderElement = {
      id: "cont_grid_test",
      name: "کانتینر شبکه",
      type: "container",
      layout: {
        kind: "grid",
        direction: "row",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 20, unit: "px" },
        gridColumns: 4,
        gridAutoFlow: "row dense",
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "تست گرید",
      slug: "test-grid",
      rootElements: [gridContainer],
    });

    expect(parsed.success).toBe(true);
    if (parsed.success && parsed.data.rootElements[0]) {
      const el = parsed.data.rootElements[0];
      expect(el.layout?.kind).toBe("grid");
      expect(el.layout?.gridColumns).toBe(4);
      expect(el.layout?.gridAutoFlow).toBe("row dense");
    }
  });

  it("validates Elementor Table of Contents and Icon widget schema parity", () => {
    const tocElement: BuilderElement = {
      id: "el_toc_unit",
      name: "فهرست مطالب",
      type: "widget",
      widgetType: "table_of_contents",
      widgetProps: {
        title: "فهرست راهنما",
        ordered: true,
        items: [
          { text: "فصل اول", anchor: "#ch1" },
          { text: "فصل دوم", anchor: "#ch2" },
        ],
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    const iconElement: BuilderElement = {
      id: "el_icon_unit",
      name: "آیکون ویژه",
      type: "widget",
      widgetType: "icon",
      widgetProps: {
        icon: "shield-check",
        view: "stacked",
        shape: "circle",
        size: 48,
        rotate: 15,
        url: "https://example.com",
        newTab: true,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "تست ویجت‌های المنتور",
      slug: "test-elementor-widgets",
      rootElements: [tocElement, iconElement],
    });

    expect(parsed.success).toBe(true);
    if (parsed.success) {
      const toc = parsed.data.rootElements[0];
      const ic = parsed.data.rootElements[1];
      expect(toc?.widgetProps?.title).toBe("فهرست راهنما");
      expect(toc?.widgetProps?.ordered).toBe(true);
      expect(ic?.widgetProps?.icon).toBe("shield-check");
      expect(ic?.widgetProps?.view).toBe("stacked");
      expect(ic?.widgetProps?.size).toBe(48);
    }
  });

  it("validates Elementor Nav Menu schema structure in AST", () => {
    const navMenuElement: BuilderElement = {
      id: "el_nav_unit",
      name: "منوی اصلی",
      type: "widget",
      widgetType: "nav_menu",
      widgetProps: {
        layout: "horizontal",
        align: "center",
        items: [
          { title: "صفحه اصلی", url: "/" },
          { title: "فروشگاه", url: "/products" },
          { title: "تماس", url: "/contact" },
        ],
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "تست منوی ناوبری",
      slug: "test-nav-menu",
      rootElements: [navMenuElement],
    });

    expect(parsed.success).toBe(true);
    if (parsed.success && parsed.data.rootElements[0]) {
      const el = parsed.data.rootElements[0];
      expect(el.widgetType).toBe("nav_menu");
      expect(el.widgetProps?.layout).toBe("horizontal");
      expect(Array.isArray(el.widgetProps?.items)).toBe(true);
      expect((el.widgetProps?.items as any[]).length).toBe(3);
    }
  });

  it("validates Elementor Pro Custom Attributes supporting both string and dictionary forms in schema", () => {
    const elWithStringAttrs: BuilderElement = {
      id: "el_attr_str",
      name: "المان با رشته",
      type: "widget",
      widgetType: "heading",
      widgetProps: { text: "ویژگی رشته‌ای" },
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {},
        customAttributes: "data-tracking|hero-cta\naria-label|test-region",
      },
      children: [],
    };

    const elWithDictAttrs: BuilderElement = {
      id: "el_attr_dict",
      name: "المان با دیکشنری",
      type: "container",
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {},
        customAttributes: { "data-role": "modal-trigger", "data-e2e": "submit-button" },
      },
      children: [],
    };

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "تست ویژگی‌های سفارشی",
      slug: "test-custom-attrs",
      rootElements: [elWithStringAttrs, elWithDictAttrs],
    });

    expect(parsed.success).toBe(true);
    if (parsed.success && parsed.data.rootElements[0] && parsed.data.rootElements[1]) {
      expect(parsed.data.rootElements[0].styles.customAttributes).toBe(
        "data-tracking|hero-cta\naria-label|test-region"
      );
      expect(typeof parsed.data.rootElements[1].styles.customAttributes).toBe("object");
    }
  });
});
