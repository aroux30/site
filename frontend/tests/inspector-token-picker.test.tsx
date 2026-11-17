import { describe, it, expect } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { InspectorPanel } from "@/components/admin/builder/inspector-panel";
import { useBuilderStore } from "@/stores/builder-store";

describe("Inspector Design System Token Picker", () => {
  it("allows selecting a design token CSS variable for background color", () => {
    const store = useBuilderStore.getState();
    store.initPage("test-page", {
      schemaVersion: 1,
      title: "Test Page",
      slug: "test-page",
      globalStyles: {},
      rootElements: [
        {
          id: "el_container_test",
          name: "کانتینر تست",
          type: "container",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    });

    store.selectElement("el_container_test");
    store.setInspectorTab("style");

    render(<InspectorPanel />);

    // Switch to Style tab and verify token chip is present
    const primaryTokenChip = screen.getByText("رنگ اصلی");
    expect(primaryTokenChip).toBeDefined();

    // Click the token chip
    fireEvent.click(primaryTokenChip);

    // Verify background color was updated to var(--primary)
    const updated = useBuilderStore.getState();
    const container = updated.ast.rootElements[0];
    expect(container).toBeDefined();
    if (container) {
      const bg = container.styles.desktop?.background?.color || container.styles.mobile?.background?.color;
      expect(bg).toBe("var(--primary)");
    }
  });

  it("allows selecting a design token CSS variable for text color and border radius", () => {
    const store = useBuilderStore.getState();
    store.initPage("test-page-2", {
      schemaVersion: 1,
      title: "Test Page 2",
      slug: "test-page-2",
      globalStyles: {},
      rootElements: [
        {
          id: "el_button_test",
          name: "دکمه تست",
          type: "widget",
          widgetType: "button",
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    });

    store.selectElement("el_button_test");
    store.setInspectorTab("style");

    render(<InspectorPanel />);

    // Select text color token "متن اصلی"
    const textTokenChip = screen.getByText("متن اصلی");
    fireEvent.click(textTokenChip);

    // Select radius token "شعاع تم سازمانی"
    const radiusTokenChip = screen.getByText("شعاع تم سازمانی");
    fireEvent.click(radiusTokenChip);

    const updated = useBuilderStore.getState();
    const btn = updated.ast.rootElements[0];
    expect(btn).toBeDefined();
    if (btn) {
      const typoColor = btn.styles.desktop?.typography?.color || btn.styles.mobile?.typography?.color;
      const radToken = (btn.styles.desktop?.border as any)?.radiusToken || (btn.styles.mobile?.border as any)?.radiusToken;

      expect(typoColor).toBe("var(--foreground)");
      expect(radToken).toBe("var(--radius)");
    }
  });
});
