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
 * Format a number as Persian currency (Toman).
 */
export function formatPrice(price: number): string {
  const formatted = new Intl.NumberFormat("fa-IR").format(price);
  return `${formatted} تومان`;
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
