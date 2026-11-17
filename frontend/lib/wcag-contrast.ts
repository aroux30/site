/**
 * WCAG 2.1 Color Contrast Utilities (Phase P5).
 *
 * Implements relative luminance calculation and contrast ratio assessment
 * per W3C WCAG 2.1 Recommendation (Section 1.4.3 Contrast Minimum).
 */

export interface RGB {
  r: number;
  g: number;
  b: number;
}

/**
 * Parses a hex color string (e.g. #fff, #ffffff, #059669) to RGB.
 * Returns null if invalid.
 */
export function hexToRgb(hex: string): RGB | null {
  const clean = hex.trim().replace(/^#/, "");
  if (clean.length === 3) {
    const c0 = clean[0] || "0";
    const c1 = clean[1] || "0";
    const c2 = clean[2] || "0";
    const r = parseInt(c0 + c0, 16);
    const g = parseInt(c1 + c1, 16);
    const b = parseInt(c2 + c2, 16);
    return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
  }
  if (clean.length === 6) {
    const r = parseInt(clean.slice(0, 2), 16);
    const g = parseInt(clean.slice(2, 4), 16);
    const b = parseInt(clean.slice(4, 6), 16);
    return isNaN(r) || isNaN(g) || isNaN(b) ? null : { r, g, b };
  }
  return null;
}

/**
 * Calculate the relative luminance of a color in sRGB space.
 * per W3C formula: L = 0.2126 * R + 0.7152 * G + 0.0722 * B
 */
export function getRelativeLuminance(rgb: RGB): number {
  const transform = (val: number) => {
    const s = val / 255;
    return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
  };

  const r = transform(rgb.r);
  const g = transform(rgb.g);
  const b = transform(rgb.b);

  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/**
 * Calculates the WCAG contrast ratio between two hex colors.
 * Formula: (L1 + 0.05) / (L2 + 0.05) where L1 is the lighter color.
 * Returns ratio e.g. 4.5 for 4.5:1, or null if color parsing fails.
 */
export function getContrastRatio(hex1: string, hex2: string): number | null {
  const rgb1 = hexToRgb(hex1);
  const rgb2 = hexToRgb(hex2);
  if (!rgb1 || !rgb2) return null;

  const lum1 = getRelativeLuminance(rgb1);
  const lum2 = getRelativeLuminance(rgb2);

  const lighter = Math.max(lum1, lum2);
  const darker = Math.min(lum1, lum2);

  const ratio = (lighter + 0.05) / (darker + 0.05);
  return Number(ratio.toFixed(2));
}

export interface WCAGComplianceResult {
  ratio: number;
  isNormalTextAA: boolean; // >= 4.5:1
  isLargeTextAA: boolean; // >= 3.0:1
  isNormalTextAAA: boolean; // >= 7.0:1
  isLargeTextAAA: boolean; // >= 4.5:1
}

/**
 * Checks compliance with WCAG 2.1 AA and AAA standards.
 */
export function checkWcagCompliance(foregroundHex: string, backgroundHex: string): WCAGComplianceResult | null {
  const ratio = getContrastRatio(foregroundHex, backgroundHex);
  if (ratio === null) return null;

  return {
    ratio,
    isNormalTextAA: ratio >= 4.5,
    isLargeTextAA: ratio >= 3.0,
    isNormalTextAAA: ratio >= 7.0,
    isLargeTextAAA: ratio >= 4.5,
  };
}
