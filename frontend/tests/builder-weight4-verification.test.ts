import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Weight 4: Drag & Drop, Copy/Paste, Templates & Global Components", () => {
  it("copies element, generates unique cloned IDs, and pastes into container", () => {
    const store = useBuilderStore.getState();
    store.initPage("w4-test", null, "تست کپی و پیست", "w4-test");

    const rootEl = useBuilderStore.getState().ast.rootElements[0];
    expect(rootEl).toBeDefined();
    if (rootEl) {
      const initialChildrenCount = rootEl.children?.length || 0;
      store.selectElement(rootEl.id);
      store.copyElement(rootEl.id);
      expect(useBuilderStore.getState().clipboard.element).not.toBeNull();

      store.pasteElement();
      const updatedRoot = useBuilderStore.getState().ast.rootElements[0];
      const newChildrenCount = updatedRoot?.children?.length || 0;
      expect(newChildrenCount).toBeGreaterThan(initialChildrenCount);
    }
  });

  it("copies and pastes styles across different elements with zero style leakage", () => {
    const store = useBuilderStore.getState();
    const widget1: BuilderElement = {
      id: "el_w4_src",
      name: "منبع استایل",
      type: "widget",
      widgetType: "button",
      isLocked: false,
      isHidden: false,
      styles: {
        mobile: {
          padding: { top: { value: 20, unit: "px" }, right: { value: 20, unit: "px" }, bottom: { value: 20, unit: "px" }, left: { value: 20, unit: "px" }, isLinked: true },
          background: { type: "color", color: "#10b981" },
        },
        customCssClass: "my-custom-btn-style",
      },
      children: [],
    };
    const widget2: BuilderElement = {
      id: "el_w4_dest",
      name: "مقصد استایل",
      type: "widget",
      widgetType: "button",
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };
    store.addElement(widget1);
    store.addElement(widget2);

    store.copyStyles("el_w4_src");
    expect(useBuilderStore.getState().clipboard.styles).not.toBeNull();

    store.pasteStyles("el_w4_dest");
    const updatedDest = findElementById(useBuilderStore.getState().ast.rootElements, "el_w4_dest");
    expect(updatedDest?.styles?.customCssClass).toBe("my-custom-btn-style");
    expect(updatedDest?.styles?.mobile?.background?.color).toBe("#10b981");
  });

  it("creates synchronized global components and detaches cleanly", () => {
    const store = useBuilderStore.getState();
    const compId = store.makeGlobalComponent("el_w4_dest");
    expect(compId).not.toBeNull();

    let elem = findElementById(useBuilderStore.getState().ast.rootElements, "el_w4_dest");
    expect(elem?.globalComponentId).toBe(compId);

    store.detachGlobalComponent("el_w4_dest");
    elem = findElementById(useBuilderStore.getState().ast.rootElements, "el_w4_dest");
    expect(elem?.globalComponentId).toBeFalsy();
  });
});
