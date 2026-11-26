import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { PageAST } from "@/types/builder";

const initialAst: PageAST = {
  schemaVersion: 1,
  title: "Weight 4 Test",
  slug: "w4-test",
  globalStyles: {},
  rootElements: [
    {
      id: "cont_w4_1",
      name: "Container",
      type: "container",
      isLocked: false,
      isHidden: false,
      layout: {
        kind: "flex",
        direction: "column",
        justifyContent: "start",
        alignItems: "stretch",
        flexWrap: "nowrap",
        gap: { value: 16, unit: "px" },
        gridColumns: 1,
      },
      styles: { mobile: {} },
      children: [
        {
          id: "head_w4_1",
          name: "Heading 1",
          type: "widget",
          widgetType: "heading",
          widgetProps: { text: "اول", tag: "h2" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {}, customCssId: "keep-unique-1" },
          children: [],
        },
        {
          id: "text_w4_1",
          name: "Text 1",
          type: "widget",
          widgetType: "text_editor",
          widgetProps: { content: "<p>دوم</p>" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {}, customCssId: "keep-unique-2" },
          children: [],
        },
      ],
    },
  ],
};

describe("Builder Gym Round 06 (Weight 4): Multi-Select, Copy/Paste Styles & Global Component Sync", () => {
  beforeEach(() => {
    useBuilderStore.getState().initPage("page-w4", JSON.parse(JSON.stringify(initialAst)), "Weight 4 Test", "w4-test");
  });

  it("multi-selects via toggleSelectElement, deletes all selected, and restores on undo", () => {
    const store = useBuilderStore.getState();
    store.selectElement("head_w4_1");
    store.toggleSelectElement("text_w4_1", true);
    expect(useBuilderStore.getState().selectedElementIds).toEqual(["head_w4_1", "text_w4_1"]);

    store.deleteSelectedElements();
    const contAfterDel = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w4_1");
    expect(contAfterDel?.children).toHaveLength(0);

    store.undo();
    const contAfterUndo = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w4_1");
    expect(contAfterUndo?.children).toHaveLength(2);
  });

  it("copies background and styles onto target element without overwriting target customCssId", () => {
    const store = useBuilderStore.getState();
    store.updateDeviceStyles("head_w4_1", "desktop", {
      background: { type: "color", color: "#dbeafe" },
    });
    store.copyStyles("head_w4_1");
    store.pasteStyles("text_w4_1");

    const updatedText = findElementById(useBuilderStore.getState().ast.rootElements, "text_w4_1");
    expect(updatedText?.styles?.desktop?.background?.color).toBe("#dbeafe");
    expect(updatedText?.styles?.customCssId).toBe("keep-unique-2");
  });

  it("syncs global component instances across edits and isolates detached instances", () => {
    const store = useBuilderStore.getState();
    const gcId = store.makeGlobalComponent("head_w4_1");
    expect(gcId).toBeTruthy();

    store.duplicateElement("head_w4_1");
    const cont = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w4_1");
    const headings = (cont?.children || []).filter((c) => c.widgetType === "heading");
    expect(headings).toHaveLength(2);
    expect(headings[0]?.globalComponentId).toBe(gcId);
    expect(headings[1]?.globalComponentId).toBe(gcId);

    store.updateElementProps("head_w4_1", { text: "عنوان همگام‌شده" });
    const afterSync = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w4_1");
    expect(afterSync?.children?.[0]?.widgetProps?.text).toBe("عنوان همگام‌شده");
    expect(afterSync?.children?.[1]?.widgetProps?.text).toBe("عنوان همگام‌شده");

    const secondId = headings[1]!.id;
    store.detachGlobalComponent(secondId);
    store.updateElementProps("head_w4_1", { text: "فقط نسخه اصلی" });

    const afterDetach = findElementById(useBuilderStore.getState().ast.rootElements, "cont_w4_1");
    expect(afterDetach?.children?.find((c) => c.id === "head_w4_1")?.widgetProps?.text).toBe("فقط نسخه اصلی");
    expect(afterDetach?.children?.find((c) => c.id === secondId)?.widgetProps?.text).toBe("عنوان همگام‌شده");
  });
});
