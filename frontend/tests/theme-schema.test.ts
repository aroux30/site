import { describe, it, expect } from "vitest";
import {
  DTCGTokenSchema,
  DesignTokensZodSchema,
  DEFAULT_THEME_TOKENS,
  extractCssVariablesFromTokens,
  resolveTokenValue,
  TokenCycleError,
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

  it("resolves token aliases cleanly via DAG resolver", () => {
    const doc = {
      primitive: {
        color: {
          brand: {
            jade: { $value: "#059669", $type: "color" },
          },
        },
      },
      semantic: {
        color: {
          primary: { $value: "{primitive.color.brand.jade}", $type: "color" },
        },
      },
      component: {},
    };

    const resolved = resolveTokenValue("{primitive.color.brand.jade}", doc);
    expect(resolved).toBe("#059669");

    const vars = extractCssVariablesFromTokens(doc);
    expect(vars["--primary"]).toBe("#059669");
    expect(vars["--color-primary"]).toBe("#059669");
  });

  it("detects circular dependencies and throws TokenCycleError with path", () => {
    const cycleDoc = {
      primitive: {
        a: { $value: "{primitive.b}" },
        b: { $value: "{primitive.c}" },
        c: { $value: "{primitive.a}" },
      },
      semantic: {},
      component: {},
    };

    expect(() => resolveTokenValue("{primitive.a}", cycleDoc)).toThrow(TokenCycleError);
    try {
      resolveTokenValue("{primitive.a}", cycleDoc);
    } catch (e: any) {
      expect(e).toBeInstanceOf(TokenCycleError);
      expect(e.cyclePath).toEqual(["primitive.a", "primitive.b", "primitive.c", "primitive.a"]);
      expect(e.message).toContain("primitive.a -> primitive.b -> primitive.c -> primitive.a");
    }
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
      component: {
        button: {
          radius: { $value: "8px", $type: "dimension" },
        },
      },
    };

    const vars = extractCssVariablesFromTokens(customTokens);
    expect(vars["--primary"]).toBe("#10b981");
    expect(vars["--secondary"]).toBe("#0d9488");
    expect(vars["--radius"]).toBe("14px");
    expect(vars["--button-radius"]).toBe("8px");
  });

  it("handles fallback defaults gracefully when groups are empty", () => {
    const vars = extractCssVariablesFromTokens({ primitive: {}, semantic: {}, component: {} });
    expect(vars["--primary"]).toBeDefined();
    expect(vars["--radius"]).toBeDefined();
  });
});
