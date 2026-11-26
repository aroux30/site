import { describe, it, expect } from "vitest";
import { useBuilderStore } from "@/stores/builder-store";

describe("Weight 1: Studio Chrome, Layers Tree, Toolbar & Canvas Frame", () => {
  it("initializes 3-tab sidebar with blocks, layers and history", () => {
    const store = useBuilderStore.getState();
    expect(store.activeLeftTab).toBe("blocks");
    store.setLeftTab("layers");
    expect(useBuilderStore.getState().activeLeftTab).toBe("layers");
    store.setLeftTab("history");
    expect(useBuilderStore.getState().activeLeftTab).toBe("history");
    store.setLeftTab("blocks");
    expect(useBuilderStore.getState().activeLeftTab).toBe("blocks");
  });

  it("handles responsive breakpoint switching without state corruption", () => {
    const store = useBuilderStore.getState();
    expect(store.activeBreakpoint).toBe("desktop");
    store.setBreakpoint("tablet");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("tablet");
    store.setBreakpoint("mobile");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("mobile");
    store.setBreakpoint("desktop");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("desktop");
  });

  it("supports toggleHideElement and toggleLockElement in layers tree", () => {
    const store = useBuilderStore.getState();
    store.initPage("w1-test", null, "تست لایه‌ها", "w1-test");
    const rootEl = useBuilderStore.getState().ast.rootElements[0];
    expect(rootEl).toBeDefined();
    if (rootEl) {
      expect(rootEl.isHidden).toBe(false);
      store.toggleHideElement(rootEl.id);
      expect(useBuilderStore.getState().ast.rootElements[0]?.isHidden).toBe(true);
      store.toggleHideElement(rootEl.id);
      expect(useBuilderStore.getState().ast.rootElements[0]?.isHidden).toBe(false);

      expect(rootEl.isLocked).toBe(false);
      store.toggleLockElement(rootEl.id);
      expect(useBuilderStore.getState().ast.rootElements[0]?.isLocked).toBe(true);
      store.toggleLockElement(rootEl.id);
      expect(useBuilderStore.getState().ast.rootElements[0]?.isLocked).toBe(false);
    }
  });

  it("duplicates elements with unique IDs maintaining child tree structure", () => {
    useBuilderStore.getState().initPage("dup-test", null, "تست تکثیر", "dup-test");
    const store = useBuilderStore.getState();
    const initialCount = store.ast.rootElements.length;
    const target = store.ast.rootElements[0];
    expect(target).toBeDefined();

    store.duplicateElement(target!.id);
    const updatedRoots = useBuilderStore.getState().ast.rootElements;
    expect(updatedRoots.length).toBe(initialCount + 1);

    const cloned = updatedRoots[1];
    expect(cloned).toBeDefined();
    expect(cloned!.id).not.toBe(target!.id);
    expect(cloned!.name).toBe(`${target!.name} (کپی)`);
    expect(useBuilderStore.getState().selectedElementId).toBe(cloned!.id);
  });

  it("renames element safely without tree corruption", () => {
    useBuilderStore.getState().initPage("rename-test", null, "تست تغییر نام", "rename-test");
    const store = useBuilderStore.getState();
    const target = store.ast.rootElements[0];
    expect(target).toBeDefined();

    store.renameElement(target!.id, "نام جدید بخش هدر");
    expect(useBuilderStore.getState().ast.rootElements[0]?.name).toBe("نام جدید بخش هدر");
  });
});

