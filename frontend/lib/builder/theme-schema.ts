import { z } from "zod";

/**
 * Design Tokens Community Group (DTCG) Token Schema in Zod.
 */
export const DTCGTokenSchema = z.object({
  $value: z.any(),
  $type: z.enum([
    "color",
    "dimension",
    "fontFamily",
    "fontWeight",
    "duration",
    "cubicBezier",
    "number",
    "shadow",
  ]).or(z.string()).optional(),
  $description: z.string().optional(),
});

export type DTCGToken = z.infer<typeof DTCGTokenSchema>;

export const DesignTokensZodSchema = z.object({
  primitive: z.record(z.any()).default({}),
  semantic: z.record(z.any()).default({}),
  component: z.record(z.any()).default({}),
});

export type DesignTokensDocument = z.infer<typeof DesignTokensZodSchema>;

/**
 * Standard enterprise design tokens matching docs/UI_UX_DESIGN_SYSTEM.md
 */
export const DEFAULT_THEME_TOKENS: DesignTokensDocument = {
  primitive: {
    color: {
      emerald: {
        500: { $value: "#10b981", $type: "color" },
        600: { $value: "#059669", $type: "color" },
      },
      teal: {
        600: { $value: "#0d9488", $type: "color" },
      },
    },
    dimension: {
      radius: {
        sm: { $value: "6px", $type: "dimension" },
        md: { $value: "10px", $type: "dimension" },
        lg: { $value: "14px", $type: "dimension" },
      },
    },
    font: {
      vazirmatn: {
        $value: "var(--font-vazirmatn, system-ui, sans-serif)",
        $type: "fontFamily",
      },
    },
  },
  semantic: {
    color: {
      primary: { $value: "#059669", $type: "color", $description: "Brand Primary Emerald" },
      secondary: { $value: "#0d9488", $type: "color", $description: "Accent Teal" },
      background: { $value: "#ffffff", $type: "color" },
      foreground: { $value: "#09090b", $type: "color" },
    },
    dimension: {
      radius: { $value: "12px", $type: "dimension", $description: "Base Border Radius" },
    },
    typography: {
      fontFamily: { $value: "var(--font-vazirmatn, system-ui, sans-serif)", $type: "fontFamily" },
    },
  },
  component: {
    button: {
      radius: { $value: "10px", $type: "dimension" },
    },
  },
};

/**
 * Extract CSS variables map from design tokens for injection into CanvasFrame iframe :root
 */
export function extractCssVariablesFromTokens(tokens: DesignTokensDocument): Record<string, string> {
  const cssVars: Record<string, string> = {
    "--primary": "#059669",
    "--secondary": "#0d9488",
    "--radius": "12px",
    "--font-vazirmatn": "Vazirmatn, system-ui, sans-serif",
  };

  const semantic = tokens.semantic || {};

  // Resolve Primary
  if (semantic.color?.primary?.$value) {
    cssVars["--primary"] = String(semantic.color.primary.$value);
  }

  // Resolve Secondary
  if (semantic.color?.secondary?.$value) {
    cssVars["--secondary"] = String(semantic.color.secondary.$value);
  }

  // Resolve Radius
  if (semantic.dimension?.radius?.$value) {
    cssVars["--radius"] = String(semantic.dimension.radius.$value);
  }

  // Resolve Typography
  if (semantic.typography?.fontFamily?.$value) {
    cssVars["--font-vazirmatn"] = String(semantic.typography.fontFamily.$value);
  }

  return cssVars;
}
