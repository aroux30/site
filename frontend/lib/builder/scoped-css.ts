/**
 * Scoped CSS Resolver with {{WRAPPER}} placeholder replacement (Elementor Pro Parity).
 *
 * In Elementor, custom CSS rules use {{WRAPPER}} as a selector token that is dynamically
 * replaced with the unique element ID / class selector of the active block, ensuring
 * that custom CSS never leaks to other elements or the parent window.
 */
export function resolveScopedCss(
  cssText: string | null | undefined,
  elementId: string
): string {
  if (!cssText || typeof cssText !== "string") return "";

  const trimmed = cssText.trim();
  if (!trimmed) return "";

  // The wrapper selector targets either the ID or the data-element-id
  const wrapperSelector = `[data-element-id="${elementId}"]`;

  // Replace case-insensitive {{WRAPPER}} with scoped selector
  const resolved = trimmed.replace(/\{\{\s*WRAPPER\s*\}\}/gi, wrapperSelector);

  return resolved;
}
