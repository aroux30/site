import type { Metadata } from "next";
import Link from "next/link";
import { RotateCcw, Clock, ShieldCheck, CheckCircle, HelpCircle, PackageX, Truck, ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "رویه و شرایط بازگشت کالا | فروشگاه آنلاین",
  description: "راهنمای گام به گام و شرایط ضمانت بازگشت ۷ روزه کالا و استرداد وجه در فروشگاه.",
};

export default function ReturnsPage() {
  const steps = [
    {
      number: "۱",
      title: "ثبت درخواست در پنل کاربری",
      desc: "وارد حساب کاربری خود شده، سفارش مربوطه را انتخاب نمایید و درخواست مرجوعی کالا را همراه با علت و تصویر ثبت فرمایید.",
      icon: Clock,
    },
    {
      number: "۲",
      title: "بررسی و هماهنگی پشتیبانی",
      desc: "کارشناسان خدمات پس از فروش ظرف حداکثر ۲۴ ساعت کاری درخواست را بررسی و جهت هماهنگی دریافت کالا با شما تماس می‌گیرند.",
      icon: ShieldCheck,
    },
    {
      number: "۳",
      title: "ارسال کالا به انبار مرکزی",
      desc: "کالا را در بسته‌بندی اولیه و ضدضربه به آدرس انبار مرکزی فروشگاه از طریق پست پیشتاز یا پیک ارسال فرمایید.",
      icon: Truck,
    },
    {
      number: "۴",
      title: "تایید سلامت و عودت کامل وجه",
      desc: "پس از دریافت بسته و تایید کارشناسی، مبلغ کالا به کیف پول اعتباری شما یا شماره شبا بانکی واریز خواهد شد.",
      icon: CheckCircle,
    },
  ];

  return (
    <div className="container mx-auto px-4 py-12 max-w-5xl">
      {/* Hero Header */}
      <div className="text-center max-w-3xl mx-auto mb-16">
        <div className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-semibold mb-4 border border-emerald-500/20">
          <RotateCcw className="w-4 h-4" />
          ضمانت طلایی ۷ روزه بازگشت
        </div>
        <h1 className="text-3xl md:text-5xl font-black text-foreground mb-4">
          رویه بازگشت و استرداد کالا
        </h1>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
          آسودگی خاطر و رضایت ۱۰۰٪ شما اولویت ماست. تمام کالاهای فروشگاه مشمول ۷ روز ضمانت بازگشت و تعویض طبق قوانین رسمی می‌باشند.
        </p>
      </div>

      {/* 4 Steps Timeline */}
      <div className="mb-20">
        <h2 className="text-2xl font-bold text-center mb-10 text-foreground">
          مراحل ۴ گانه ثبت و عودت سفارش
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {steps.map((s, idx) => {
            const Icon = s.icon;
            return (
              <div
                key={idx}
                className="relative p-6 rounded-2xl bg-card border border-border shadow-sm hover:shadow-md transition-shadow flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-center justify-between mb-4">
                    <div className="w-12 h-12 rounded-xl bg-emerald-500/10 text-emerald-600 flex items-center justify-center font-black text-lg">
                      <Icon className="w-6 h-6" />
                    </div>
                    <span className="text-3xl font-black text-muted/60 dark:text-muted/30">
                      {s.number}
                    </span>
                  </div>
                  <h3 className="text-base font-bold text-foreground mb-2">
                    {s.title}
                  </h3>
                  <p className="text-xs text-muted-foreground leading-relaxed">
                    {s.desc}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Conditions & Guidelines */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-16">
        <div className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
            <CheckCircle className="w-5 h-5 text-emerald-600" />
            شرایط الزامی پذیرش مرجوعی
          </h3>
          <ul className="space-y-3 text-xs md:text-sm text-muted-foreground pr-2">
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0" />
              کالا باید در بسته‌بندی اصلی و اولیه همراه با کارتن، متعلقات و فاکتور باشد.
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0" />
              هرگونه مخدوش کردن جعبه، پاره شدن بارکد، نوشتن یادداشت روی کارتن اصلی مانع بازگشت کالا خواهد شد.
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0" />
              کالاهای الکترونیک نباید راه‌اندازی با حساب‌های شخصی (مانند Apple ID یا Google Account) شده باشند.
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 mt-2 shrink-0" />
              مهلت ثبت درخواست مرجوعی حداکثر ۷ روز تقویمی از لحظه تحویل مرسوله است.
            </li>
          </ul>
        </div>

        <div className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <h3 className="text-lg font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
            <PackageX className="w-5 h-5 text-rose-500" />
            کالاهایی که امکان بازگشت ندارند
          </h3>
          <ul className="space-y-3 text-xs md:text-sm text-muted-foreground pr-2">
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-2 shrink-0" />
              کدهای نرم‌افزاری دیجیتال، گیفت‌کارت‌ها و لایسنس‌های ارائه‌شده پس از تحویل آنی.
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-2 shrink-0" />
              اقلام بهداشتی شخصی و هدفون‌های داخل گوشی (In-ear) پس از باز شدن پلمپ بهداشتی.
            </li>
            <li className="flex items-start gap-2">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-500 mt-2 shrink-0" />
              کالاهایی که بر اثر نوسان برق، آب‌خوردگی، ضربه فیزیکی یا استفاده نادرست کاربر آسیب دیده‌اند.
            </li>
          </ul>
        </div>
      </div>

      {/* CTA Box */}
      <div className="p-8 rounded-3xl bg-gradient-to-l from-emerald-900 to-slate-900 text-white flex flex-col md:flex-row items-center justify-between gap-6 shadow-xl">
        <div>
          <h3 className="text-xl font-bold mb-2">نیاز به ثبت مرجوعی دارید؟</h3>
          <p className="text-slate-300 text-sm">
            از بخش سفارشات در پنل کاربری اقدام کنید یا مستقیماً با تیم پشتیبانی در ارتباط باشید.
          </p>
        </div>
        <div className="flex items-center gap-3 shrink-0">
          <Link href="/account">
            <Button className="bg-emerald-500 hover:bg-emerald-600 text-white font-bold gap-2">
              ورود به حساب و ثبت مرجوعی
              <ArrowLeft className="w-4 h-4" />
            </Button>
          </Link>
          <Link href="/contact">
            <Button variant="outline" className="border-white/20 text-white hover:bg-white/10">
              تماس با پشتیبانی
            </Button>
          </Link>
        </div>
      </div>
    </div>
  );
}
