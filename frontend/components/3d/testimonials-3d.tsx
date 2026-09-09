"use client";

import React from "react";
import { Star, CheckCircle2, Quote } from "lucide-react";
import { TiltCard3D } from "./tilt-card-3d";
import { toPersianDigits } from "@/lib/utils";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";

interface TestimonialItem {
  id: string;
  name: string;
  avatarInitial: string;
  role: string;
  purchasedProduct: string;
  rating: number;
  date: string;
  comment: string;
}

const TESTIMONIALS: TestimonialItem[] = [
  {
    id: "t1",
    name: "محمدرضا کاظمی",
    avatarInitial: "م",
    role: "برنامه‌نویس ارشد",
    purchasedProduct: "لپ‌تاپ ایسوس ROG Zephyrus G16",
    rating: 5,
    date: "۱۴ شهریور ۱۴۰۳",
    comment:
      "سرعت ارسال و بسته‌بندی عالی بود. برای کار سنگین برنامه‌نویسی و رندرهای هوش مصنوعی خریدم و عملکرد دستگاه با توضیحات سایت ۱۰۰٪ منطبق بود. گارانتی رسمی شرکتی هم سریع فعال شد.",
  },
  {
    id: "t2",
    name: "سارا نیکنام",
    avatarInitial: "س",
    role: "طراح UI/UX و معمار گرافیک",
    purchasedProduct: "گوشی موبایل سامسونگ Galaxy S24 Ultra",
    rating: 5,
    date: "۱۰ شهریور ۱۴۰۳",
    comment:
      "کیفیت ساخت و دوربین شگفت‌انگیزه! قابلیت‌های Galaxy AI برای ترجمه و خلاصه‌سازی متون توی پروژه‌های طراحی واقعاً کاربردیه. از پشتیبانی خوب و پاسخگویی سریع فروشگاه کمال تشکر رو دارم.",
  },
  {
    id: "t3",
    name: "امیرحسین رضوی",
    avatarInitial: "ا",
    role: "تهیه‌کننده محتوا و پادکستر",
    purchasedProduct: "هدفون بی‌سیم سونی WH-1000XM5",
    rating: 5,
    date: "۲ شهریور ۱۴۰۳",
    comment:
      "سکوت عجیبی که نویزکنسلینگ این هدفون ایجاد می‌کنه بی‌رقیبه! توی شلوغی کافه و استودیو بدون هیچ حواس‌پرتی روی ضبط و ادیت تمرکز می‌کنم. اصالت کالا کاملاً مورد تایید بود.",
  },
];

export function Testimonials3D() {
  return (
    <section className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-2 border-b border-border pb-4">
        <div>
          <h2 className="text-xl sm:text-2xl font-black text-foreground flex items-center gap-2.5">
            <span className="h-6 w-2 rounded-full bg-primary inline-block shadow-sm shadow-primary/40" />
            نظرات و تجربیات مشتریان واقعی (Social Proof)
          </h2>
          <p className="text-xs sm:text-sm text-muted-foreground mt-1">
            بیش از ۵۰,۰۰۰ سفارش موفق با بازخورد مثبت و رضایت ۹۹ درصدی
          </p>
        </div>
        <div className="flex items-center gap-1 text-amber-500 font-bold text-sm">
          <Star className="h-4 w-4 fill-amber-400" />
          <span>امتیاز ۴.۹ از ۵ بر اساس رضایت خریداران</span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {TESTIMONIALS.map((t) => (
          <TiltCard3D
            key={t.id}
            maxTilt={8}
            className="flex flex-col justify-between p-6 bg-card/90 border-border/80 hover:border-primary/50 transition-all duration-300"
          >
            <div className="space-y-4">
              {/* Top Row: User Avatar & Quote Icon */}
              <div className="flex items-start justify-between">
                <div className="flex items-center gap-3">
                  <Avatar className="h-11 w-11 border-2 border-primary/20 bg-primary/10">
                    <AvatarFallback className="bg-primary/15 text-primary font-black text-sm">
                      {t.avatarInitial}
                    </AvatarFallback>
                  </Avatar>
                  <div>
                    <h4 className="text-sm font-bold text-foreground flex items-center gap-1.5">
                      {t.name}
                      <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                    </h4>
                    <span className="text-[11px] text-muted-foreground block">
                      {t.role}
                    </span>
                  </div>
                </div>
                <Quote className="h-7 w-7 text-primary/20 rotate-180" />
              </div>

              {/* Rating stars */}
              <div className="flex items-center gap-1 text-amber-400">
                {Array.from({ length: 5 }).map((_, i) => (
                  <Star
                    key={i}
                    className={`h-3.5 w-3.5 ${
                      i < t.rating ? "fill-amber-400" : "text-muted-foreground/30"
                    }`}
                  />
                ))}
              </div>

              {/* Comment text */}
              <p className="text-xs sm:text-sm text-foreground/85 leading-relaxed">
                «{t.comment}»
              </p>
            </div>

            {/* Bottom Product Verified Tag */}
            <div className="mt-6 pt-4 border-t border-border/60 flex items-center justify-between text-[11px]">
              <Badge variant="outline" className="bg-primary/5 text-primary border-primary/20 text-[10px]">
                خرید تاییدشده: {t.purchasedProduct}
              </Badge>
              <span className="text-muted-foreground">{toPersianDigits(t.date)}</span>
            </div>
          </TiltCard3D>
        ))}
      </div>
    </section>
  );
}
