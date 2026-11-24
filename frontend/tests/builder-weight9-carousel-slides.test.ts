import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Loop Carousel & Advanced Slides", () => {
  it("renders loop_carousel and updates item category and limit", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-carousel-test", null, "تست کاروسل پویا", "w9-carousel-test");

    const carouselWidget: BuilderElement = {
      id: "el_w9_carousel",
      name: "گردونه محصولات ویژه",
      type: "widget",
      widgetType: "loop_carousel",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        limit: 5,
        category: "دیجیتال",
        show_price: true,
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(carouselWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_carousel");
    expect(found?.widgetProps?.limit).toBe(5);
    expect(found?.widgetProps?.category).toBe("دیجیتال");

    store.updateElementProps("el_w9_carousel", { limit: 6, category: "موبایل" });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_carousel");
    expect(updated?.widgetProps?.limit).toBe(6);
    expect(updated?.widgetProps?.category).toBe("موبایل");
  });

  it("handles slides widget with multiple slide items and active slide switching", () => {
    const store = useBuilderStore.getState();
    const slidesWidget: BuilderElement = {
      id: "el_w9_slides",
      name: "اسلایدر بنر اصلی",
      type: "widget",
      widgetType: "slides",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        active_slide: 0,
        slides: [
          { title: "اسلاید ۱: حراج بزرگ", description: "تا ۵۰٪ تخفیف", button_text: "خرید" },
          { title: "اسلاید ۲: کالاهای نو", description: "ارسال رایگان", button_text: "مشاهده" },
        ],
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(slidesWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_slides");
    expect(found?.widgetProps?.active_slide).toBe(0);
    const slides = found?.widgetProps?.slides as any[];
    expect(slides).toHaveLength(2);

    store.updateElementProps("el_w9_slides", { active_slide: 1 });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_slides");
    expect(updated?.widgetProps?.active_slide).toBe(1);
  });
});
