import { describe, it, expect } from "vitest";
import { getBuilderIcon, getBuilderIconLabel, BUILDER_ICONS, BUILDER_ICON_OPTIONS } from "@/lib/builder/icon-registry";
import { useBuilderStore } from "@/stores/builder-store";

describe("Weight 0: Inspector, Registry, RTL & SVG Icon Verification", () => {
  it("provides valid LucideIcon components and labels from icon-registry", () => {
    expect(BUILDER_ICONS.star).toBeDefined();
    expect(BUILDER_ICONS.heart).toBeDefined();
    expect(BUILDER_ICONS["shield-check"]).toBeDefined();
    expect(BUILDER_ICONS.truck).toBeDefined();

    const starIcon = getBuilderIcon("star");
    expect(starIcon).toBe(BUILDER_ICONS.star);

    const fallbackIcon = getBuilderIcon("unknown-non-existent-icon");
    expect(fallbackIcon).toBe(BUILDER_ICONS.sparkles);

    const starLabel = getBuilderIconLabel("star");
    expect(starLabel).toBe("ستاره (Star)");

    expect(BUILDER_ICON_OPTIONS.length).toBeGreaterThanOrEqual(20);
  });

  it("initializes default canvas content with correct RTL right-panel guidance", () => {
    useBuilderStore.getState().initPage("rtl-page-test", null, "تست جهت‌داری", "rtl-test");
    const state = useBuilderStore.getState();
    const textWidget = state.ast.rootElements[0]?.children?.[1];
    expect(textWidget).toBeDefined();
    expect(textWidget?.widgetProps?.content).toContain("پنل سمت راست");
    expect(textWidget?.widgetProps?.content).not.toContain("پنل سمت چپ");
  });
});
