"use client";

/** Storefront-side half of the customizer live preview (WordPress
 *  "customizer" parity). Mounted in the root layout; the admin theme editor
 *  streams {type:"theme-preview", tokens} into the preview iframe via
 *  postMessage. Only the parent window is trusted (the iframe is same-origin
 *  and embedded by admin), and every color is re-validated as #RRGGBB here —
 *  the receiving side must not trust the sender's shape either. */

import { useEffect } from "react";

const COLOR_TO_VAR: Record<string, string> = {
  primary: "--primary",
  secondary: "--secondary",
  accent: "--accent",
  background: "--background",
  surface: "--card",
  text: "--foreground",
  muted: "--muted-foreground",
};

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

/** Radius arrives from the same admin control set the ThemeEditor writes
 *  (e.g. "0.5rem", "8px"); anything containing a character a CSS value could
 *  smuggle through (;, {, }) is dropped rather than set. */
const RADIUS_RE = /^[0-9a-zA-Z.\- ]+$/;

export function ThemePreviewBridge() {
  useEffect(() => {
    const onMessage = (event: MessageEvent) => {
      if (event.source !== window.parent) return;
      const data = event.data as { type?: string; tokens?: unknown } | null;
      if (!data || data.type !== "theme-preview") return;
      const c = (data.tokens ?? {}) as { colors?: Record<string, unknown>; radius?: unknown };
      if (typeof c.colors !== "object" || c.colors === null) return;
      const style = document.documentElement.style;
      for (const [key, raw] of Object.entries(c.colors)) {
        const varName = COLOR_TO_VAR[key];
        if (!varName || typeof raw !== "string") continue;
        const hsl = hexToHsl(raw);
        if (hsl) style.setProperty(varName, hsl);
      }
      if (typeof c.radius === "string" && RADIUS_RE.test(c.radius.trim()))
        style.setProperty("--radius", c.radius.trim());
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);
  return null;
}
