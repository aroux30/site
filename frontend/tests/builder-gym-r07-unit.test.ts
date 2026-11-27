import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import type { BuilderElement, PageAST } from "@/types/builder";

function makeStressAst(countContainers = 10, childrenPerContainer = 5): PageAST {
  const roots: BuilderElement[] = Array.from({ length: countContainers }, (_, i) => ({
    id: `cont_s5_${i}`,
    name: `بخش ${i + 1}`,
    type: "container",
    isLocked: false,
    isHidden: false,
    layout: {
      kind: "flex",
      direction: "column",
      justifyContent: "start",
      alignItems: "stretch",
      flexWrap: "nowrap",
      gap: { value: 12, unit: "px" },
      gridColumns: 1,
    },
    styles: { mobile: {} },
    children: [
      {
        id: `inner_s5_${i}`,
        name: `تودرتو ${i + 1}`,
        type: "container",
        isLocked: false,
        isHidden: false,
        layout: {
          kind: "flex",
          direction: "column",
          justifyContent: "start",
          alignItems: "stretch",
          flexWrap: "nowrap",
          gap: { value: 8, unit: "px" },
          gridColumns: 1,
        },
        styles: { mobile: {} },
        children: Array.from({ length: childrenPerContainer - 1 }, (__, j) => ({
          id: `wid_s5_${i}_${j}`,
          name: `ویجت ${i + 1}-${j + 1}`,
          type: "widget",
          widgetType: "heading",
          widgetProps: { text: `متن ${i + 1}-${j + 1}`, tag: "h3" },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        })),
      },
    ],
  }));

  return {
    schemaVersion: 1,
    title: "Stress Test 60",
    slug: "stress-60",
    globalStyles: {},
    rootElements: roots,
  };
}

describe("Builder Gym Round 07 (Weight 5): Responsive Overrides, Stress 60+ Nodes & Dirty Retention", () => {
  beforeEach(() => {
    useBuilderStore.getState().initPage("p-w5", makeStressAst(10, 5), "Stress Test 60", "stress-60");
  });

  it("handles 60 nested elements across 3 levels cleanly and retains isDirty until markClean", () => {
    const ast = useBuilderStore.getState().ast;
    const total = ast.rootElements.reduce(
      (sum, root) => sum + 1 + (root.children || []).reduce((s2, c) => s2 + 1 + (c.children?.length || 0), 0),
      0
    );
    expect(total).toBe(60);

    useBuilderStore.getState().updateDeviceStyles("wid_s5_9_3", "mobile", {
      typography: { fontSize: { value: 16, unit: "px" } },
    });
    useBuilderStore.getState().updateDeviceStyles("wid_s5_9_3", "tablet", {
      typography: { fontSize: { value: 24, unit: "px" } },
    });
    expect(useBuilderStore.getState().isDirty).toBe(true);

    const updated = findElementById(useBuilderStore.getState().ast.rootElements, "wid_s5_9_3");
    expect(updated?.styles?.mobile?.typography?.fontSize?.value).toBe(16);
    expect(updated?.styles?.tablet?.typography?.fontSize?.value).toBe(24);

    // Simulate failed network save: setIsSaving(false) must NOT clear isDirty
    useBuilderStore.getState().setIsSaving(true);
    useBuilderStore.getState().setIsSaving(false);
    expect(useBuilderStore.getState().isDirty).toBe(true);

    useBuilderStore.getState().markClean();
    expect(useBuilderStore.getState().isDirty).toBe(false);
  });
});
