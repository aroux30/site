import type { Metadata } from "next";
import Link from "next/link";
import { ShieldCheck, FileText, CheckCircle2, AlertCircle, Scale } from "lucide-react";

export const metadata: Metadata = {
  title: "شرایط و قوانین استفاده | فروشگاه آنلاین",
  description: "شرایط، ضوابط و قوانین استفاده از خدمات و خریدهای آنلاین در فروشگاه.",
};

export default function TermsPage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-5xl">
      {/* Header */}
      <div className="text-center max-w-3xl mx-auto mb-12">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-xs font-medium mb-4">
          <Scale className="w-4 h-4" />
          قوانین و مقررات رسمی
        </div>
        <h1 className="text-3xl md:text-4xl font-extrabold text-foreground mb-4">
          شرایط و قوانین استفاده از خدمات
        </h1>
        <p className="text-muted-foreground text-sm md:text-base leading-relaxed">
          استفاده از خدمات این فروشگاه به منزله پذیرش کلیه قوانین، مقررات تجارت الکترونیکی و ضوابط زیر است. لطفاً پیش از ثبت سفارش این صفحه را با دقت مطالعه فرمایید.
        </p>
        <div className="mt-4 text-xs text-muted-foreground">
          آخرین بروزرسانی: شهریور ۱۴۰۵
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-12 gap-8">
        {/* Navigation / Quick Links */}
        <aside className="hidden md:block md:col-span-4 lg:col-span-3">
          <div className="sticky top-24 p-5 rounded-2xl bg-card border border-border shadow-sm space-y-2 text-sm">
            <div className="font-bold text-foreground mb-3 flex items-center gap-2">
              <FileText className="w-4 h-4 text-emerald-600" />
              فهرست عناوین
            </div>
            <a href="#general" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۱. تعاریف و کلیات
            </a>
            <a href="#account" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۲. حساب کاربری و امنیت
            </a>
            <a href="#orders" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۳. ثبت و پردازش سفارش
            </a>
            <a href="#payments" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۴. شیوه و قوانین پرداخت
            </a>
            <a href="#shipping" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۵. حمل و نقل و تحویل
            </a>
            <a href="#returns" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۶. انصراف و مرجوعی کالا
            </a>
            <a href="#copyright" className="block text-muted-foreground hover:text-emerald-600 transition-colors py-1">
              ۷. مالکیت فکری
            </a>
          </div>
        </aside>

        {/* Content Body */}
        <main className="md:col-span-8 lg:col-span-9 space-y-10">
          <section id="general" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۱. تعاریف و کلیات
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              کلیه اصول و رویه‌های این فروشگاه منطبق با قوانین جمهوری اسلامی ایران، قانون تجارت الکترونیک و قانون حمایت از حقوق مصرف‌کننده است و کاربر نیز موظف به رعایت قوانین مرتبط با کاربر است.
            </p>
            <ul className="list-disc list-inside text-muted-foreground text-sm space-y-2 pr-2">
              <li><strong>فروشگاه:</strong> وب‌سایت فروشگاه آنلاین ارائه دهنده کالا و خدمات الکترونیکی.</li>
              <li><strong>مشتری یا کاربر:</strong> هر شخصی که با اطلاعات هویتی خود در سایت ثبت‌نام کرده و از خدمات استفاده می‌نماید.</li>
              <li><strong>روز کاری:</strong> به معنی روز شنبه تا پنج‌شنبه هر هفته، به استثنای تعطیلات عمومی در ایران است.</li>
            </ul>
          </section>

          <section id="account" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۲. حساب کاربری و امنیت
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              کاربران هنگام ثبت‌نام باید شماره تلفن همراه معتبر و متعلق به خود را وارد نمایند. کدهای تایید هویت (OTP) محرمانه بوده و مسئولیت حفظ امنیت و هرگونه فعالیت تحت حساب کاربری به عهده کاربر است.
            </p>
            <p className="text-muted-foreground text-sm leading-relaxed">
              فروشگاه هویت و سوابق دسترسی را با پروتکل‌های امنیتی روز دنیا و رمزنگاری چندمرحله‌ای محافظت می‌نماید و متعهد است اطلاعات خصوصی کاربران را در اختیار اشخاص ثالث قرار ندهد.
            </p>
          </section>

          <section id="orders" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۳. ثبت و پردازش سفارش
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              ثبت سفارش در ۷ روز هفته و ۲۴ ساعت شبانه‌روز امکان‌پذیر است. پس از نهایی شدن پرداخت، سفارش وارد چرخه پردازش، انبارداری و بسته‌بندی خواهد شد. کد رهگیری پستی بلافاصله پس از تحویل به ناوگان حمل از طریق پنل و پیامک به اطلاع خریدار می‌رسد.
            </p>
            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-700 dark:text-amber-400 text-xs flex items-start gap-2">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              در صورت بروز هرگونه مغایرت قیمتی ناشی از اشتباهات سیستمی، حق لغو سفارش و استرداد وجه ظرف کمتر از ۲۴ ساعت برای فروشگاه محفوظ است.
            </div>
          </section>

          <section id="payments" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۴. شیوه و قوانین پرداخت
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              پرداخت در فروشگاه از طریق درگاه‌های پرداخت رسمی شبکه شتاب (زرین‌پال، سداد، به‌پرداخت، سامان و غیره)، واریز از کیف‌پول اعتباری، درگاه رمزارز معتبر و انتقال کارت به کارت با تایید فیش واریز امکان‌پذیر است.
            </p>
          </section>

          <section id="shipping" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۵. حمل و نقل و تحویل
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              سفارشات شهر تهران با پیک اختصاصی و سایر نقاط کشور از طریق شرکت ملی پست (پیشتاز) و تیپاکس با بسته‌بندی ایمن ضدضربه ارسال می‌گردند. خریدار موظف است هنگام دریافت کالا، سلامت فیزیکی بسته را بررسی نماید.
            </p>
          </section>

          <section id="returns" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600" />
              ۶. انصراف و مرجوعی کالا (ضمانت ۷ روزه)
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              کلیه کالاها دارای ۷ روز مهلت تست سلامت و بازگشت وجه طبق شیوه‌نامه رسمی بازگشت کالا می‌باشند. جهت مشاهده شرایط اختصاصی عودت قطعات دیجیتال، لطفاً به بخش 
              <Link href="/returns" className="text-emerald-600 font-semibold px-1 underline">
                رویه بازگشت کالا
              </Link> 
              مراجعه نمایید.
            </p>
          </section>

          <section id="copyright" className="p-8 rounded-2xl bg-card border border-border shadow-sm space-y-4">
            <h2 className="text-xl font-bold text-foreground flex items-center gap-2 border-b border-border pb-3">
              <ShieldCheck className="w-5 h-5 text-emerald-600" />
              ۷. مالکیت فکری
            </h2>
            <p className="text-muted-foreground text-sm leading-relaxed">
              تمامی محتویات، طرح گرافیکی، تصاویر محصولات، کدهای فنی و نام تجاری متعلق به این فروشگاه بوده و هرگونه کپی‌برداری تجاری بدون کسب مجوز کتبی پیگرد قانونی دارد.
            </p>
          </section>
        </main>
      </div>
    </div>
  );
}
