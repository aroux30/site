import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Nested Tabs, Nested Accordion & Container Presets", () => {
  it("renders nested_tabs container and handles tab switching with nested children", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-nested-test", null, "تست کانتینرهای تودرتو", "w9-nested-test");

    const nestedTabsContainer: BuilderElement = {
      id: "cont_nested_tabs",
      name: "تب‌های تودرتو کانتینری",
      type: "container",
      widgetType: "nested_tabs",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        active_tab: 0,
        tab_titles: ["بررسی تخصصی", "مشخصات فنی", "نظرات کاربران"],
      },
      styles: { mobile: {} },
      children: [
        {
          id: "cont_tab_pane_1",
          name: "محتوای تب اول",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [
            {
              id: "el_tab1_h2",
              name: "تیتر تب ۱",
              type: "widget",
              widgetType: "heading",
              widgetProps: { text: "بررسی عمیق سخت‌افزار" },
              isLocked: false,
              isHidden: false,
              styles: { mobile: {} },
              children: [],
            },
          ],
        },
        {
          id: "cont_tab_pane_2",
          name: "محتوای تب دوم",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(nestedTabsContainer);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nested_tabs");
    expect(found?.children?.length).toBe(2);
    expect(found?.widgetProps?.active_tab).toBe(0);

    store.updateElementProps("cont_nested_tabs", { active_tab: 1 });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nested_tabs");
    expect(updated?.widgetProps?.active_tab).toBe(1);
  });

  it("renders nested_accordion with customizable item titles and children", () => {
    const store = useBuilderStore.getState();
    const nestedAccordion: BuilderElement = {
      id: "cont_nested_accordion",
      name: "آکاردئون کانتینری پیشرفته",
      type: "container",
      widgetType: "nested_accordion",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        item_titles: ["سوال اول: شرایط ارسال", "سوال دوم: روش‌های پرداخت"],
      },
      styles: { mobile: {} },
      children: [
        {
          id: "cont_acc_item_1",
          name: "محتوای پرسش ۱",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(nestedAccordion);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nested_accordion");
    expect(found?.widgetType).toBe("nested_accordion");
    expect(found?.children?.length).toBe(1);
    const titles = found?.widgetProps?.item_titles as string[];
    expect(titles?.[0]).toBe("سوال اول: شرایط ارسال");
  });
});
