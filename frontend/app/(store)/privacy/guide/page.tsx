import type { Metadata } from "next";
import Link from "next/link";
import { Copy, FileText, Info } from "lucide-react";

export const metadata: Metadata = {
  title: "راهنمای سیاست حفظ حریم خصوصی",
  description:
    "متن پیشنهادی سیاست حفظ حریم خصوصی برای فروشگاه اینترنتی، بند‌به‌بند، برای بازبینی حقوقی و درج در سایت.",
  robots: { index: false, follow: true },
};

/**
 * WordPress ships a privacy-policy guide: a suggested policy an operator
 * reviews and publishes, rather than a page they have to write. It existed in
 * ours as a gap — the store could publish a policy but had nothing to publish.
 *
 * This is deliberately NOT linked from the site navigation and is marked
 * noindex: it is drafting material for the operator, not a public document.
 * Once reviewed, the published policy belongs in the CMS at the `privacy` slug
 * (`/(store)/privacy`), which this page links to.
 *
 * The placeholders are the parts only the operator can fill in. Everything
 * around them states what this codebase actually does, so the draft cannot
 * quietly diverge from the system.
 */
interface Section {
  title: string;
  body: React.ReactNode;
}

const PLACEHOLDER = "【نام فروشگاه】";

const SECTIONS: Section[] = [
  {
    title: "۱. چه داده‌هایی جمع‌آوری می‌کنیم",
    body: (
      <>
        <p>ما تنها داده‌ای را جمع‌آوری می‌کنیم که برای انجام سفارش لازم است:</p>
        <ul>
          <li>نام، شمارهٔ تلفن همراه و نشانی برای ارسال سفارش</li>
          <li>نشانی ایمیل برای اطلاع‌رسانی وضعیت سفارش</li>
          <li>سابقهٔ سفارش و پرداخت برای پیگیری و بازگشت وجه</li>
        </ul>
        <p>اطلاعات کارت بانکی هرگز روی سرورهای ما ذخیره نمی‌شود؛ درگاه پرداخت آن را مستقیم پردازش می‌کند.</p>
      </>
    ),
  },
  {
    title: "۲. چرا این داده‌ها را نگه می‌داریم",
    body: (
      <p>
        نگه‌داشتن این داده‌ها برای اجرای تعهدات قانونی ما در قبال شما ضروری است: تحویل
        سفارش، رسیدگی به مرجوعی، و الزامات مالیاتی و حسابرسی.
      </p>
    ),
  },
  {
    title: "۳. با چه کسانی به اشتراک می‌گذاریم",
    body: (
      <>
        <p>فقط با ارائه‌دهندگانی که برای انجام سفارش لازم‌اند:</p>
        <ul>
          <li>شرکت پستی و پیک برای تحویل</li>
          <li>درگاه پرداخت برای تأیید تراکنش</li>
          <li>{PLACEHOLDER} برای ارسال پیامک تأیید سفارش</li>
        </ul>
        <p>ما دادهٔ شما را برای تبلیغات به شخص ثالث نمی‌فروشیم.</p>
      </>
    ),
  },
  {
    title: "۴. چه مدت نگه می‌داریم",
    body: (
      <p>
        داده‌های سفارش تا پایان مدت الزام قانونی نگه‌داری اسناد مالی باقی می‌مانند. سایر
        داده‌ها تا زمانی که حساب شما فعال است.
      </p>
    ),
  },
  {
    title: "۵. حق شما نسبت به داده‌ها",
    body: (
      <>
        <p>شما می‌توانید در هر زمان یکی از این کارها را انجام دهید:</p>
        <ul>
          <li>دریافت یک نسخهٔ کامل از داده‌هایتان</li>
          <li>اصلاح داده‌های نادرست</li>
          <li>درخواست حذف حساب و داده‌هایتان</li>
        </ul>
        <p>
          هر سه از بخش «حریم خصوصی» در <Link href="/account/privacy" className="underline">حساب کاربری شما</Link>{" "}
          قابل درخواست است و وضعیت هر درخواست قابل پیگیری است.
        </p>
      </>
    ),
  },
  {
    title: "۶. کوکی‌ها",
    body: (
      <p>
        برای نگه‌داشتن شما در وضعیت ورود و افزودن کالاها به سبد خرید از کوکی استفاده
        می‌کنیم. کوکی‌های تبلیغاتی شخصی‌سازی‌شده تنظیم نشده‌اند.
      </p>
    ),
  },
  {
    title: "۷. امنیت داده",
    body: (
      <p>
        دسترسی به داده‌های کاربران فقط برای کارکنانی است که برای انجام وظیفهٔ خود به آن
        نیاز دارند، و همهٔ دسترسی‌ها ثبت می‌شوند.
      </p>
    ),
  },
  {
    title: "۸. حق شما نسبت به این متن",
    body: (
      <p>
        این متن یک پیش‌نویس است، نه سند حقوقی. پیش از انتشار، آن را با وضعیت واقعی کسب‌وکارتان
        — به‌ویژه بخش «چه کسانی» و «چه مدت» — تطبیق دهید.
      </p>
    ),
  },
];

export default function PrivacyPolicyGuidePage() {
  return (
    <div className="container mx-auto px-4 py-12 max-w-3xl">
      <header className="mb-10">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-amber-500/10 text-amber-600 dark:text-amber-400 text-xs font-medium mb-4">
          <FileText className="w-4 h-4" />
          پیش‌نویس برای بازبینی
        </div>
        <h1 className="text-3xl font-bold text-foreground mb-3">راهنمای سیاست حفظ حریم خصوصی</h1>
        <p className="text-muted-foreground leading-8">
          متن پیشنهادی سیاست حفظ حریم خصوصی برای فروشگاه اینترنتی. بخش‌هایی که باید خودتان
          پر کنید با <Copy className="inline w-4 h-4 align-text-bottom" />{" "}
          مشخص شده‌اند.
        </p>
      </header>

      <div className="mb-8 p-4 rounded-xl border border-amber-500/30 bg-amber-500/5 flex gap-3">
        <Info className="w-5 h-5 shrink-0 text-amber-600 dark:text-amber-400 mt-0.5" />
        <p className="text-sm text-muted-foreground leading-7">
          این صفحه برای بازبینی داخلی است و در فهرست سایت نیست. سیاست منتشرشده باید در
          بخش «حریم خصوصی» سایت قرار بگیرد:{" "}
          <Link href="/privacy" className="underline">
            صفحهٔ سیاست حریم خصوصی
          </Link>
          .
        </p>
      </div>

      <div className="space-y-8">
        {SECTIONS.map((section) => (
          <section key={section.title}>
            <h2 className="text-lg font-semibold text-foreground mb-3">{section.title}</h2>
            <div className="text-muted-foreground leading-8 space-y-3">{section.body}</div>
          </section>
        ))}
      </div>

      <footer className="mt-12 pt-6 border-t border-border text-sm text-muted-foreground">
        آخرین بازبینی این پیش‌نویس باید پس از هر تغییر در فرایندهای جمع‌آوری داده به‌روز شود.
      </footer>
    </div>
  );
}
