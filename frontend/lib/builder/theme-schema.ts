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
      surface: { $value: "#f8fafc", $type: "color" },
      muted: { $value: "#f1f5f9", $type: "color" },
      border: { $value: "#e2e8f0", $type: "color" },
      input: { $value: "#e2e8f0", $type: "color" },
      ring: { $value: "#059669", $type: "color" },
      success: { $value: "#16a34a", $type: "color" },
      warning: { $value: "#f59e0b", $type: "color" },
      destructive: { $value: "#e11d48", $type: "color" },
      info: { $value: "#2563eb", $type: "color" },
    },
    dimension: {
      radius: { $value: "12px", $type: "dimension", $description: "Base Border Radius" },
      containerWidth: { $value: "1280px", $type: "dimension", $description: "Max Container Width" },
      contentWidth: { $value: "768px", $type: "dimension", $description: "Readable Content Width" },
      sectionSpacing: { $value: "64px", $type: "dimension", $description: "Vertical Section Spacing" },
      spacingScale: { $value: "16px", $type: "dimension", $description: "Base Spacing Unit" },
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

export function hexToHslChannels(hex: string): string {
  const clean = String(hex).trim().replace(/^#/, "");
  if (clean.length === 3) {
    const expanded = clean.split("").map((c) => c + c).join("");
    return hexToHslChannels("#" + expanded);
  }
  if (clean.length !== 6) return String(hex);
  const r = parseInt(clean.slice(0, 2), 16) / 255;
  const g = parseInt(clean.slice(2, 4), 16) / 255;
  const b = parseInt(clean.slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  let h = 0;
  let s = 0;
  const l = (max + min) / 2;
  if (max !== min) {
    const d = max - min;
    s = l > 0.5 ? d / (2 - max - min) : d / (max + min);
    switch (max) {
      case r:
        h = (g - b) / d + (g < b ? 6 : 0);
        break;
      case g:
        h = (b - r) / d + 2;
        break;
      case b:
        h = (r - g) / d + 4;
        break;
    }
    h /= 6;
  }
  return `${Math.round(h * 360)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

const ALIAS_PATTERN = /^\{([a-zA-Z0-9_.-]+)\}$/;

export class TokenCycleError extends Error {
  cyclePath: string[];

  constructor(cyclePath: string[]) {
    super(`Circular dependency detected in design token aliases: ${cyclePath.join(" -> ")}`);
    this.name = "TokenCycleError";
    this.cyclePath = cyclePath;
  }
}

function lookupPath(tree: any, pathParts: string[]): any {
  let current = tree;
  for (const part of pathParts) {
    if (current && typeof current === "object" && part in current) {
      current = current[part];
    } else {
      return null;
    }
  }
  return current;
}

/**
 * Resolve token aliases using a Directed Acyclic Graph (DAG) resolver with explicit cycle detection.
 */
export function resolveTokenValue(
  valueOrAlias: any,
  tokens: DesignTokensDocument,
  maxDepth = 10
): any {
  let currentVal = valueOrAlias;
  const visitedChain: string[] = [];

  while (typeof currentVal === "string" && ALIAS_PATTERN.test(currentVal.trim())) {
    const match = currentVal.trim().match(ALIAS_PATTERN);
    if (!match || !match[1]) break;
    const pathStr: string = match[1];

    if (visitedChain.includes(pathStr)) {
      const cycle = [...visitedChain, pathStr];
      throw new TokenCycleError(cycle);
    }

    if (visitedChain.length >= maxDepth) {
      throw new Error(`Max alias resolution depth of ${maxDepth} exceeded for ${valueOrAlias}`);
    }

    visitedChain.push(pathStr);
    const parts = pathStr.split(".");
    const rootKey = parts[0];

    let target: any = null;
    if (rootKey === "primitive") {
      target = lookupPath(tokens.primitive, parts.slice(1));
    } else if (rootKey === "semantic") {
      target = lookupPath(tokens.semantic, parts.slice(1));
    } else if (rootKey === "component") {
      target = lookupPath(tokens.component, parts.slice(1));
    } else {
      target = lookupPath(tokens.primitive, parts) || lookupPath(tokens.semantic, parts);
    }

    if (target === null || target === undefined) {
      throw new Error(`Unable to resolve design token alias: '${pathStr}'`);
    }

    if (typeof target === "object" && target !== null && ("$value" in target || "value" in target)) {
      currentVal = target.$value ?? target.value;
    } else {
      currentVal = target;
    }
  }

  return currentVal;
}

export const SHORTHAND_MAP: Record<string, string> = {
  "color.primary": "--primary",
  "color.secondary": "--secondary",
  "color.background": "--background",
  "color.foreground": "--foreground",
  "color.surface": "--surface",
  "color.muted": "--muted",
  "color.border": "--border",
  "color.input": "--input",
  "color.ring": "--ring",
  "color.success": "--success",
  "color.warning": "--warning",
  "color.destructive": "--destructive",
  "color.info": "--info",
  "dimension.radius": "--radius",
  "dimension.containerWidth": "--container-width",
  "dimension.contentWidth": "--content-width",
  "dimension.sectionSpacing": "--section-spacing",
  "dimension.spacingScale": "--spacing-scale",
  "typography.fontFamily": "--font-vazirmatn",
};

/**
 * Extract CSS variables map from design tokens for injection into CanvasFrame iframe :root.
 * Compiles all semantic and component tokens via DAG resolver.
 */
export function extractCssVariablesFromTokens(tokens: DesignTokensDocument): Record<string, string> {
  const cssVars: Record<string, string> = {
    "--primary": "#059669",
    "--secondary": "#0d9488",
    "--background": "#ffffff",
    "--foreground": "#09090b",
    "--surface": "#f8fafc",
    "--muted": "#f1f5f9",
    "--border": "#e2e8f0",
    "--input": "#e2e8f0",
    "--ring": "#059669",
    "--success": "#16a34a",
    "--warning": "#f59e0b",
    "--destructive": "#e11d48",
    "--info": "#2563eb",
    "--radius": "12px",
    "--font-vazirmatn": "Vazirmatn, system-ui, sans-serif",
  };

  function walk(d: any, prefix: string[]): Array<{ path: string[]; value: any }> {
    const items: Array<{ path: string[]; value: any }> = [];
    if (!d || typeof d !== "object") return items;

    if ("$value" in d || "value" in d) {
      items.push({ path: prefix, value: d.$value ?? d.value });
    } else {
      for (const [k, v] of Object.entries(d)) {
        items.push(...walk(v, [...prefix, k]));
      }
    }
    return items;
  }

  // 1. Process Semantic Tokens
  for (const item of walk(tokens.semantic || {}, [])) {
    let resolved: string;
    try {
      resolved = String(resolveTokenValue(item.value, tokens));
    } catch {
      resolved = String(item.value);
    }

    const key2 = item.path.slice(0, 2).join(".");
    if (SHORTHAND_MAP[key2]) {
      cssVars[SHORTHAND_MAP[key2]] = resolved;
    }

    const kebab = "--" + item.path.join("-").replace(/_/g, "-");
    cssVars[kebab] = resolved;
  }

  // 2. Process Component Tokens
  for (const item of walk(tokens.component || {}, [])) {
    let resolved: string;
    try {
      resolved = String(resolveTokenValue(item.value, tokens));
    } catch {
      resolved = String(item.value);
    }

    const kebab = "--" + item.path.join("-").replace(/_/g, "-");
    cssVars[kebab] = resolved;
  }

  return cssVars;
}
