import { describe, it, expect, beforeEach } from "vitest";
import { useBuilderStore } from "@/stores/builder-store";

describe("Global Styles in Builder Store", () => {
  beforeEach(() => {
    useBuilderStore.getState().initPage("test-page", null, "تست استایل سراسری", "test-page");
  });

  it("initializes with default globalStyles", () => {
    const { ast } = useBuilderStore.getState();
    expect(ast.globalStyles).toBeDefined();
  });

  it("updates globalStyles and sets isDirty to true", () => {
    const store = useBuilderStore.getState();
    expect(store.isDirty).toBe(false);

    store.updateGlobalStyles({
      primaryColor: "#10b981",
      secondaryColor: "#0d9488",
      borderRadius: "16px",
      fontFamily: "vazirmatn",
    });

    const updated = useBuilderStore.getState();
    expect(updated.isDirty).toBe(true);
    expect(updated.ast.globalStyles?.primaryColor).toBe("#10b981");
    expect(updated.ast.globalStyles?.secondaryColor).toBe("#0d9488");
    expect(updated.ast.globalStyles?.borderRadius).toBe("16px");
    expect(updated.ast.globalStyles?.fontFamily).toBe("vazirmatn");
  });

  it("supports undo and redo for globalStyles changes", () => {
    const store = useBuilderStore.getState();
    store.updateGlobalStyles({ primaryColor: "#f59e0b" });
    expect(useBuilderStore.getState().ast.globalStyles?.primaryColor).toBe("#f59e0b");

    useBuilderStore.getState().undo();
    expect(useBuilderStore.getState().ast.globalStyles?.primaryColor).toBeUndefined();

    useBuilderStore.getState().redo();
    expect(useBuilderStore.getState().ast.globalStyles?.primaryColor).toBe("#f59e0b");
  });
});
