/**
 * Scoped CSS Resolver with {{WRAPPER}} placeholder replacement (Elementor Pro Parity).
 *
 * In Elementor, custom CSS rules use {{WRAPPER}} as a selector token that is dynamically
 * replaced with the unique element ID / class selector of the active block, ensuring
 * that custom CSS never leaks to other elements or the parent window.
 */

/**
 * Sanitizes CSS text to prevent tag breakouts, script execution, or insecure imports.
 */
export function sanitizeScopedCss(css: string): string {
  if (!css || typeof css !== "string") return "";
  const clean = css
    // Strip HTML style or script tags to prevent DOM breakout
    .replace(/<\/?style[^>]*>/gi, "")
    .replace(/<\/?script[^>]*>/gi, "")
    // Block @import directives (prevent external asset / SSRF leaks)
    .replace(/@import\s+[^;]+;?/gi, "")
    // Block IE expressions and javascript pseudo-protocol URLs
    .replace(/expression\s*\([^)]*\)/gi, "")
    .replace(/url\s*\(\s*["']?javascript:[^"')]*["']?\s*\)/gi, "")
    // Block HTC behavior bindings
    .replace(/behavior\s*:[^;]+;?/gi, "");
  return clean.trim();
}

export function resolveScopedCss(
  cssText: string | null | undefined,
  elementId: string
): string {
  if (!cssText || typeof cssText !== "string") return "";

  const sanitized = sanitizeScopedCss(cssText);
  if (!sanitized) return "";

  // The wrapper selector targets data-element-id inside Canvas and matches #id/data-element-id safely
  const wrapperSelector = `[data-element-id="${elementId}"]`;

  // Support both {{WRAPPER}} and Elementor's `selector` keyword cleanly (when used as CSS selector token)
  const resolved = sanitized
    .replace(/\{\{\s*WRAPPER\s*\}\}/gi, wrapperSelector)
    .replace(/(^|[},;\s>+~])selector(?=\s*(?:[.{:[,>+~\s]|$))/gi, `$1${wrapperSelector}`);

  return resolved;
}
