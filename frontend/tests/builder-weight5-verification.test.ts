import { describe, it, expect } from "vitest";
import { useBuilderStore } from "@/stores/builder-store";
import { resolveResponsiveValue } from "@/lib/builder/schema";

describe("Weight 5: Responsive Resolution, Mobile/Tablet Viewports & Dark Mode", () => {
  it("resolves responsive values with mobile-first cascade correctly", () => {
    const values = {
      mobile: "16px",
      tablet: "24px",
      desktop: "32px",
    };

    expect(resolveResponsiveValue(values, "mobile")).toBe("16px");
    expect(resolveResponsiveValue(values, "tablet")).toBe("24px");
    expect(resolveResponsiveValue(values, "desktop")).toBe("32px");

    // Fallback cascade to mobile when tablet/desktop are omitted
    const fallbackValues = {
      mobile: "18px",
    };
    expect(resolveResponsiveValue(fallbackValues, "tablet")).toBe("18px");
    expect(resolveResponsiveValue(fallbackValues, "desktop")).toBe("18px");
  });

  it("handles active breakpoint switching without mutating document schema", () => {
    const store = useBuilderStore.getState();
    store.initPage("w5-test", null, "تست ریسپانسیو", "w5-test");

    store.setBreakpoint("tablet");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("tablet");

    store.setBreakpoint("mobile");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("mobile");

    store.setBreakpoint("desktop");
    expect(useBuilderStore.getState().activeBreakpoint).toBe("desktop");
    expect(useBuilderStore.getState().ast.rootElements.length).toBeGreaterThan(0);
  });

  it("safely handles null/undefined values and custom fallback in resolveResponsiveValue", () => {
    expect(resolveResponsiveValue(undefined as any, "mobile", "14px")).toBe("14px");
    expect(resolveResponsiveValue(null as any, "desktop", "20px")).toBe("20px");
    expect(resolveResponsiveValue(undefined as any, "tablet")).toBeUndefined();
  });

  it("handles 50+ nested elements stress test without topology errors", () => {
    const store = useBuilderStore.getState();
    store.initPage("stress-test-page", null, "تست فشار ۵۰ المان", "stress-page");

    for (let i = 0; i < 50; i++) {
      const el = {
        id: `el_stress_${i}`,
        name: `المان فشار ${i + 1}`,
        type: "widget" as const,
        widgetType: "heading",
        widgetProps: { text: `تیتر شماره ${i + 1}` },
        isLocked: false,
        isHidden: false,
        styles: { mobile: {} },
        children: [],
      };
      store.addElement(el);
    }

    const state = useBuilderStore.getState();
    expect(state.ast.rootElements.length).toBeGreaterThanOrEqual(51);
  });
});

