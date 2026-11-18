/**
 * Safe CSS Color and HEX normalization utilities (Phase P5 Hardening).
 *
 * Solves:
 * 1. Safe hex values for `<input type="color" value={...}>` (strictly `#rrggbb`).
 * 2. Normalization of Tailwind space-separated HSL variables (e.g. `var(--primary)`
 *    where `--primary` is `160 84% 39%`) so inline styles using `hsl(var(--primary))`
 *    never evaluate as invalid CSS.
 */

const KNOWN_TOKEN_FALLBACKS: Record<string, string> = {
  "var(--primary)": "#059669",
  "var(--secondary)": "#0d9488",
  "var(--background)": "#ffffff",
  "var(--foreground)": "#09090b",
  "var(--surface)": "#f8fafc",
  "var(--muted)": "#f1f5f9",
  "var(--border)": "#e2e8f0",
  "var(--ring)": "#059669",
  "var(--card)": "#ffffff",
  "--primary": "#059669",
  "--secondary": "#0d9488",
  "--background": "#ffffff",
  "--foreground": "#09090b",
};

/**
 * Returns a strict 7-character lowercase `#rrggbb` string acceptable by `<input type="color">`.
 * If given a token, var(), or invalid string, returns the provided fallback.
 */
export function toValidHexColor(val: unknown, fallback = "#059669"): string {
  if (typeof val !== "string" || !val.trim()) {
    return fallback;
  }
  const str = val.trim().toLowerCase();

  // Check known token fallbacks first
  if (KNOWN_TOKEN_FALLBACKS[str]) {
    return KNOWN_TOKEN_FALLBACKS[str]!;
  }

  // 3-digit hex #abc
  if (/^#[0-9a-f]{3}$/.test(str)) {
    return `#${str[1]}${str[1]}${str[2]}${str[2]}${str[3]}${str[3]}`;
  }

  // 6-digit hex #aabbcc
  if (/^#[0-9a-f]{6}$/.test(str)) {
    return str;
  }

  return fallback;
}

/**
 * Variables in Tailwind that contain space-separated HSL channels rather than direct hex.
 */
const HSL_CHANNEL_VARIABLES = new Set([
  "--primary",
  "--secondary",
  "--background",
  "--foreground",
  "--card",
  "--card-foreground",
  "--popover",
  "--popover-foreground",
  "--primary-foreground",
  "--secondary-foreground",
  "--muted",
  "--muted-foreground",
  "--accent",
  "--accent-foreground",
  "--destructive",
  "--destructive-foreground",
  "--success",
  "--success-foreground",
  "--warning",
  "--warning-foreground",
  "--info",
  "--info-foreground",
  "--border",
  "--input",
  "--ring",
]);

/**
 * Normalizes a color string for use in inline styles.
 * E.g., if a user selects `var(--primary)` from the chip picker, wraps it as `hsl(var(--primary))`
 * because `--primary` stores `160 84% 39%` in Tailwind, which would otherwise be invalid CSS.
 */
export function normalizeCssColor(color: unknown): string | undefined {
  if (typeof color !== "string" || !color.trim()) {
    return undefined;
  }
  const trimmed = color.trim();

  // If it's already wrapped in hsl(), rgb(), var(--theme-), linear-gradient, or is a hex, return as-is
  if (
    trimmed.startsWith("#") ||
    trimmed.startsWith("hsl(") ||
    trimmed.startsWith("hsla(") ||
    trimmed.startsWith("rgb(") ||
    trimmed.startsWith("rgba(") ||
    trimmed.startsWith("linear-gradient(") ||
    trimmed.startsWith("var(--theme-") ||
    trimmed.startsWith("var(--color-") ||
    trimmed === "transparent" ||
    trimmed === "currentColor" ||
    trimmed === "inherit"
  ) {
    return trimmed;
  }

  // If it's `var(--...)`, check if it targets an HSL channel variable
  const varMatch = trimmed.match(/^var\((--[a-zA-Z0-9_-]+)(?:,[^)]+)?\)$/);
  if (varMatch && varMatch[1] && HSL_CHANNEL_VARIABLES.has(varMatch[1])) {
    return `hsl(${trimmed})`;
  }

  return trimmed;
}
