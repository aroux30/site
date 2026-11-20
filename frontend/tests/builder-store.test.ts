import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore, findElementById, cloneElementWithNewIds } from "@/stores/builder-store";
import type { BuilderElement } from "@/types/builder";

describe("Visual Page Builder Zustand Store & Undo/Redo Engine (Phase P1)", () => {
  beforeEach(() => {
    useBuilderStore.getState().initPage("page-123", null, "برگه تست", "test-page");
  });

  it("initializes with default PageAST and root elements", () => {
    const state = useBuilderStore.getState();
    expect(state.ast.title).toBe("برگه تست");
    expect(state.ast.slug).toBe("test-page");
    expect(state.ast.rootElements.length).toBeGreaterThan(0);
    expect(state.isDirty).toBe(false);
    expect(state.history.past).toHaveLength(0);
    expect(state.history.future).toHaveLength(0);
  });

  it("adds an element to the root and records undo history", () => {
    const newWidget: BuilderElement = {
      id: "el_customBtn",
      name: "دکمه خرید جدید",
      type: "widget",
      widgetType: "button",
      widgetProps: { label: "کلیک کنید", url: "/shop" },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    useBuilderStore.getState().addElement(newWidget);

    const state = useBuilderStore.getState();
    expect(state.isDirty).toBe(true);
    expect(state.history.past).toHaveLength(1);
    expect(state.selectedElementId).toBe("el_customBtn");

    const found = findElementById(state.ast.rootElements, "el_customBtn");
    expect(found).not.toBeNull();
    expect(found?.name).toBe("دکمه خرید جدید");
  });

  it("adds an element inside a target container", () => {
    const containerId = useBuilderStore.getState().ast.rootElements[0]!.id;
    const innerWidget: BuilderElement = {
      id: "el_innerHead",
      name: "عنوان فرعی درون کانتینر",
      type: "widget",
      widgetType: "heading",
      widgetProps: { text: "تست کانتینر", tag: "h3" },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    useBuilderStore.getState().addElement(innerWidget, containerId, 0);

    const state = useBuilderStore.getState();
    const container = findElementById(state.ast.rootElements, containerId);
    expect(container).not.toBeNull();
    expect(container?.children[0]?.id).toBe("el_innerHead");
  });

  it("updates element props and tracks history", () => {
    const state = useBuilderStore.getState();
    const firstWidget = state.ast.rootElements[0]!.children[0]!;

    useBuilderStore.getState().updateElementProps(firstWidget.id, { text: "متن ویرایش‌شده" });

    const updatedState = useBuilderStore.getState();
    const updatedEl = findElementById(updatedState.ast.rootElements, firstWidget.id);
    expect(updatedEl?.widgetProps?.text).toBe("متن ویرایش‌شده");
    expect(updatedState.history.past).toHaveLength(1);
  });

  it("updates device styles following Mobile-First convention", () => {
    const state = useBuilderStore.getState();
    const targetId = state.ast.rootElements[0]!.id;

    // Apply mobile style
    useBuilderStore.getState().updateDeviceStyles(targetId, "mobile", {
      opacity: 0.8,
    });
    // Apply tablet override
    useBuilderStore.getState().updateDeviceStyles(targetId, "tablet", {
      opacity: 0.9,
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, targetId);
    expect(updated?.styles.mobile.opacity).toBe(0.8);
    expect(updated?.styles.tablet?.opacity).toBe(0.9);
  });

  it("duplicates an element with new unique IDs and correct placement", () => {
    const state = useBuilderStore.getState();
    const firstWidget = state.ast.rootElements[0]!.children[0]!;
    const originalChildrenCount = state.ast.rootElements[0]!.children.length;

    useBuilderStore.getState().duplicateElement(firstWidget.id);

    const updatedState = useBuilderStore.getState();
    const container = updatedState.ast.rootElements[0]!;
    expect(container.children.length).toBe(originalChildrenCount + 1);

    const duplicated = container.children[1]!;
    expect(duplicated.id).not.toBe(firstWidget.id);
    expect(duplicated.name).toContain("(کپی)");
  });

  it("deletes an element and clears selection if active", () => {
    const state = useBuilderStore.getState();
    const firstWidget = state.ast.rootElements[0]!.children[0]!;

    useBuilderStore.getState().selectElement(firstWidget.id);
    expect(useBuilderStore.getState().selectedElementId).toBe(firstWidget.id);

    useBuilderStore.getState().deleteElement(firstWidget.id);

    const updatedState = useBuilderStore.getState();
    expect(findElementById(updatedState.ast.rootElements, firstWidget.id)).toBeNull();
    expect(updatedState.selectedElementId).toBeNull();
  });

  it("handles multi-step undo and redo stack correctly", () => {
    const state = useBuilderStore.getState();
    const firstWidget = state.ast.rootElements[0]!.children[0]!;
    const originalText = firstWidget.widgetProps?.text;

    // Edit 1
    useBuilderStore.getState().updateElementProps(firstWidget.id, { text: "ویرایش ۱" });
    // Edit 2
    useBuilderStore.getState().updateElementProps(firstWidget.id, { text: "ویرایش ۲" });

    let current = findElementById(useBuilderStore.getState().ast.rootElements, firstWidget.id);
    expect(current?.widgetProps?.text).toBe("ویرایش ۲");

    // Undo 1 -> should revert to "ویرایش ۱"
    useBuilderStore.getState().undo();
    current = findElementById(useBuilderStore.getState().ast.rootElements, firstWidget.id);
    expect(current?.widgetProps?.text).toBe("ویرایش ۱");

    // Undo 2 -> should revert to original text
    useBuilderStore.getState().undo();
    current = findElementById(useBuilderStore.getState().ast.rootElements, firstWidget.id);
    expect(current?.widgetProps?.text).toBe(originalText);

    // Redo 1 -> should go back to "ویرایش ۱"
    useBuilderStore.getState().redo();
    current = findElementById(useBuilderStore.getState().ast.rootElements, firstWidget.id);
    expect(current?.widgetProps?.text).toBe("ویرایش ۱");

    // Redo 2 -> should go back to "ویرایش ۲"
    useBuilderStore.getState().redo();
    current = findElementById(useBuilderStore.getState().ast.rootElements, firstWidget.id);
    expect(current?.widgetProps?.text).toBe("ویرایش ۲");
  });

  it("updates element layout for nested containers and records undo history", () => {
    const rootContainer = useBuilderStore.getState().ast.rootElements[0]!;
    const nestedContainer: BuilderElement = {
      id: "cont_nested_1",
      name: "کانتینر تودرتو",
      type: "container",
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 1,
      },
      isLocked: false,
      isHidden: false,
      styles: { mobile: {} },
      children: [],
    };

    useBuilderStore.getState().addElement(nestedContainer, rootContainer.id);

    // Update nested container layout
    useBuilderStore.getState().updateElementLayout("cont_nested_1", {
      kind: "grid",
      gridColumns: 4,
      gap: { value: 24, unit: "px" },
      justifyContent: "center",
      alignItems: "center",
    });

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nested_1");
    expect(updated?.layout?.kind).toBe("grid");
    expect(updated?.layout?.gridColumns).toBe(4);
    expect(updated?.layout?.gap.value).toBe(24);
    expect(updated?.layout?.justifyContent).toBe("center");
    expect(updated?.layout?.alignItems).toBe("center");

    // Undo should revert layout
    useBuilderStore.getState().undo();
    const reverted = findElementById(useBuilderStore.getState().ast.rootElements, "cont_nested_1");
    expect(reverted?.layout?.kind).toBe("flex");
    expect(reverted?.layout?.gridColumns).toBe(1);
    expect(reverted?.layout?.gap.value).toBe(16);
  });

  it("renames, hides, locks, and detaches elements with undo history", () => {
    const targetEl = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;

    // Rename
    useBuilderStore.getState().renameElement(targetEl.id, "سرتیتر سفارشی جدید");
    let current = findElementById(useBuilderStore.getState().ast.rootElements, targetEl.id);
    expect(current?.name).toBe("سرتیتر سفارشی جدید");

    // Hide and Lock
    useBuilderStore.getState().setElementHidden(targetEl.id, true);
    useBuilderStore.getState().setElementLocked(targetEl.id, true);
    current = findElementById(useBuilderStore.getState().ast.rootElements, targetEl.id);
    expect(current?.isHidden).toBe(true);
    expect(current?.isLocked).toBe(true);

    // Make and Detach Global Component
    const globalId = useBuilderStore.getState().makeGlobalComponent(targetEl.id);
    expect(globalId).toBeTruthy();
    current = findElementById(useBuilderStore.getState().ast.rootElements, targetEl.id);
    expect(current?.globalComponentId).toBe(globalId);

    useBuilderStore.getState().detachGlobalComponent(targetEl.id);
    current = findElementById(useBuilderStore.getState().ast.rootElements, targetEl.id);
    expect(current?.globalComponentId).toBeNull();
  });

  it("cloneElementWithNewIds respects appendCopySuffix flag", () => {
    const targetEl = useBuilderStore.getState().ast.rootElements[0]!.children[0]!;

    // Default: appends (کپی)
    const clonedWithSuffix = cloneElementWithNewIds(targetEl, true);
    expect(clonedWithSuffix.name).toContain("(کپی)");

    // Clean clone: preserves original clean name
    const clonedClean = cloneElementWithNewIds(targetEl, false);
    expect(clonedClean.name).toBe(targetEl.name);
    expect(clonedClean.id).not.toBe(targetEl.id);
  });
});
