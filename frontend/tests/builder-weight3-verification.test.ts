import { describe, it, expect } from "vitest";
import { useBuilderStore } from "@/stores/builder-store";
import { DEFAULT_THEME_TOKENS } from "@/lib/builder/theme-schema";

describe("Weight 3: Block Patterns, Palette Tabs & Global Styles Dialog", () => {
  it("manages global styles design tokens and resets to site theme", () => {
    const store = useBuilderStore.getState();
    store.initPage("w3-test", null, "تست استایل سراسری", "w3-test");

    // 1. Update Global Tokens
    store.updateGlobalStyles({
      primaryColor: "#2563eb",
      secondaryColor: "#7c3aed",
      borderRadius: "16px",
      fontFamily: "system-ui",
      textColor: "#1e293b",
      backgroundColor: "#f8fafc",
    });

    let currentGs = useBuilderStore.getState().ast.globalStyles;
    expect(currentGs?.primaryColor).toBe("#2563eb");
    expect(currentGs?.secondaryColor).toBe("#7c3aed");
    expect(currentGs?.borderRadius).toBe("16px");
    expect(currentGs?.fontFamily).toBe("system-ui");

    // 2. Reset to Site Theme
    store.updateGlobalStyles({
      primaryColor: undefined,
      secondaryColor: undefined,
      borderRadius: undefined,
      fontFamily: undefined,
      textColor: undefined,
      backgroundColor: undefined,
    });

    currentGs = useBuilderStore.getState().ast.globalStyles;
    expect(currentGs?.primaryColor).toBeUndefined();
    expect(currentGs?.secondaryColor).toBeUndefined();
    expect(currentGs?.borderRadius).toBeUndefined();
  });

  it("verifies default theme token schema values", () => {
    expect(DEFAULT_THEME_TOKENS.primitive).toBeDefined();
    expect(DEFAULT_THEME_TOKENS.primitive.color?.emerald?.[500]?.$value).toBe("#10b981");
    expect(DEFAULT_THEME_TOKENS.primitive.dimension?.radius?.lg?.$value).toBe("14px");
  });
});
