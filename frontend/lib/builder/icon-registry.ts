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
  path: string;
}

export const BUILDER_ICONS: Record<string, LucideIcon> = {
  star: Star,
  heart: Heart,
  "shield-check": ShieldCheck,
  shield: Shield,
  truck: Truck,
  headphones: Headphones,
  support: Headphones,
  award: Award,
  check: Check,
  zap: Zap,
  sparkles: Sparkles,
  clock: Clock,
  "credit-card": CreditCard,
  "shopping-cart": ShoppingCart,
  "shopping-bag": ShoppingBag,
  gift: Gift,
  phone: Phone,
  mail: Mail,
  "thumbs-up": ThumbsUp,
  "map-pin": MapPin,
  user: User,
  lock: Lock,
};

export const BUILDER_ICON_OPTIONS: IconOption[] = [
  { id: "star", label: "ستاره (Star)", icon: Star },
  { id: "heart", label: "قلب (Heart)", icon: Heart },
  { id: "shield-check", label: "ضمانت (Shield)", icon: ShieldCheck },
  { id: "truck", label: "ارسال سریع (Truck)", icon: Truck },
  { id: "headphones", label: "پشتیبانی (Support)", icon: Headphones },
  { id: "award", label: "نشان کیفیت (Award)", icon: Award },
  { id: "check", label: "تایید (Check)", icon: Check },
  { id: "zap", label: "سرعت (Zap)", icon: Zap },
  { id: "sparkles", label: "ویژه (Sparkles)", icon: Sparkles },
  { id: "clock", label: "زمان (Clock)", icon: Clock },
  { id: "credit-card", label: "پرداخت (Card)", icon: CreditCard },
  { id: "shopping-cart", label: "سبد خرید (Cart)", icon: ShoppingCart },
  { id: "shopping-bag", label: "فروشگاه (Bag)", icon: ShoppingBag },
  { id: "gift", label: "هدیه (Gift)", icon: Gift },
  { id: "phone", label: "تلفن (Phone)", icon: Phone },
  { id: "mail", label: "ایمیل (Mail)", icon: Mail },
  { id: "thumbs-up", label: "رضایت (Thumbs Up)", icon: ThumbsUp },
  { id: "map-pin", label: "آدرس (Location)", icon: MapPin },
  { id: "user", label: "کاربر (User)", icon: User },
  { id: "lock", label: "امنیت (Lock)", icon: Lock },
];

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

export function getIconSvgPath(name?: string | null): string {
  if (!name) return ICON_SVG_PATHS.star ?? "";
  const key = String(name).toLowerCase().trim();
  return ICON_SVG_PATHS[key] ?? ICON_SVG_PATHS.star ?? "";
}

export function getBuilderIcon(name?: string | null): LucideIcon {
  if (!name) return Sparkles;
  const key = String(name).toLowerCase().trim();
  return BUILDER_ICONS[key] || Sparkles;
}

export function getBuilderIconLabel(name?: string | null): string {
  if (!name) return "ستاره (Star)";
  const key = String(name).toLowerCase().trim();
  const option = BUILDER_ICON_OPTIONS.find((opt) => opt.id === key);
  return option ? option.label : key;
}
