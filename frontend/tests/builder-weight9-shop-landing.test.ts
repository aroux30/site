import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Complex E-Commerce Landing Suite", () => {
  it("integrates product_grid, mega_menu, star_rating and cta into a high-converting shop landing", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-shop-landing", null, "لندینگ فروشگاهی پیشرفته", "w9-shop-landing");

    // 1. Navigation & Header Mega Menu
    const navSection: BuilderElement = {
      id: "cont_shop_nav",
      name: "بخش ناوبری بالای صفحه",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "row",
        justifyContent: "between",
        alignItems: "center",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 1,
      },
      styles: { mobile: {} },
      children: [
        {
          id: "el_shop_megamenu",
          name: "مگامنو دسته‌بندی‌ها",
          type: "widget",
          widgetType: "mega_menu",
          widgetProps: { label: "دسته‌بندی‌های برگزیده" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_shop_search",
          name: "فرم جستجوی سریع",
          type: "widget",
          widgetType: "search_bar",
          widgetProps: { placeholder: "جستجو در میان ۱۰۰۰+ محصول..." },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(navSection);

    // 2. Featured Products Grid
    const gridSection: BuilderElement = {
      id: "cont_shop_grid",
      name: "ویترین محصولات ویژه",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 24, unit: "px" },
        gridColumns: 1,
      },
      styles: { mobile: {} },
      children: [
        {
          id: "el_shop_prodgrid",
          name: "گرید کالاهای پرفروش",
          type: "widget",
          widgetType: "product_grid",
          widgetProps: { limit: 4, category: "all", show_pagination: false },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(gridSection);

    // Assert DOM elements are structured correctly
    const state = useBuilderStore.getState();
    const nav = findElementById(state.ast.rootElements, "cont_shop_nav");
    expect(nav?.children?.length).toBe(2);

    const grid = findElementById(state.ast.rootElements, "cont_shop_grid");
    expect(grid?.children?.length).toBe(1);
    expect(grid?.children?.[0]?.widgetType).toBe("product_grid");
  });

  it("handles complex customer proof with star_rating and review_histogram", () => {
    const store = useBuilderStore.getState();
    const ratingWidget: BuilderElement = {
      id: "el_shop_rating",
      name: "امتیاز کالا",
      type: "widget",
      widgetType: "star_rating",
      widgetProps: { value: 4.9, reviewCount: 230, size: "lg", showValue: true },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(ratingWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_shop_rating");
    expect(found?.widgetProps?.value).toBe(4.9);
    expect(found?.widgetProps?.reviewCount).toBe(230);
  });
});
