import { toPersianDigits } from "./utils";

/**
 * Iranian Bank Shetab BIN mappings
 */
export interface ShetabBankInfo {
  bin: string;
  name: string;
  shortName: string;
  brandColor: string;
  logoEmoji: string;
}

export const SHETAB_BANKS: Record<string, ShetabBankInfo> = {
  "603799": { bin: "603799", name: "بانک ملی ایران", shortName: "ملی", brandColor: "#0047BA", logoEmoji: "🏛️" },
  "610433": { bin: "610433", name: "بانک ملت", shortName: "ملت", brandColor: "#E30613", logoEmoji: "🔴" },
  "621986": { bin: "621986", name: "بانک سامان", shortName: "سامان", brandColor: "#007A3D", logoEmoji: "🌿" },
  "502229": { bin: "502229", name: "بانک پاسارگاد", shortName: "پاسارگاد", brandColor: "#D4AF37", logoEmoji: "🟡" },
  "627353": { bin: "627353", name: "بانک تجارت", shortName: "تجارت", brandColor: "#002B49", logoEmoji: "🔷" },
  "589210": { bin: "589210", name: "بانک سپه", shortName: "سپه", brandColor: "#E2001A", logoEmoji: "🛡️" },
  "627412": { bin: "627412", name: "بانک اقتصاد نوین", shortName: "اقتصاد نوین", brandColor: "#5B2C83", logoEmoji: "🟣" },
  "603769": { bin: "603769", name: "بانک صادرات ایران", shortName: "صادرات", brandColor: "#172A68", logoEmoji: "🔵" },
  "622106": { bin: "622106", name: "بانک پارسیان", shortName: "پارسیان", brandColor: "#6B3923", logoEmoji: "🟤" },
  "636214": { bin: "636214", name: "بانک آینده", shortName: "آینده", brandColor: "#804A26", logoEmoji: "🟠" },
  "505416": { bin: "505416", name: "بانک گردشگری", shortName: "گردشگری", brandColor: "#64656A", logoEmoji: "✈️" },
  "639346": { bin: "639346", name: "بانک سینا", shortName: "سینا", brandColor: "#005596", logoEmoji: "🌐" },
  "502938": { bin: "502938", name: "بانک دی", shortName: "دی", brandColor: "#00857C", logoEmoji: "💠" },
};

/**
 * Validate Iranian Shetab card number using Luhn algorithm
 */
export function validateShetabCard(cardNumber: string): {
  isValid: boolean;
  bank?: ShetabBankInfo;
  cleanNumber: string;
} {
  const clean = cardNumber.replace(/\D/g, "");
  if (clean.length !== 16) {
    return { isValid: false, cleanNumber: clean };
  }

  // Luhn Checksum
  let sum = 0;
  for (let i = 0; i < 16; i++) {
    let digit = parseInt(clean[i]!, 10);
    if (i % 2 === 0) {
      digit *= 2;
      if (digit > 9) digit -= 9;
    }
    sum += digit;
  }

  const isValid = sum % 10 === 0;
  const bin = clean.substring(0, 6);
  const bank = SHETAB_BANKS[bin];

  return { isValid, bank, cleanNumber: clean };
}

/**
 * Format 16-digit card number with 4-digit groups
 */
export function formatCardNumber(cardNumber: string): string {
  const clean = cardNumber.replace(/\D/g, "").slice(0, 16);
  const parts = [];
  for (let i = 0; i < clean.length; i += 4) {
    parts.push(clean.substring(i, i + 4));
  }
  return parts.join(" - ");
}

/**
 * Validate Iranian National ID (کد ملی)
 */
export function validateNationalId(nationalId: string): boolean {
  const clean = nationalId.replace(/\D/g, "");
  if (clean.length !== 10) return false;

  // Reject repetition of identical digits
  if (/^(\d)\1{9}$/.test(clean)) return false;

  const check = parseInt(clean[9]!, 10);
  let sum = 0;
  for (let i = 0; i < 9; i++) {
    sum += parseInt(clean[i]!, 10) * (10 - i);
  }

  const remainder = sum % 11;
  return (remainder < 2 && check === remainder) || (remainder >= 2 && check === 11 - remainder);
}

/**
 * Validate and format Iranian mobile number (09xx xxx xxxx)
 */
export function validateIranianMobile(phone: string): boolean {
  const clean = phone.replace(/\D/g, "");
  return /^09\d{9}$/.test(clean);
}

export function formatIranianMobile(phone: string): string {
  const clean = phone.replace(/\D/g, "").slice(0, 11);
  if (clean.length <= 4) return clean;
  if (clean.length <= 7) return `${clean.slice(0, 4)} ${clean.slice(4)}`;
  return `${clean.slice(0, 4)} ${clean.slice(4, 7)} ${clean.slice(7)}`;
}

/**
 * Validate and format 10-digit Iranian postal code
 */
export function validatePostalCode(postalCode: string): boolean {
  const clean = postalCode.replace(/\D/g, "");
  // Postal code must be 10 digits and not start with 0 or 2 per post office rules
  return /^[13-9]\d{9}$/.test(clean);
}

export function formatPostalCode(postalCode: string): string {
  const clean = postalCode.replace(/\D/g, "").slice(0, 10);
  if (clean.length <= 5) return clean;
  return `${clean.slice(0, 5)} - ${clean.slice(5)}`;
}

/**
 * Delivery slot model
 */
export interface DeliverySlot {
  id: string;
  dayName: string;
  dateStr: string;
  timeRange: string;
  cost: number;
  isExpress?: boolean;
}

/**
 * Generate real-world delivery slots for the upcoming 3 days.
 * Day names and dates are computed from the current date (Jalali calendar)
 * so the slots are accurate on every day of the year.
 */
export function getAvailableDeliverySlots(): DeliverySlot[] {
  const dayFormatter = new Intl.DateTimeFormat("fa-IR", { weekday: "long" });
  const dateFormatter = new Intl.DateTimeFormat("fa-IR", {
    day: "numeric",
    month: "long",
  });

  const dayLabel = (offsetDays: number): { dayName: string; dateStr: string } => {
    const d = new Date();
    d.setDate(d.getDate() + offsetDays);
    const weekday = dayFormatter.format(d);
    const prefix = offsetDays === 1 ? `فردا (${weekday})` : offsetDays === 2 ? `پس‌فردا (${weekday})` : weekday;
    return { dayName: prefix, dateStr: dateFormatter.format(d) };
  };

  const tomorrow = dayLabel(1);
  const dayAfter = dayLabel(2);
  const inThree = dayLabel(3);

  return [
    {
      id: "slot-1",
      dayName: tomorrow.dayName,
      dateStr: tomorrow.dateStr,
      timeRange: "۰۹:۰۰ الی ۱۳:۰۰",
      cost: 0,
      isExpress: false,
    },
    {
      id: "slot-2",
      dayName: tomorrow.dayName,
      dateStr: tomorrow.dateStr,
      timeRange: "۱۴:۰۰ الی ۱۸:۰۰",
      cost: 0,
      isExpress: false,
    },
    {
      id: "slot-3",
      dayName: tomorrow.dayName,
      dateStr: tomorrow.dateStr,
      timeRange: "۱۹:۰۰ الی ۲۲:۰۰ (تحویل شبانه)",
      cost: 25000,
      isExpress: true,
    },
    {
      id: "slot-4",
      dayName: dayAfter.dayName,
      dateStr: dayAfter.dateStr,
      timeRange: "۱۰:۰۰ الی ۱۵:۰۰",
      cost: 0,
      isExpress: false,
    },
    {
      id: "slot-5",
      dayName: inThree.dayName,
      dateStr: inThree.dateStr,
      timeRange: "۰۹:۰۰ الی ۱۳:۰۰",
      cost: 0,
      isExpress: false,
    },
  ];
}

/**
 * Formats price into human friendly Toman units
 * e.g., 65000000 -> "۶۵ میلیون تومان"
 */
export function formatTomanHuman(price: number): string {
  if (price >= 1000000) {
    const millions = price / 1000000;
    const formatted = millions % 1 === 0 ? millions.toString() : millions.toFixed(1);
    return `${toPersianDigits(formatted)} میلیون تومان`;
  }
  if (price >= 1000) {
    const thousands = Math.round(price / 1000);
    return `${toPersianDigits(thousands)} هزار تومان`;
  }
  return `${toPersianDigits(price)} تومان`;
}

/**
 * Mock coupon validation engine
 */

