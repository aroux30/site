import React from "react";
import {
  Truck,
  ShieldCheck,
  RotateCcw,
  CreditCard,
  Headphones,
  CheckCircle,
} from "lucide-react";

export interface TrustBadgeItem {
  icon: React.ComponentType<{ className?: string }>;
  title: string;
  description: string;
  badge?: string;
}

const DEFAULT_BADGES: TrustBadgeItem[] = [
  {
    icon: Truck,
    title: "ارسال سریع و اکسپرس",
    description: "تحویل فوق‌سریع در تهران و تمام شهرهای کشور",
    badge: "پوشش سراسری",
  },
  {
    icon: ShieldCheck,
    title: "ضمانت ۱۰۰٪ اصالت کالا",
    description: "فروش مستقیم کالای اورجینال با شناسه قانونی",
    badge: "تضمین اصل بودن",
  },
  {
    icon: RotateCcw,
    title: "۷ روز ضمانت بازگشت",
    description: "مهلت قانونی تست و استرداد آنی وجه به کیف پول",
    badge: "بدون قید و شرط",
  },
  {
    icon: CreditCard,
    title: "پرداخت امن شتاب و تتر",
    description: "درگاه‌های رسمی بانکی با رمزنگاری پیشرفته",
    badge: "شاپرک و کریپتو",
  },
  {
    icon: Headphones,
    title: "پشتیبانی ۲۴ ساعته",
    description: "پاسخگویی آنلاین کارشناسان در تمام ایام هفته",
    badge: "مشاوره رایگان",
  },
];

export function TrustBadgesSection({
  className = "",
  items = DEFAULT_BADGES,
}: {
  className?: string;
  items?: TrustBadgeItem[];
}) {
  return (
    <section className={`py-12 border-y border-border/60 bg-muted/20 ${className}`}>
      <div className="container mx-auto px-4 sm:px-6 max-w-7xl">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-6">
          {items.map((item, index) => {
            const Icon = item.icon;
            return (
              <div
                key={index}
                className="group relative rounded-2xl border border-border/60 bg-card/60 p-5 transition-all duration-300 hover:shadow-lg hover:border-emerald-500/40 hover:-translate-y-1 flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="p-3 rounded-2xl bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 group-hover:scale-110 transition-transform">
                      <Icon className="w-6 h-6" />
                    </div>
                    {item.badge && (
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20">
                        {item.badge}
                      </span>
                    )}
                  </div>
                  <h3 className="font-bold text-sm text-foreground mb-1.5 group-hover:text-emerald-600 dark:group-hover:text-emerald-400 transition-colors">
                    {item.title}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {item.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
