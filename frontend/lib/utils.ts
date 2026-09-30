import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/**
 * Convert English digits to Persian digits.
 */
export function toPersianDigits(value: string | number): string {
  const persianDigits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  return String(value).replace(/\d/g, (d) => persianDigits[parseInt(d)]!);
}

/**
 * Convert Persian and Arabic digits to English digits.
 */
export function toEnglishDigits(value: string): string {
  const persianDigits = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
  const arabicDigits = ["٠", "١", "٢", "٣", "٤", "٥", "٦", "٧", "٨", "٩"];
  return value
    .replace(/[۰-۹]/g, (char) => String(persianDigits.indexOf(char)))
    .replace(/[٠-٩]/g, (char) => String(arabicDigits.indexOf(char)));
}

/**
 * Normalizes any Iranian mobile number format into 09xxxxxxxxx.
 * Handles:
 * - Persian/Arabic digits: ۰۹۱۲۳۴۵۶۷۸۹ -> 09123456789
 * - International prefix: +989123456789, 00989123456789, 989123456789 -> 09123456789
 * - Missing leading zero: 9123456789 -> 09123456789
 * - Hidden RTL/bidi marks (\u200B-\u200D, \uFEFF, \u200E, \u200F, \u202A-\u202E)
 * - Separators: spaces, dashes, dots, parentheses
 */
export function normalizeIranPhone(phone: string): string {
  if (!phone) return "";
  // 1. Strip hidden bidi marks, whitespace, hyphens, dots, parentheses
  let cleaned = String(phone)
    .replace(/[\u200B-\u200D\uFEFF\u200E\u200F\u202A-\u202E]/g, "")
    .replace(/[\s\-\(\)\.]+/g, "")
    .trim();

  // 2. Convert Persian & Arabic digits to English digits
  cleaned = toEnglishDigits(cleaned);

  // 3. Strip leading plus
  if (cleaned.startsWith("+")) {
    cleaned = cleaned.slice(1);
  }

  // 4. Normalize international and local prefixes
  if (cleaned.startsWith("0098")) {
    cleaned = "0" + cleaned.slice(4);
  } else if (cleaned.startsWith("98") && cleaned.length === 12) {
    cleaned = "0" + cleaned.slice(2);
  } else if (cleaned.startsWith("9") && cleaned.length === 10) {
    cleaned = "0" + cleaned;
  }

  return cleaned;
}

/**
 * Validate Iranian mobile number (09xxxxxxxxx).
 */
export function isValidIranPhone(phone: string): boolean {
  const normalized = normalizeIranPhone(phone);
  return /^09\d{9}$/.test(normalized);
}

/**
 * Format an integer Toman amount with Persian grouping and a تومان suffix.
 *
 * Catalog/list product prices are already Toman in API responses. Checkout
 * quotes, order totals, payment.amount, cart price_snapshot, and shipping
 * quotes are still integer Rials — convert at the call site with
 * Math.trunc(rial / 10) before passing them here. Never divide inside this
 * helper. For raw Rial labels (admin/internal), use formatRial().
 */
export function formatPrice(price: number): string {
  const formatted = new Intl.NumberFormat("fa-IR").format(Math.trunc(price));
  return `${formatted} تومان`;
}

/**
 * Format a raw Rial amount with Rial label.
 * Use only for internal/admin views that bypass toman conversion.
 */
export function formatRial(priceRial: number): string {
  const formatted = new Intl.NumberFormat("fa-IR").format(Math.trunc(priceRial));
  return `${formatted} ریال`;
}

/**
 * Parse a Persian/Arabic-digit price string back to an integer.
 * Strips separators, currency labels, and non-digit chars.
 * Returns integer (never float) — NaN if unparseable.
 */
export function parsePrice(display: string): number {
  const english = toEnglishDigits(display)
    .replace(/[^\d-]/g, "");
  const n = parseInt(english, 10);
  return Number.isNaN(n) ? NaN : n;
}

/**
 * Safe integer money math — prevents floating-point drift.
 * All amounts must be integer Toman (API) or Rial (DB) throughout the system.
 */
export function safeMoneyAdd(a: number, b: number): number {
  return Math.trunc(a) + Math.trunc(b);
}

export function safeMoneyMultiply(amount: number, quantity: number): number {
  return Math.trunc(amount) * Math.trunc(quantity);
}

/**
 * Format a number with Persian locale.
 */
export function formatNumber(num: number): string {
  return new Intl.NumberFormat("fa-IR").format(num);
}

/**
 * Truncate text to a maximum length with ellipsis.
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}

/**
 * Generate a URL-safe slug from Persian or English text.
 */
export function slugify(text: string): string {
  return text
    .toLowerCase()
    .trim()
    .replace(/[\s\u200C]+/g, "-") // spaces and zero-width non-joiners
    .replace(/[^\w\u0600-\u06FF-]/g, "") // keep Persian chars, latin, digits, hyphens
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
}
