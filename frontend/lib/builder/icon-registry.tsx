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

export interface IconDefinition {
  id: string;
  label: string;
  component: LucideIcon;
  svgPath: string;
}

export const BUILDER_ICON_REGISTRY: Record<string, IconDefinition> = {
  star: {
    id: "star",
    label: "ستاره (Star)",
    component: Star,
    svgPath: "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z",
  },
  heart: {
    id: "heart",
    label: "قلب (Heart)",
    component: Heart,
    svgPath: "M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z",
  },
  "shield-check": {
    id: "shield-check",
    label: "ضمانت (Shield)",
    component: ShieldCheck,
    svgPath: "M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z M9 12l2 2 4-4",
  },
  truck: {
    id: "truck",
    label: "ارسال سریع (Truck)",
    component: Truck,
    svgPath: "M14 18V6a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v11a1 1 0 0 0 1 1h2 M15 18H9 M19 18h2a1 1 0 0 0 1-1v-3.65a1 1 0 0 0-.22-.624l-3.48-4.35A1 1 0 0 0 17.52 8H14",
  },
  headphones: {
    id: "headphones",
    label: "پشتیبانی (Support)",
    component: Headphones,
    svgPath: "M3 18v-6a9 9 0 0 1 18 0v6 M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z",
  },
  award: {
    id: "award",
    label: "نشان کیفیت (Award)",
    component: Award,
    svgPath: "m15.477 12.89 1.515 8.526a.5.5 0 0 1-.81.47l-3.58-2.687a1 1 0 0 0-1.197 0l-3.586 2.686a.5.5 0 0 1-.81-.469l1.514-8.526 M12 15a7 7 0 1 0 0-14 7 7 0 0 0 0 14z",
  },
  check: {
    id: "check",
    label: "تایید (Check)",
    component: Check,
    svgPath: "M20 6 9 17l-5-5",
  },
  zap: {
    id: "zap",
    label: "سرعت (Zap)",
    component: Zap,
    svgPath: "M4 14a1 1 0 0 1-.78-1.63l9.9-10.2a.5.5 0 0 1 .86.46l-1.92 6.02A1 1 0 0 0 13 10h7a1 1 0 0 1 .78 1.63l-9.9 10.2a.5.5 0 0 1-.86-.46l1.92-6.02A1 1 0 0 0 11 14z",
  },
  sparkles: {
    id: "sparkles",
    label: "ویژه (Sparkles)",
    component: Sparkles,
    svgPath: "m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z",
  },
  clock: {
    id: "clock",
    label: "زمان (Clock)",
    component: Clock,
    svgPath: "M12 22a10 10 0 1 0 0-20 10 10 0 0 0 0 20z M12 6v6l4 2",
  },
  "credit-card": {
    id: "credit-card",
    label: "پرداخت (Card)",
    component: CreditCard,
    svgPath: "M2 5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5z M2 10h20",
  },
  "shopping-cart": {
    id: "shopping-cart",
    label: "سبد خرید (Cart)",
    component: ShoppingCart,
    svgPath: "circle cx='8' cy='21' r='1' M19 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2z M2.05 2.05h2l2.66 12.42a2 2 0 0 0 2 1.58h9.78a2 2 0 0 0 1.95-1.57l1.65-7.43H5.12",
  },
  "shopping-bag": {
    id: "shopping-bag",
    label: "فروشگاه (Bag)",
    component: ShoppingBag,
    svgPath: "M6 2 3 6v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V6l-3-4Z M3 6h18 M16 10a4 4 0 0 1-8 0",
  },
  gift: {
    id: "gift",
    label: "هدیه (Gift)",
    component: Gift,
    svgPath: "M20 12v10H4V12 M2 7h20v5H2z M12 22V7 M12 7H7.5a2.5 2.5 0 0 1 0-5C11 2 12 7 12 7z M12 7h4.5a2.5 2.5 0 0 0 0-5C13 2 12 7 12 7z",
  },
  phone: {
    id: "phone",
    label: "تلفن (Phone)",
    component: Phone,
    svgPath: "M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z",
  },
  mail: {
    id: "mail",
    label: "ایمیل (Mail)",
    component: Mail,
    svgPath: "M22 6c0-1.1-.9-2-2-2H4c-1.1 0-2 .9-2 2v12c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V6zm-2 0-8 5-8-5h16zm0 12H4V8l8 5 8-5v10z",
  },
  "thumbs-up": {
    id: "thumbs-up",
    label: "پسندیدن (Thumbs Up)",
    component: ThumbsUp,
    svgPath: "M7 10v12 M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z",
  },
  "map-pin": {
    id: "map-pin",
    label: "موقعیت (Map Pin)",
    component: MapPin,
    svgPath: "M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z M12 10a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z",
  },
  user: {
    id: "user",
    label: "کاربر (User)",
    component: User,
    svgPath: "M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2 M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z",
  },
  lock: {
    id: "lock",
    label: "امنیت (Lock)",
    component: Lock,
    svgPath: "rect width='18' height='11' x='3' y='11' rx='2' ry='2' M7 11V7a5 5 0 0 1 10 0v4",
  },
};

export function getBuilderIcon(name: string): LucideIcon {
  const normalized = String(name || "").toLowerCase().trim();
  if (BUILDER_ICON_REGISTRY[normalized]) {
    return BUILDER_ICON_REGISTRY[normalized].component;
  }
  return Star;
}

export function getBuilderIconSvgPath(name: string): string {
  const normalized = String(name || "").toLowerCase().trim();
  if (BUILDER_ICON_REGISTRY[normalized]) {
    return BUILDER_ICON_REGISTRY[normalized].svgPath;
  }
  return BUILDER_ICON_REGISTRY["star"]?.svgPath || "M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z";
}

export function BuilderIconSvg({
  name,
  size = 24,
  className,
  style,
}: {
  name: string;
  size?: number;
  className?: string;
  style?: React.CSSProperties;
}) {
  const IconComponent = getBuilderIcon(name);
  return (
    <IconComponent
      size={size}
      className={className}
      style={style}
      aria-hidden="true"
    />
  );
}
