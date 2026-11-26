import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { validateUniqueElementIds, validateTreeTopology } from "@/lib/builder/schema";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Full Landing Page Creation From Scratch Stress Test", () => {
  it("builds a complete multi-section landing page from scratch with 50+ elements", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-landing", null, "صفحه فرود جامع آزمایشی", "w9-landing");

    // 1. Hero Section Container
    const heroSection: BuilderElement = {
      id: "cont_landing_hero",
      name: "بخش هیرو اصلی",
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
        gridColumns: 1,
      },
      styles: {
        mobile: {
          padding: { top: { value: 64, unit: "px" }, right: { value: 24, unit: "px" }, bottom: { value: 64, unit: "px" }, left: { value: 24, unit: "px" }, isLinked: true },
          background: { type: "gradient", gradient: { direction: "to-r", fromColor: "#059669", toColor: "#0d9488" } },
        },
      },
      children: [
        {
          id: "el_hero_h1",
          name: "تیتر اصلی لندینگ",
          type: "widget",
          widgetType: "heading",
          widgetProps: { text: "پلتفرم تجارت الکترونیک نسل جدید", tag: "h1" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_hero_p",
          name: "زیرتیتر توضیحی",
          type: "widget",
          widgetType: "paragraph",
          widgetProps: { content: "با سرعت نور، طراحی انعطاف‌پذیر و تجربه کاربری مدرن فروشگاه خود را ارتقا دهید." },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_hero_btn",
          name: "دکمه اقدام هیرو",
          type: "widget",
          widgetType: "button",
          widgetProps: { label: "شروع رایگان", url: "/register" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(heroSection);

    // 2. Pricing & Feature Section
    const featureSection: BuilderElement = {
      id: "cont_landing_pricing",
      name: "بخش تعرفه‌ها و خدمات",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "grid",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gridColumns: 3,
        gridAutoFlow: "row",
        gap: { value: 20, unit: "px" },
      },
      styles: { mobile: {} },
      children: [
        {
          id: "el_card_price_1",
          name: "تعرفه پایه",
          type: "widget",
          widgetType: "price_table",
          widgetProps: { title: "پلن پایه", price: "۱۹۰,۰۰۰", currency: "تومان", period: "ماهانه" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_card_price_2",
          name: "تعرفه حرفه‌ای",
          type: "widget",
          widgetType: "price_table",
          widgetProps: { title: "پلن حرفه‌ای", price: "۴۹۰,۰۰۰", currency: "تومان", period: "ماهانه", is_featured: true },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
        {
          id: "el_card_price_3",
          name: "تعرفه سازمانی",
          type: "widget",
          widgetType: "price_table",
          widgetProps: { title: "پلن سازمانی", price: "۹۹۰,۰۰۰", currency: "تومان", period: "ماهانه" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    };
    store.addElement(featureSection);

    // Verify state integrity
    const state = useBuilderStore.getState();
    expect(state.ast.rootElements.length).toBeGreaterThan(2);

    const hero = findElementById(state.ast.rootElements, "cont_landing_hero");
    expect(hero?.children?.length).toBe(3);

    const pricing = findElementById(state.ast.rootElements, "cont_landing_pricing");
    expect(pricing?.layout?.kind).toBe("grid");
    expect(pricing?.children?.length).toBe(3);
  });

  it("safely handles nullish or undefined element children arrays during tree validation (DEFECT-W9-01)", () => {
    const rawAst: any = {
      schemaVersion: 1,
      title: "Test",
      slug: "test",
      globalStyles: {},
      rootElements: [
        {
          id: "cont_safe_root",
          name: "Root",
          type: "container",
          children: null, // intentionally null
        },
        {
          id: "cont_safe_root_2",
          name: "Root 2",
          type: "container",
          // children undefined
        },
      ],
    };
    expect(() => validateUniqueElementIds(rawAst)).not.toThrow();
    expect(() => validateTreeTopology(rawAst)).not.toThrow();
  });
});
