import React from "react";
import {
  Star,
  Heart,
  ShieldCheck,
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

export const BUILDER_ICONS: Record<string, LucideIcon> = {
  star: Star,
  heart: Heart,
  "shield-check": ShieldCheck,
  truck: Truck,
  headphones: Headphones,
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

export function getBuilderIcon(name?: string | null): LucideIcon {
  if (!name) return Sparkles;
  const key = String(name).toLowerCase().trim();
  return BUILDER_ICONS[key] || Sparkles;
}
