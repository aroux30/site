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
 * Validate Iranian mobile number (09xxxxxxxxx).
 */
export function isValidIranPhone(phone: string): boolean {
  const cleanPhone = toEnglishDigits(phone.trim());
  return /^09\d{9}$/.test(cleanPhone);
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
