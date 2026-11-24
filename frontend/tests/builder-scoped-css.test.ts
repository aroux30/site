import { describe, it, expect } from "vitest";
import { resolveScopedCss } from "@/lib/builder/scoped-css";

describe("Weight 9: Scoped CSS Resolver ({{WRAPPER}} Parity)", () => {
  it("replaces {{WRAPPER}} with data-element-id selector", () => {
    const rawCss = "{{WRAPPER}} .title { color: #10b981; }";
    const resolved = resolveScopedCss(rawCss, "el_hero_123");
    expect(resolved).toBe('[data-element-id="el_hero_123"] .title { color: #10b981; }');
  });

  it("handles case-insensitive and spaced {{ wrapper }} placeholders", () => {
    const rawCss = "{{ wrapper }} { border-radius: 12px; } {{  WRAPPER  }} p { margin: 0; }";
    const resolved = resolveScopedCss(rawCss, "el_box_456");
    expect(resolved).toContain('[data-element-id="el_box_456"] { border-radius: 12px; }');
    expect(resolved).toContain('[data-element-id="el_box_456"] p { margin: 0; }');
  });

  it("returns empty string on null or empty input", () => {
    expect(resolveScopedCss(null, "el_1")).toBe("");
    expect(resolveScopedCss("", "el_1")).toBe("");
    expect(resolveScopedCss("   ", "el_1")).toBe("");
  });
});
