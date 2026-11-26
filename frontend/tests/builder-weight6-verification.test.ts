import { describe, it, expect } from "vitest";
import { useBuilderStore, findElementById } from "@/stores/builder-store";
import { resolveScopedCss, sanitizeScopedCss } from "@/lib/builder/scoped-css";
import type { BuilderElement } from "@/types/builder";

describe("Weight 6: Elementor Parity Wave 1 — Advanced Controls, Transform, Mask & Navigator", () => {
  it("updates transform and mask properties in device styles cleanly", () => {
    const store = useBuilderStore.getState();
    store.initPage("w6-test", null, "تست پورت المنتور", "w6-test");

    const rootEl = useBuilderStore.getState().ast.rootElements[0];
    expect(rootEl).toBeDefined();
    if (rootEl) {
      store.updateDeviceStyles(rootEl.id, "desktop", {
        transform: {
          rotate: 45,
          scale: 1.2,
          skewX: 10,
          skewY: 0,
          flipX: true,
          flipY: false,
        },
        mask: {
          shape: "circle",
          size: "cover",
          position: "center center",
        },
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, rootEl.id);
      const transform = updated?.styles?.desktop?.transform;
      const mask = updated?.styles?.desktop?.mask;

      expect(transform?.rotate).toBe(45);
      expect(transform?.scale).toBe(1.2);
      expect(transform?.skewX).toBe(10);
      expect(transform?.flipX).toBe(true);
      expect(mask?.shape).toBe("circle");
    }
  });

  it("updates CSS grid container properties (columns, auto-flow, gap)", () => {
    const store = useBuilderStore.getState();
    const rootEl = useBuilderStore.getState().ast.rootElements[0];
    if (rootEl) {
      store.updateElementLayout(rootEl.id, {
        kind: "grid",
        gridColumns: 4,
        gridAutoFlow: "dense",
        gap: { value: 24, unit: "px" },
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, rootEl.id);
      expect(updated?.layout?.kind).toBe("grid");
      expect(updated?.layout?.gridColumns).toBe(4);
      expect(updated?.layout?.gridAutoFlow).toBe("dense");
      expect(updated?.layout?.gap?.value).toBe(24);
    }
  });

  it("sets element badges (hidden, locked, custom CSS) for Navigator display", () => {
    const store = useBuilderStore.getState();
    const rootEl = useBuilderStore.getState().ast.rootElements[0];
    if (rootEl) {
      store.setElementLocked(rootEl.id, true);
      store.setElementHidden(rootEl.id, true);
      store.updateElementStyles(rootEl.id, {
        customCssClass: "elementor-animated-widget",
        customCssId: "hero-widget-1",
      });

      const updated = findElementById(useBuilderStore.getState().ast.rootElements, rootEl.id);
      expect(updated?.isLocked).toBe(true);
      expect(updated?.isHidden).toBe(true);
      expect(updated?.styles?.customCssClass).toBe("elementor-animated-widget");
      expect(updated?.styles?.customCssId).toBe("hero-widget-1");
    }
  });

  it("sanitizes and scopes custom CSS with {{WRAPPER}} against injections", () => {
    const rawCss = `{{WRAPPER}} { color: red; } </style><script>alert(1)</script> @import url("evil.css");`;
    const resolved = resolveScopedCss(rawCss, "elem-w6-99");
    expect(resolved).toContain('[data-element-id="elem-w6-99"] { color: red; }');
    expect(resolved).not.toContain("</style>");
    expect(resolved).not.toContain("<script>");
    expect(resolved).not.toContain("@import");
  });
});
