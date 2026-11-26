import { describe, it, expect } from "vitest";
import { getBuilderIcon, getBuilderIconLabel, BUILDER_ICONS, BUILDER_ICON_OPTIONS } from "@/lib/builder/icon-registry";
import { useBuilderStore } from "@/stores/builder-store";
import { createDefaultSpacingBox, validateUniqueElementIds, BuilderValidationError } from "@/lib/builder/schema";

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

  it("creates default spacing box with linked 0px values", () => {
    const spacing = createDefaultSpacingBox();
    expect(spacing.isLinked).toBe(true);
    expect(spacing.top).toEqual({ value: 0, unit: "px" });
    expect(spacing.right).toEqual({ value: 0, unit: "px" });
    expect(spacing.bottom).toEqual({ value: 0, unit: "px" });
    expect(spacing.left).toEqual({ value: 0, unit: "px" });

    const custom = createDefaultSpacingBox(16, "rem", false);
    expect(custom.isLinked).toBe(false);
    expect(custom.top).toEqual({ value: 16, unit: "rem" });
  });

  it("validates unique element IDs in page topology", () => {
    const validAst = {
      schemaVersion: 1,
      title: "معتبر",
      slug: "valid",
      rootElements: [
        { id: "el_root_1", type: "container", children: [{ id: "el_child_1", type: "widget", children: [] }] },
      ],
    };
    expect(() => validateUniqueElementIds(validAst as any)).not.toThrow();

    const duplicateAst = {
      schemaVersion: 1,
      title: "تکراری",
      slug: "duplicate",
      rootElements: [
        { id: "el_duplicate", type: "container", children: [{ id: "el_duplicate", type: "widget", children: [] }] },
      ],
    };
    expect(() => validateUniqueElementIds(duplicateAst as any)).toThrow(BuilderValidationError);
  });
});
