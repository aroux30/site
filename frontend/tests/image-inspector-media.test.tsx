import { describe, it, expect, vi } from "vitest";
import React from "react";
import { render, screen, fireEvent } from "@testing-library/react";
import { InspectorPanel } from "@/components/admin/builder/inspector-panel";
import { useBuilderStore } from "@/stores/builder-store";

vi.mock("@/components/admin/media-picker", () => ({
  MediaPicker: ({ value, onChange }: { value: string; onChange: (url: string) => void }) => (
    <div data-testid="media-picker-mock">
      <span data-testid="media-picker-value">{value}</span>
      <button
        type="button"
        data-testid="media-picker-choose-btn"
        onClick={() => onChange("https://example.com/selected-image.webp")}
      >
        انتخاب تصویر
      </button>
    </div>
  ),
}));

describe("Image Inspector Media Library Integration", () => {
  it("renders MediaPicker and allows selecting an asset URL", () => {
    // Initialize store with an image element selected
    const store = useBuilderStore.getState();
    store.initPage("test-page", {
      schemaVersion: 1,
      title: "Test Page",
      slug: "test-page",
      globalStyles: {},
      rootElements: [
        {
          id: "el_img_test",
          name: "تصویر تست",
          type: "widget",
          widgetType: "image",
          widgetProps: {
            url: "/initial-image.svg",
            alt: "تصویر اولیه",
          },
          isLocked: false,
          isHidden: false,
          styles: { mobile: {} },
          children: [],
        },
      ],
    });

    store.selectElement("el_img_test");

    render(<InspectorPanel />);

    // Verify MediaPicker is rendered
    expect(screen.getByTestId("media-picker-mock")).toBeDefined();
    expect(screen.getByTestId("media-picker-value").textContent).toBe("/initial-image.svg");

    // Click the mock choose button to select an image
    fireEvent.click(screen.getByTestId("media-picker-choose-btn"));

    // Verify store element props updated
    const updated = useBuilderStore.getState();
    const imgEl = updated.ast.rootElements[0];
    expect(imgEl.widgetProps?.url).toBe("https://example.com/selected-image.webp");
  });
});
