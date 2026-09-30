/**
 * Client-side PII Masking utilities for national ID and phone numbers.
 * Formats:
 *  - National ID: ***-****-011
 *  - Mobile Number: 0912***1234
 */

import { normalizeDigits } from "./dynamic-fields";

/**
 * Masks an Iranian national ID to the format `***-****-011`.
 * Displays the last 3 digits while masking the first 7 digits with asterisks and hyphens.
 */
export function maskNationalId(nationalId: string | null | undefined): string {
  if (!nationalId) return "";

  // Convert Persian/Arabic digits to ASCII and remove any non-digit chars
  const clean = normalizeDigits(String(nationalId)).replace(/\D/g, "");
  if (!clean) return "";

  if (clean.length >= 3) {
    const last3 = clean.slice(-3);
    return `***-****-${last3}`;
  }

  return "***-****-***";
}

/**
 * Masks an Iranian mobile phone number to the format `0912***1234`.
 * Preserves the first 4 digits (e.g. operator code) and the last 4 digits,
 * replacing the middle digits with `***`.
 */
export function maskPhoneNumber(phone: string | null | undefined): string {
  if (!phone) return "";

  // Normalize digits and remove non-digit characters
  let clean = normalizeDigits(String(phone)).replace(/\D/g, "");
  if (!clean) return "";

  // Handle +98 or 0098 international prefixes
  if (clean.startsWith("98") && clean.length === 12) {
    clean = "0" + clean.slice(2);
  } else if (clean.startsWith("0098") && clean.length === 14) {
    clean = "0" + clean.slice(4);
  } else if (clean.length === 10 && clean.startsWith("9")) {
    clean = "0" + clean;
  }

  if (clean.length === 11) {
    const prefix = clean.slice(0, 4);
    const suffix = clean.slice(-4);
    return `${prefix}***${suffix}`;
  }

  if (clean.length >= 7) {
    const prefix = clean.slice(0, Math.min(4, Math.floor(clean.length / 2)));
    const suffix = clean.slice(-Math.min(4, Math.ceil(clean.length / 2)));
    return `${prefix}***${suffix}`;
  }

  return clean;
}
