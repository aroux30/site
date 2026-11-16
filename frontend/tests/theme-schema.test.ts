import { describe, it, expect } from "vitest";
import {
  DTCGTokenSchema,
  DesignTokensZodSchema,
  DEFAULT_THEME_TOKENS,
  extractCssVariablesFromTokens,
} from "@/lib/builder/theme-schema";

describe("Frontend DTCG Design Tokens (Zod & CSS Variables)", () => {
  it("validates valid DTCG token objects", () => {
    const validColor = {
      $value: "#059669",
      $type: "color",
      $description: "Emerald primary",
    };
    const parsed = DTCGTokenSchema.safeParse(validColor);
    expect(parsed.success).toBe(true);
    if (parsed.success) {
      expect(parsed.data.$value).toBe("#059669");
      expect(parsed.data.$type).toBe("color");
    }
  });

  it("validates full DesignTokens document with primitive, semantic, and component groups", () => {
    const parsed = DesignTokensZodSchema.safeParse(DEFAULT_THEME_TOKENS);
    expect(parsed.success).toBe(true);
  });

  it("extracts CSS variables map for CanvasFrame injection", () => {
    const customTokens = {
      ...DEFAULT_THEME_TOKENS,
      semantic: {
        ...DEFAULT_THEME_TOKENS.semantic,
        color: {
          primary: { $value: "#10b981", $type: "color" },
          secondary: { $value: "#0d9488", $type: "color" },
        },
        dimension: {
          radius: { $value: "14px", $type: "dimension" },
        },
      },
    };

    const vars = extractCssVariablesFromTokens(customTokens);
    expect(vars["--primary"]).toBe("#10b981");
    expect(vars["--secondary"]).toBe("#0d9488");
    expect(vars["--radius"]).toBe("14px");
  });

  it("handles fallback defaults gracefully when groups are empty", () => {
    const vars = extractCssVariablesFromTokens({ primitive: {}, semantic: {}, component: {} });
    expect(vars["--primary"]).toBeDefined();
    expect(vars["--radius"]).toBeDefined();
  });
});
