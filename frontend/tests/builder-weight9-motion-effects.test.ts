import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 9: Infinite Overload — Motion, Animations & Transition Effects", () => {
  it("applies entrance animations with duration and delay to elements", () => {
    const store = useBuilderStore.getState();
    store.initPage("w9-motion-test", null, "تست افکت‌های حرکتی", "w9-motion-test");

    const animatedBox: BuilderElement = {
      id: "el_w9_anim_box",
      name: "باکس انیمیشنی",
      type: "widget",
      widgetType: "call_to_action",
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          transitionDuration: 0.3,
        },
        animation: "fade-in",
        animationDuration: 0.8,
        animationDelay: 0.2,
      },
      children: [],
    };
    store.addElement(animatedBox);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_anim_box");
    expect(found?.styles?.animation).toBe("fade-in");
    expect(found?.styles?.animationDuration).toBe(0.8);
    expect(found?.styles?.animationDelay).toBe(0.2);
    expect(found?.styles?.mobile?.transitionDuration).toBe(0.3);

    store.updateElementStyles("el_w9_anim_box", {
      animation: "slide-up",
      animationDuration: 1.2,
    });
    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_anim_box");
    expect(updated?.styles?.animation).toBe("slide-up");
    expect(updated?.styles?.animationDuration).toBe(1.2);
  });

  it("handles hover states and box shadows without style degradation", () => {
    const store = useBuilderStore.getState();
    const cardWidget: BuilderElement = {
      id: "el_w9_hover_card",
      name: "کارت با افکت هاور",
      type: "widget",
      widgetType: "button",
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          boxShadow: "0 4px 6px -1px rgb(0 0 0 / 0.1)",
          hoverBoxShadow: "0 20px 25px -5px rgb(0 0 0 / 0.1)",
          transitionDuration: 0.25,
        },
      },
      children: [],
    };
    store.addElement(cardWidget);

    const found = findElementById(useBuilderStore.getState().ast.rootElements, "el_w9_hover_card");
    expect(found?.styles?.mobile?.boxShadow).toContain("0 4px 6px");
    expect(found?.styles?.mobile?.hoverBoxShadow).toContain("0 20px 25px");
  });
});
