import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 8: Elementor Wave 3 — Theme Builder, Loop Builder & Multi-Step Form", () => {
  it("renders loop_grid widget and updates columns and limit reactively", () => {
    const store = useBuilderStore.getState();
    store.initPage("w8-test", null, "تست موج ۳ المنتور", "w8-test");

    const loopGridWidget: BuilderElement = {
      id: "el_w8_loop",
      name: "حلقه پویا",
      type: "widget",
      widgetType: "loop_grid",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        columns: 4,
        limit: 8,
        category: "محصولات ویژه",
        show_price: true,
        show_button: true,
        button_text: "خرید فوری",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(loopGridWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w8_loop");
    expect(found?.widgetProps?.columns).toBe(4);
    expect(found?.widgetProps?.limit).toBe(8);

    store.updateElementProps("el_w8_loop", { columns: 3, limit: 6 });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w8_loop");
    expect(updated?.widgetProps?.columns).toBe(3);
    expect(updated?.widgetProps?.limit).toBe(6);
  });

  it("advances and steps through multi_step_form steps", () => {
    const store = useBuilderStore.getState();
    const formWidget: BuilderElement = {
      id: "el_w8_form",
      name: "فرم چندمرحله‌ای",
      type: "widget",
      widgetType: "multi_step_form",
      isLocked: false,
      isHidden: false,
      widgetProps: {
        title: "ثبت‌نام و عضویت",
        current_step: 1,
        steps: ["مشخصات فردی", "اطلاعات تماس", "بارگذاری مدارک", "تایید"],
        indicator_style: "numbers",
      },
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(formWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w8_form");
    expect(found?.widgetProps?.current_step).toBe(1);

    store.updateElementProps("el_w8_form", { current_step: 2 });
    const step2 = findElementById(useBuilderStore.getState().ast.rootElements, "el_w8_form");
    expect(step2?.widgetProps?.current_step).toBe(2);

    store.updateElementProps("el_w8_form", { current_step: 3 });
    const step3 = findElementById(useBuilderStore.getState().ast.rootElements, "el_w8_form");
    expect(step3?.widgetProps?.current_step).toBe(3);
  });
});
