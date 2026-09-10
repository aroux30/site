import type { Metadata } from "next";
import { Shield, Lock, Eye, Server, Database, KeyRound, CheckCircle2 } from "lucide-react";

export const metadata: Metadata = {
  title: "سیاست حفظ حریم خصوصی | فروشگاه آنلاین",
  description: "خط‌مشی رازداری، حفظ حریم شخصی و نگهداری امن داده‌های کاربران در فروشگاه.",
};

export default function PrivacyPage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-4xl">
      {/* Header */}
      <div className="text-center mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-medium mb-4">
          <Shield className="w-4 h-4" />
          امنیت و صیانت از داده‌ها
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mb-4">
          سیاست حفظ حریم خصوصی
        </h1>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed max-w-2xl mx-auto">
          ما در این فروشگاه متعهد هستیم که از اطلاعات شخصی شما با بالاترین استانداردهای امنیتی، رمزنگاری پیشرفته و احترام به حقوق حریم خصوصی محافظت نماییم.
        </p>
      </div>

      <div className="space-y-8">
        {/* Section 1 */}
        <section className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400 font-bold text-lg">
            <Database className="w-5 h-5" />
            <h2>۱. چه اطلاعاتی را جمع‌آوری می‌کنیم؟</h2>
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            ما تنها اطلاعاتی را جمع‌آوری می‌کنیم که برای ثبت، پردازش و تحویل بی‌نقص سفارش شما ضروری هستند:
          </p>
          <ul className="list-disc list-inside text-muted-foreground text-sm space-y-2 pr-2">
            <li>اطلاعات هویتی و تماسی: نام و نام خانوادگی، شماره تلفن همراه، آدرس ایمیل.</li>
            <li>اطلاعات پستی و تحویل: نشانی دقیق گیرنده، کدپستی ده رقمی، استان و شهر.</li>
            <li>سوابق مالی: تاریخچه تراکنش‌ها و شناسه پیگیری درگاه‌های بانکی شتاب (اطلاعات کارت شما در درگاه امن بانکی ثبت شده و هرگز در سرورهای ما ذخیره نمی‌گردد).</li>
          </ul>
        </section>

        {/* Section 2 */}
        <section className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400 font-bold text-lg">
            <Eye className="w-5 h-5" />
            <h2>۲. چگونه از اطلاعات شما استفاده می‌کنیم؟</h2>
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            اطلاعات کاربران صرفاً در جهت بهبود تجربه خرید و اهداف زیر به کار گرفته می‌شود:
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2">
            <div className="p-4 rounded-xl bg-muted/40 border border-border/50 text-xs text-muted-foreground leading-relaxed">
              <span className="font-bold text-foreground block mb-1">پردازش و ارسال سریع سفارش</span>
              هماهنگی با ناوگان‌های پستی و تحویل کالا به دست شخص خریدار.
            </div>
            <div className="p-4 rounded-xl bg-muted/40 border border-border/50 text-xs text-muted-foreground leading-relaxed">
              <span className="font-bold text-foreground block mb-1">اطلاع‌رسانی وضعیت سفارش</span>
              ارسال پیامک لحظه‌ای آماده‌سازی و کد رهگیری مرسوله پستی.
            </div>
            <div className="p-4 rounded-xl bg-muted/40 border border-border/50 text-xs text-muted-foreground leading-relaxed">
              <span className="font-bold text-foreground block mb-1">پشتیبانی و خدمات پس از فروش</span>
              پاسخگویی به تیکت‌ها و رسیدگی به امور گارانتی و مرجوعی.
            </div>
            <div className="p-4 rounded-xl bg-muted/40 border border-border/50 text-xs text-muted-foreground leading-relaxed">
              <span className="font-bold text-foreground block mb-1">تسهیل ورود بدون پسورد</span>
              ورود سریع با تاییدیه پیامکی یکبار مصرف امن (OTP).
            </div>
          </div>
        </section>

        {/* Section 3 */}
        <section className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400 font-bold text-lg">
            <Lock className="w-5 h-5" />
            <h2>۳. امنیت و حفاظت فنی از داده‌ها</h2>
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            ما از فناوری‌های پیشرفته مهندسی و امنیتی مطابق با استاندارد جهانی OWASP ASVS بهره می‌بریم:
          </p>
          <ul className="list-disc list-inside text-muted-foreground text-sm space-y-2 pr-2">
            <li><strong>رمزنگاری انتقال داده‌ها (TLS/HTTPS):</strong> کلیه ارتباطات و ارسال فرم‌ها با پروتکل رمزگذاری ۲۵۶ بیتی محافظت می‌شوند.</li>
            <li><strong>کوکی‌های امن HttpOnly:</strong> نشانه‌های ورود و سشن‌ها به شکلی نگهداری می‌شوند که در برابر حملات XSS و نفوذ جاوااسکریپتی کاملاً نفوذناپذیر هستند.</li>
            <li><strong>هش رمزعبور با الگوریتم قدرتمند Argon2id:</strong> کلمات عبور به صورت خام در هیچ پایگاه داده‌ای ثبت نشده و با استانداردترین الگوریتم روز دنیا رمزگذاری می‌گردند.</li>
            <li><strong>جداسازی شبکه سرورها:</strong> پایگاه داده در شبکه‌های امن و ایزوله داخلی میزبانی شده و ارتباط مستقیم با اینترنت عمومی ندارد.</li>
          </ul>
        </section>

        {/* Section 4 */}
        <section className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400 font-bold text-lg">
            <Server className="w-5 h-5" />
            <h2>۴. عدم افشا به اشخاص ثالث</h2>
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            فروشگاه به هیچ عنوان اطلاعات هویتی، آدرس، شماره تماس و سوابق خرید مشتریان را به شرکت‌های تبلیغاتی یا اشخاص ثالث به فروش نرسانده و اجاره نمی‌دهد. تنها استثنا شرکت‌های پستی و ارسال بار هستند که منحصراً نام و آدرس شما را جهت رساندن بسته در اختیار دارند.
          </p>
        </section>

        {/* Section 5 */}
        <section className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
          <div className="flex items-center gap-3 text-emerald-600 dark:text-emerald-400 font-bold text-lg">
            <KeyRound className="w-5 h-5" />
            <h2>۵. حقوق کاربر و کنترل داده‌ها</h2>
          </div>
          <p className="text-muted-foreground text-sm leading-relaxed">
            شما در هر زمان حق دارید به اطلاعات پروفایل خود در بخش «حساب کاربری» دسترسی داشته باشید، آدرس‌های ثبت‌شده را ویرایش یا حذف نمایید، و یا در صورت نیاز از طریق تیکت پشتیبانی، درخواست حذف کامل تاریخچه‌های غیرضروری را ارائه دهید.
          </p>
        </section>
      </div>
    </div>
  );
}
