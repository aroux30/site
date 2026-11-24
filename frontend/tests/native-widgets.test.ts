import { describe, it, expect } from "vitest";
import { BASIC_BLOCK_DEFINITIONS } from "@/lib/builder/block-registry";
import { PageASTSchema } from "@/lib/builder/schema";

describe("P2.1 Native Widgets: Table & Form Inputs", () => {
  it("registers table widget in BASIC_BLOCK_DEFINITIONS", () => {
    const tableDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "table");
    expect(tableDef).toBeDefined();
    expect(tableDef?.name).toContain("جدول");

    const element = tableDef!.createDefaultElement();
    expect(element.type).toBe("widget");
    expect(element.widgetType).toBe("table");
    expect(element.widgetProps?.headers).toBeInstanceOf(Array);
    expect(element.widgetProps?.rows).toBeInstanceOf(Array);
  });

  it("registers form_input, form_textarea, and form_select in BASIC_BLOCK_DEFINITIONS", () => {
    const formInput = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_input");
    const formTextarea = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_textarea");
    const formSelect = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_select");

    expect(formInput).toBeDefined();
    expect(formTextarea).toBeDefined();
    expect(formSelect).toBeDefined();

    const inputEl = formInput!.createDefaultElement();
    expect(inputEl.widgetType).toBe("form_input");
    expect(inputEl.widgetProps?.label).toBeDefined();
    expect(inputEl.widgetProps?.name).toBeDefined();

    const textareaEl = formTextarea!.createDefaultElement();
    expect(textareaEl.widgetType).toBe("form_textarea");
    expect(textareaEl.widgetProps?.rows).toBe(4);

    const selectEl = formSelect!.createDefaultElement();
    expect(selectEl.widgetType).toBe("form_select");
    expect(selectEl.widgetProps?.options).toBeInstanceOf(Array);
  });

  it("ensures native table and form widgets conform to PageASTSchema", () => {
    const tableEl = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "table")!.createDefaultElement();
    const inputEl = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "form_input")!.createDefaultElement();

    const ast = {
      schemaVersion: 1,
      title: "Test AST",
      slug: "test-ast",
      globalStyles: {},
      rootElements: [
        {
          id: "el_container",
          name: "کانتینر",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [tableEl, inputEl],
        },
      ],
    };

    const parsed = PageASTSchema.safeParse(ast);
    expect(parsed.success).toBe(true);
  });

  it("registers icon, icon_list, price_table and price_list widgets with valid schema conformity", () => {
    const iconDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "icon");
    const iconListDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "icon_list");
    const priceTableDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "price_table");
    const priceListDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "price_list");

    expect(iconDef).toBeDefined();
    expect(iconListDef).toBeDefined();
    expect(priceTableDef).toBeDefined();
    expect(priceListDef).toBeDefined();

    const iconEl = iconDef!.createDefaultElement();
    const iconListEl = iconListDef!.createDefaultElement();
    const priceTableEl = priceTableDef!.createDefaultElement();
    const priceListEl = priceListDef!.createDefaultElement();

    expect(iconEl.widgetType).toBe("icon");
    expect(iconEl.widgetProps?.icon).toBe("star");

    expect(iconListEl.widgetType).toBe("icon_list");
    expect(Array.isArray(iconListEl.widgetProps?.items)).toBe(true);

    expect(priceTableEl.widgetType).toBe("price_table");
    expect(priceTableEl.widgetProps?.price).toBe("۴۹۰,۰۰۰");
    expect(Array.isArray(priceTableEl.widgetProps?.features)).toBe(true);

    // Verify string and object features support
    const stringFeatureTable = {
      ...priceTableEl,
      widgetProps: {
        ...priceTableEl.widgetProps,
        features: ["ویژگی اول متنی", { text: "ویژگی دوم شیء", available: false }],
        transitionDuration: 0.3,
      },
    };

    expect(priceListEl.widgetType).toBe("price_list");
    expect(Array.isArray(priceListEl.widgetProps?.items)).toBe(true);

    const ast = {
      schemaVersion: 1,
      title: "Elementor Parity AST",
      slug: "elementor-parity-ast",
      globalStyles: {},
      rootElements: [
        {
          id: "el_root",
          name: "ریشه",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [iconEl, iconListEl, stringFeatureTable, priceListEl],
        },
      ],
    };

    const parsed = PageASTSchema.safeParse(ast);
    expect(parsed.success).toBe(true);
  });

  it("registers and validates floating_bar widget in block registry and AST", () => {
    const floatingBarDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "floating_bar");
    expect(floatingBarDef).toBeDefined();

    const element = floatingBarDef!.createDefaultElement();
    expect(["floating_bar", "floating_buttons"]).toContain(element.widgetType);
    expect(element.widgetProps?.phone).toBeDefined();
    expect(element.widgetProps?.message).toBeDefined();

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "Floating Bar AST",
      slug: "floating-bar-ast",
      rootElements: [element],
    });
    expect(parsed.success).toBe(true);
  });

  it("registers and validates breadcrumbs, search_bar and nav_menu widgets in block registry and AST", () => {
    const breadcrumbsDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "breadcrumbs");
    const searchBarDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "search_bar");
    const navMenuDef = BASIC_BLOCK_DEFINITIONS.find((b) => b.type === "nav_menu");

    expect(breadcrumbsDef).toBeDefined();
    expect(searchBarDef).toBeDefined();
    expect(navMenuDef).toBeDefined();

    const breadcrumbsEl = breadcrumbsDef!.createDefaultElement();
    const searchBarEl = searchBarDef!.createDefaultElement();
    const navMenuEl = navMenuDef!.createDefaultElement();

    expect(breadcrumbsEl.widgetType).toBe("breadcrumbs");
    expect(breadcrumbsEl.widgetProps?.separator).toBe("/");
    expect(Array.isArray(breadcrumbsEl.widgetProps?.items)).toBe(true);

    expect(searchBarEl.widgetType).toBe("search_bar");
    expect(searchBarEl.widgetProps?.placeholder).toBeDefined();

    expect(navMenuEl.widgetType).toBe("nav_menu");
    expect(Array.isArray(navMenuEl.widgetProps?.items)).toBe(true);
    expect((navMenuEl.widgetProps?.items as any[])?.length).toBeGreaterThan(0);

    const verticalNavMenuEl = {
      ...navMenuEl,
      widgetProps: {
        ...navMenuEl.widgetProps,
        layout: "vertical",
      },
    };

    const parsed = PageASTSchema.safeParse({
      schemaVersion: 1,
      title: "Theme Builder AST",
      slug: "theme-builder-ast",
      rootElements: [breadcrumbsEl, searchBarEl, navMenuEl, verticalNavMenuEl],
    });
    expect(parsed.success).toBe(true);
  });
});
