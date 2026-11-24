import React from "react";
import {
  Star,
  Heart,
  ShieldCheck,
  Shield,
  Truck,
  Headphones,
  Award,
  Check,
  Zap,
  Sparkles,
  Clock,
  CreditCard,
  ShoppingCart,
  ShoppingBag,
  Gift,
  Phone,
  Mail,
  ThumbsUp,
  MapPin,
  User,
  Lock,
  type LucideIcon,
} from "lucide-react";

export interface IconOption {
  id: string;
  label: string;
  icon: LucideIcon;
}

export interface IconDefinition {
  id: string;
  label: string;
  icon: LucideIcon;
  svgPath: string;
}

export const BUILDER_ICON_REGISTRY: Record<string, IconDefinition> = {
  star: {
    id: "star",
    label: "ستاره (Star)",
    icon: Star,
    svgPath:
      '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />',
  },
  heart: {
    id: "heart",
    label: "قلب (Heart)",
    icon: Heart,
    svgPath:
      '<path d="M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z" />',
  },
  "shield-check": {
    id: "shield-check",
    label: "ضمانت (Shield)",
    icon: ShieldCheck,
    svgPath:
      '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z" /><path d="m9 12 2 2 4-4" />',
  },
  shield: {
    id: "shield",
    label: "سپر (Shield)",
    icon: Shield,
    svgPath:
      '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />',
  },
  truck: {
    id: "truck",
    label: "ارسال سریع (Truck)",
    icon: Truck,
    svgPath:
      '<path d="M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2" /><path d="M15 18H9" /><path d="M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14" /><circle cx="17" cy="18.5" r="2.5" /><circle cx="7" cy="18.5" r="2.5" />',
  },
  headphones: {
    id: "headphones",
    label: "پشتیبانی (Support)",
    icon: Headphones,
    svgPath:
      '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3" />',
  },
  support: {
    id: "support",
    label: "پشتیبانی (Support)",
    icon: Headphones,
    svgPath:
      '<path d="M3 14h3a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-7a9 9 0 0 1 18 0v7a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3" />',
  },
  award: {
    id: "award",
    label: "نشان کیفیت (Award)",
    icon: Award,
    svgPath:
      '<circle cx="12" cy="8" r="6" /><path d="m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526" />',
  },
  check: {
    id: "check",
    label: "تایید (Check)",
    icon: Check,
    svgPath: '<path d="M20 6 9 17l-5-5" />',
  },
  zap: {
    id: "zap",
    label: "سرعت (Zap)",
    icon: Zap,
    svgPath: '<path d="M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z" />',
  },
  sparkles: {
    id: "sparkles",
    label: "ویژه (Sparkles)",
    icon: Sparkles,
    svgPath:
      '<path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" /><path d="M5 3v4" /><path d="M19 17v4" /><path d="M3 5h4" /><path d="M17 19h4" />',
  },
  clock: {
    id: "clock",
    label: "زمان (Clock)",
    icon: Clock,
    svgPath:
      '<circle cx="12" cy="12" r="10" /><polyline points="12 6 12 12 16 14" />',
  },
  "credit-card": {
    id: "credit-card",
    label: "پرداخت (Card)",
    icon: CreditCard,
    svgPath:
      '<rect width="20" height="14" x="2" y="5" rx="2" /><line x1="2" x2="22" y1="10" y2="10" />',
  },
  "shopping-cart": {
    id: "shopping-cart",
    label: "سبد خرید (Cart)",
    icon: ShoppingCart,
    svgPath:
      '<circle cx="8" cy="21" r="1" /><circle cx="19" cy="21" r="1" /><path d="M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12" />',
  },
  "shopping-bag": {
    id: "shopping-bag",
    label: "فروشگاه (Bag)",
    icon: ShoppingBag,
    svgPath:
      '<path d="M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z" /><path d="M3 6h18" /><path d="M16 10a4 4 0 0 1-8 0" />',
  },
  gift: {
    id: "gift",
    label: "هدیه (Gift)",
    icon: Gift,
    svgPath:
      '<rect x="3" y="8" width="18" height="4" rx="1" /><path d="M12 8v13" /><path d="M19 12v7a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-7" /><path d="M7.5 8a2.5 2.5 0 0 1 0-5A4.8 8 0 0 1 12 8a4.8 8 0 0 1 4.5-5 2.5 2.5 0 0 1 0 5" />',
  },
  phone: {
    id: "phone",
    label: "تلفن (Phone)",
    icon: Phone,
    svgPath:
      '<path d="M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z" />',
  },
  mail: {
    id: "mail",
    label: "ایمیل (Mail)",
    icon: Mail,
    svgPath:
      '<rect width="20" height="16" x="2" y="4" rx="2" /><path d="m22 7-8.97 5.7a1.94 1.94 0 0 1-2.06 0L2 7" />',
  },
  "thumbs-up": {
    id: "thumbs-up",
    label: "رضایت (Thumbs Up)",
    icon: ThumbsUp,
    svgPath:
      '<path d="M7 10v12" /><path d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z" />',
  },
  "map-pin": {
    id: "map-pin",
    label: "آدرس (Location)",
    icon: MapPin,
    svgPath:
      '<path d="M20 10c0 4.993-5.539 10.193-7.399 11.799a1 1 0 0 1-1.202 0C9.539 20.193 4 14.993 4 10a8 8 0 0 1 16 0" /><circle cx="12" cy="10" r="3" />',
  },
  user: {
    id: "user",
    label: "کاربر (User)",
    icon: User,
    svgPath:
      '<path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />',
  },
  lock: {
    id: "lock",
    label: "امنیت (Lock)",
    icon: Lock,
    svgPath:
      '<rect width="18" height="11" x="3" y="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />',
  },
};

export const BUILDER_ICONS: Record<string, LucideIcon> = Object.fromEntries(
  Object.entries(BUILDER_ICON_REGISTRY).map(([k, def]) => [k, def.icon])
);

export const BUILDER_ICON_OPTIONS: IconOption[] = Object.values(BUILDER_ICON_REGISTRY).map((def) => ({
  id: def.id,
  label: def.label,
  icon: def.icon,
}));

export const ICON_SVG_PATHS: Record<string, string> = {
  star: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  heart: "M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z",
  "shield-check": "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z M9 12l2 2 4-4",
  shield: "M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z",
  truck: "M1 3h15v13H1z M16 8h4l3 3v5h-7V8z M5.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z M18.5 21a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  headphones: "M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z",
  support: "M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3z M3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z",
  award: "M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14z M8.21 13.89L7 23l5-3 5 3-1.21-9.12",
  check: "M20 6L9 17l-5-5",
  zap: "M13 2L3 14h9l-1 8 10-12h-9l1-8z",
  sparkles: "M12 3l1.912 5.886a2 2 0 0 0 1.202 1.202L21 12l-5.886 1.912a2 2 0 0 0-1.202 1.202L12 21l-1.912-5.886a2 2 0 0 0-1.202-1.202L3 12l5.886-1.912a2 2 0 0 0 1.202-1.202L12 3z",
  clock: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
  "credit-card": "M1 4h22v16H1z M1 10h22",
  "shopping-cart": "M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6 M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M20 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2z",
  "shopping-bag": "M6 2L3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4z M3 6h18 M16 10a4 4 0 0 1-8 0",
  gift: "M20 12v10H4V12 M2 7h20v5H2z M12 22V7 M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z",
  phone: "M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z",
  mail: "M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z M22 6l-10 7L2 6",
  "thumbs-up": "M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3",
  "map-pin": "M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z M12 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
  user: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z",
  lock: "M19 11H5a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7a2 2 0 0 0-2-2z M7 11V7a5 5 0 0 1 10 0v4",
};

export function getBuilderIcon(name?: string | null): LucideIcon {
  if (!name) return Sparkles;
  const key = String(name).toLowerCase().trim();
  const entry = BUILDER_ICON_REGISTRY[key];
  return entry ? entry.icon : Sparkles;
}

const DEFAULT_SVG_PATH =
  '<polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />';

export function getBuilderIconSvgPath(name?: string | null): string {
  if (!name) return DEFAULT_SVG_PATH;
  const key = String(name).toLowerCase().trim();
  const entry = BUILDER_ICON_REGISTRY[key];
  return entry ? entry.svgPath : DEFAULT_SVG_PATH;
}

export function getIconSvgPath(name?: string | null): string {
  if (!name) return ICON_SVG_PATHS.star ?? "";
  const key = String(name).toLowerCase().trim();
  return ICON_SVG_PATHS[key] ?? ICON_SVG_PATHS.star ?? "";
}
