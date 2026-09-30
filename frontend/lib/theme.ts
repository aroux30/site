/**
 * Server-side theme token loader: turns the admin-editable `theme` single
 * type into CSS custom properties injected on <html>. The admin ThemeEditor
 * (admin/cms) previously saved tokens that no storefront code ever read —
 * this is the consumer that makes "edit without a deploy" true.
 */

import { apiInternalUrl } from "@/lib/api/server-base";

const API_BASE = apiInternalUrl();

export interface ThemeTokens {
  colors: Record<string, string>;
  radius?: string;
  dark_mode_default?: boolean;
}

export async function fetchThemeTokens(): Promise<ThemeTokens | null> {
  try {
    const res = await fetch(`${API_BASE}/content/single-types/theme`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return null;
    const doc = (await res.json()) as { value?: ThemeTokens };
    return doc.value ?? null;
  } catch {
    return null;
  }
}

function hexToHsl(hex: string): string | null {
  const m = /^#([0-9a-fA-F]{6})$/.exec(hex.trim());
  if (!m || !m[1]) return null;
  const r = parseInt(m[1].slice(0, 2), 16) / 255;
  const g = parseInt(m[1].slice(2, 4), 16) / 255;
  const b = parseInt(m[1].slice(4, 6), 16) / 255;
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const l = (max + min) / 2;
  const d = max - min;
  let h = 0;
  if (d !== 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  const s = d === 0 ? 0 : d / (1 - Math.abs(2 * l - 1));
  return `${Math.round(h)} ${Math.round(s * 100)}% ${Math.round(l * 100)}%`;
}

const COLOR_TO_VAR: Record<string, string> = {
  primary: "--primary",
  secondary: "--secondary",
  accent: "--accent",
  background: "--background",
  surface: "--card",
  text: "--foreground",
  muted: "--muted-foreground",
};

/** Serialize theme tokens into a style object applied on the <html> element. */
export function themeStyleVars(tokens: ThemeTokens | null): Record<string, string> {
  if (!tokens) return {};
  const vars: Record<string, string> = {};
  for (const [key, hex] of Object.entries(tokens.colors ?? {})) {
    const varName = COLOR_TO_VAR[key];
    const hsl = hexToHsl(hex);
    if (varName && hsl) vars[varName] = hsl;
  }
  if (tokens.radius) vars["--radius"] = tokens.radius;
  return vars;
}
