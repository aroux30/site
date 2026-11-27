import { describe, it, expect } from "vitest";
import { SHAPE_DIVIDERS, SHAPE_DIVIDER_OPTIONS } from "@/lib/builder/shape-dividers";
import { parseCssFilterString, composeCssFilterString, computeScrollMotionVars } from "@/lib/builder/motion-runtime";
import { resolveScopedCss } from "@/lib/builder/scoped-css";
import { PageASTSchema } from "@/lib/builder/schema";

describe("Builder Gym Round 08: Elementor Wave 1 Unit Verification", () => {
  it("provides all 29 Elementor SVG shape dividers + none (30 choices) with valid geometry", () => {
    expect(Object.keys(SHAPE_DIVIDERS).length).toBe(29);
    expect(SHAPE_DIVIDER_OPTIONS.length).toBe(30);
    for (const [key, def] of Object.entries(SHAPE_DIVIDERS)) {
      expect(def.viewBox, key).toMatch(/^\d+(\.\d+)?\s+\d+(\.\d+)?\s+[\d.]+\s+[\d.]+$/);
      expect(def.paths.length, key).toBeGreaterThanOrEqual(1);
      expect(def.paths[0]?.d.length ?? 0, key).toBeGreaterThan(5);
    }
  });

  it("parses and composes Elementor CSS filters symmetrically", () => {
    const composed = composeCssFilterString({
      blur: 2.5,
      brightness: 120,
      contrast: 110,
      saturate: 130,
      hue: 45,
    });
    expect(composed).toBe("blur(2.5px) brightness(120%) contrast(110%) saturate(130%) hue-rotate(45deg)");
    expect(parseCssFilterString(composed)).toEqual({
      blur: 2.5,
      brightness: 120,
      contrast: 110,
      saturate: 130,
      hue: 45,
    });
    expect(composeCssFilterString({ blur: 0, brightness: 100, contrast: 100, saturate: 100, hue: 0 })).toBeUndefined();
  });

  it("scopes both {{WRAPPER}} and Elementor selector CSS without corrupting CSS values", () => {
    const css = `
      selector { border: 2px solid #10b981; user-select: none; }
      {{WRAPPER}} > h2:hover { color: #f59e0b; }
      </style><script>alert(1)</script>
    `;
    const resolved = resolveScopedCss(css, "sec_w1_01");
    expect(resolved).toContain('[data-element-id="sec_w1_01"] { border: 2px solid #10b981; user-select: none; }');
    expect(resolved).toContain('[data-element-id="sec_w1_01"] > h2:hover { color: #f59e0b; }');
    expect(resolved).not.toContain("<script>");
  });

  it("computes deterministic scroll parallax, scale and transparency transforms", () => {
    const res = computeScrollMotionVars(
      { scrollParallax: true, parallaxSpeed: 5, scrollScale: true, scrollScaleSpeed: 1.5, scrollOpacity: true },
      1.0
    );
    expect(res.translateY).toBe(-45);
    expect(res.scale).toBe(1.5);
    expect(res.opacity).toBe(1);
  });

  it("validates complete Wave 1 PageAST fields with Zod schema", () => {
    const parsed = PageASTSchema.parse({
      schemaVersion: 1,
      title: "Wave 1 Schema Test",
      slug: "wave-1-schema-test",
      rootElements: [
        {
          id: "sec_w1_grid",
          name: "گرید موج ۱",
          type: "container",
          layout: {
            kind: "grid",
            gridColumns: 4,
            gridRows: 2,
            justifyItems: "center",
            alignContent: "between",
          },
          styles: {
            mobile: {
              background: {
                type: "gradient",
                gradient: { direction: "to-r", gradientType: "radial", angle: 120, fromColor: "#0f172a", toColor: "#10b981" },
                blendMode: "multiply",
              },
              backgroundOverlay: { type: "color", color: "#000000", opacity: 0.4, blendMode: "overlay" },
              hoverBackground: { type: "color", color: "#1e293b" },
              hoverFilter: "brightness(115%)",
              mixBlendMode: "normal",
            },
            customCss: "selector { padding-inline: 12px; }",
            stickyMode: "top",
            stickyOffset: 24,
            stickyOn: ["desktop", "tablet"],
            motionEffects: { scrollParallax: true, parallaxSpeed: 3, mouseTrack: true, mouseSpeed: 4 },
            shapeDividerTop: "clouds",
            shapeDividerBottom: "zigzag",
            shapeDividerTopColor: "#10b981",
            shapeDividerBottomHeight: 60,
            shapeDividerBottomFlip: true,
          },
          children: [
            {
              id: "hd_w1_001",
              name: "هدینگ پیشرفته",
              type: "widget",
              widgetType: "heading",
              widgetProps: { text: "تست تایپوگرافی", tag: "h2" },
              styles: {
                mobile: {
                  typography: {
                    fontFamily: "vazirmatn",
                    fontSize: { value: 2.2, unit: "rem" },
                    fontStyle: "italic",
                    wordSpacing: { value: 0.2, unit: "em" },
                    textDecoration: "overline",
                    textStroke: { value: 1, unit: "px" },
                    textStrokeColor: "#f59e0b",
                  },
                },
              },
              children: [],
            },
          ],
        },
      ],
    });
    expect(parsed.rootElements[0]?.styles.shapeDividerTop).toBe("clouds");
    expect(parsed.rootElements[0]?.styles.stickyMode).toBe("top");
  });
});
