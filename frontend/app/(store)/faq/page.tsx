"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import {
  Search,
  ShoppingCart,
  Truck,
  RotateCcw,
  UserCircle,
  Phone,
  Mail,
  MessageCircle,
  HelpCircle,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

interface FAQItem {
  question: string;
  answer: string;
}

interface FAQCategory {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  items: FAQItem[];
}

const faqCategories: FAQCategory[] = [
  {
    id: "order",
    title: "سفارش و خرید",
    icon: ShoppingCart,
    color: "text-blue-500 bg-blue-50 dark:bg-blue-950/40",
    items: [
      {
        question: "چگونه می‌توانم سفارش خود را ثبت کنم؟",
        answer:
          "برای ثبت سفارش، ابتدا محصول مورد نظر خود را انتخاب کرده و به سبد خرید اضافه کنید. سپس وارد حساب کاربری خود شوید (یا یک حساب جدید بسازید) و اطلاعات آدرس و نحوه پرداخت را تکمیل نمایید. پس از تأیید نهایی، سفارش شما ثبت شده و کد پیگیری به شماره موبایل شما ارسال خواهد شد.",
      },
      {
        question: "چه روش‌های پرداختی در دسترس هستند؟",
        answer:
          "ما از پرداخت آنلاین از طریق درگاه‌های معتبر بانکی (شامل تمامی کارت‌های عضو شبکه شتاب)، پرداخت از کیف پول کاربری و پرداخت در محل (برای شهرهای منتخب) پشتیبانی می‌کنیم. همچنین امکان پرداخت اقساطی از طریق خدمات اعتباری همکاران ما وجود دارد.",
      },
      {
        question: "چگونه سفارش خود را پیگیری کنم؟",
        answer:
          "پس از ثبت سفارش، می‌توانید از بخش «سفارش‌های من» در پنل کاربری وضعیت سفارش خود را بررسی کنید. همچنین پس از ارسال کالا، کد رهگیری مرسوله پستی برای شما پیامک می‌شود که با آن می‌توانید از سایت شرکت پستی پیگیری لازم را انجام دهید.",
      },
      {
        question: "آیا امکان لغو سفارش وجود دارد؟",
        answer:
          "بله، تا زمانی که سفارش شما در مرحله «در حال پردازش» قرار دارد و هنوز ارسال نشده است، می‌توانید از طریق پنل کاربری درخواست لغو سفارش ثبت کنید. پس از ارسال کالا، امکان لغو وجود ندارد ولی می‌توانید از فرآیند بازگشت کالا استفاده نمایید.",
      },
    ],
  },
  {
    id: "shipping",
    title: "ارسال و تحویل",
    icon: Truck,
    color: "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/40",
    items: [
      {
        question: "زمان تحویل سفارش چقدر است؟",
        answer:
          "برای تهران و کلان‌شهرها معمولاً ۱ تا ۳ روز کاری و برای سایر شهرها ۳ تا ۷ روز کاری زمان نیاز است. در صورت انتخاب ارسال اکسپرس در تهران، سفارش‌های ثبت‌شده تا ساعت ۱۲ ظهر، همان روز ارسال می‌شوند.",
      },
      {
        question: "هزینه ارسال چقدر است؟",
        answer:
          "هزینه ارسال بسته به وزن مرسوله، شهر مقصد و روش ارسال انتخابی متفاوت است. هزینه دقیق ارسال در مرحله تکمیل سفارش و پیش از پرداخت به شما نمایش داده می‌شود. برای سفارش‌های بالای ۵۰۰,۰۰۰ تومان، ارسال رایگان خواهد بود.",
      },
      {
        question: "آیا ارسال رایگان دارید؟",
        answer:
          "بله! تمامی سفارش‌هایی که مبلغ کل آن‌ها بیش از ۵۰۰,۰۰۰ تومان باشد، با ارسال رایگان به سراسر کشور فرستاده می‌شوند. همچنین در مناسبت‌های ویژه و جشنواره‌های فروش، ممکن است ارسال رایگان بدون حداقل خرید ارائه شود.",
      },
    ],
  },
  {
    id: "returns",
    title: "بازگشت و گارانتی",
    icon: RotateCcw,
    color: "text-orange-500 bg-orange-50 dark:bg-orange-950/40",
    items: [
      {
        question: "شرایط بازگشت کالا چیست؟",
        answer:
          "شما می‌توانید تا ۷ روز پس از دریافت کالا، درخواست بازگشت خود را ثبت کنید. کالا باید در بسته‌بندی اصلی، بدون استفاده و بدون آسیب‌دیدگی باشد. پس از تأیید درخواست بازگشت، هماهنگی لازم جهت جمع‌آوری کالا انجام خواهد شد.",
      },
      {
        question: "گارانتی محصولات چگونه است؟",
        answer:
          "تمامی محصولات فروشگاه ما دارای ضمانت اصالت هستند. محصولات الکترونیکی دارای گارانتی رسمی شرکت سازنده یا نمایندگی معتبر در ایران می‌باشند. مدت و شرایط گارانتی در صفحه هر محصول مشخص شده است.",
      },
      {
        question: "اگر کالای آسیب‌دیده دریافت کنم چه کار کنم؟",
        answer:
          "در صورت دریافت کالای آسیب‌دیده، لطفاً ظرف ۲۴ ساعت با پشتیبانی تماس بگیرید و تصاویری از آسیب‌دیدگی ارسال نمایید. ما بلافاصله فرآیند جایگزینی یا استرداد وجه را آغاز خواهیم کرد. هزینه ارسال برگشت کالای آسیب‌دیده نیز بر عهده فروشگاه خواهد بود.",
      },
    ],
  },
  {
    id: "account",
    title: "حساب کاربری",
    icon: UserCircle,
    color: "text-purple-500 bg-purple-50 dark:bg-purple-950/40",
    items: [
      {
        question: "چگونه حساب کاربری ایجاد کنم؟",
        answer:
          'برای ایجاد حساب کاربری، روی دکمه «ثبت‌نام» در بالای صفحه کلیک کنید. سپس شماره موبایل خود را وارد کرده و کد تأیید ارسال‌شده را وارد نمایید. پس از تأیید شماره، اطلاعات پروفایل خود شامل نام و ایمیل (اختیاری) را تکمیل کنید.',
      },
      {
        question: "رمز عبور خود را فراموش کرده‌ام، چه کار کنم؟",
        answer:
          'در صفحه ورود، روی گزینه «فراموشی رمز عبور» کلیک کنید و شماره موبایل ثبت‌شده را وارد نمایید. یک کد تأیید به شماره شما ارسال می‌شود و پس از وارد کردن آن می‌توانید رمز عبور جدیدی تنظیم کنید. همچنین می‌توانید از طریق تماس با پشتیبانی نیز درخواست بازیابی رمز ثبت کنید.',
      },
    ],
  },
];

export default function FAQPage() {
  const [searchQuery, setSearchQuery] = useState("");

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return faqCategories;

    const query = searchQuery.trim().toLowerCase();
    return faqCategories
      .map((category) => ({
        ...category,
        items: category.items.filter(
          (item) =>
            item.question.toLowerCase().includes(query) ||
            item.answer.toLowerCase().includes(query)
        ),
      }))
      .filter((category) => category.items.length > 0);
  }, [searchQuery]);

  const totalResults = filteredCategories.reduce(
    (acc, cat) => acc + cat.items.length,
    0
  );

  return (
    <div className="container-page">
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="transition-colors hover:text-primary">
          صفحه اصلی
        </Link>
        <span>/</span>
        <span className="font-medium text-foreground">سوالات متداول</span>
      </div>

      {/* Hero Section */}
      <section className="mb-12 rounded-2xl bg-gradient-to-l from-primary-600 to-secondary-600 p-8 text-white sm:p-14">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-white/15 backdrop-blur-sm">
            <HelpCircle className="h-8 w-8" />
          </div>
          <h1 className="mb-3 text-3xl font-bold sm:text-4xl">
            سوالات متداول
          </h1>
          <p className="mb-8 text-lg leading-relaxed text-white/90">
            پاسخ سوالات رایج خود را در اینجا بیابید. اگر پاسخ سوال خود را
            نیافتید، با تیم پشتیبانی ما تماس بگیرید.
          </p>

          {/* Search Input */}
          <div className="relative mx-auto max-w-md">
            <Search className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="جستجو در سوالات متداول..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-12 rounded-xl border-white/20 bg-white pr-12 text-foreground shadow-lg placeholder:text-muted-foreground"
            />
          </div>
        </div>
      </section>

      {/* Search Results Info */}
      {searchQuery.trim() && (
        <div className="mb-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {totalResults > 0 ? (
              <>
                <span className="font-medium text-foreground">
                  {totalResults}
                </span>{" "}
                نتیجه برای &laquo;{searchQuery}&raquo; یافت شد
              </>
            ) : (
              <>نتیجه‌ای برای &laquo;{searchQuery}&raquo; یافت نشد</>
            )}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSearchQuery("")}
            className="text-xs"
          >
            پاک کردن جستجو
          </Button>
        </div>
      )}

      {/* FAQ Categories */}
      {filteredCategories.length > 0 ? (
        <div className="space-y-10">
          {filteredCategories.map((category) => {
            const CategoryIcon = category.icon;
            return (
            <section key={category.id}>
              {/* Category Header */}
              <div className="mb-4 flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl ${category.color}`}
                >
                  <CategoryIcon className="h-5 w-5" />
                </div>
                <h2 className="text-xl font-bold text-foreground">
                  {category.title}
                </h2>
              </div>

              {/* Accordion */}
              <Card className="overflow-hidden">
                <Accordion type="single" collapsible className="w-full">
                  {category.items.map((item, index) => (
                    <AccordionItem
                      key={index}
                      value={`${category.id}-${index}`}
                      className="border-border px-6"
                    >
                      <AccordionTrigger className="text-right text-sm font-medium leading-relaxed sm:text-base">
                        {item.question}
                      </AccordionTrigger>
                      <AccordionContent className="text-sm leading-7 text-muted-foreground">
                        {item.answer}
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </Card>
            </section>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-border bg-card p-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Search className="h-8 w-8" />
          </div>
          <h3 className="mb-2 text-lg font-semibold text-foreground">
            نتیجه‌ای یافت نشد
          </h3>
          <p className="mb-6 text-sm text-muted-foreground">
            سوال مورد نظر شما در لیست سوالات متداول یافت نشد. لطفاً با تیم
            پشتیبانی ما تماس بگیرید.
          </p>
          <Link href="/contact">
            <Button>تماس با پشتیبانی</Button>
          </Link>
        </div>
      )}

      {/* Contact Support CTA */}
      <section className="mt-16 mb-4 rounded-2xl border border-border bg-card p-8 sm:p-12">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="mb-3 text-2xl font-bold text-foreground">
            پاسخ سوال خود را نیافتید؟
          </h2>
          <p className="mb-8 text-muted-foreground">
            تیم پشتیبانی ما آماده پاسخگویی به سوالات شماست. از طریق یکی از
            روش‌های زیر با ما در ارتباط باشید.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-blue-50 text-blue-500 dark:bg-blue-950/40">
                <Phone className="h-5 w-5" />
              </div>
              <h3 className="mb-1 text-sm font-semibold text-foreground">
                تماس تلفنی
              </h3>
              <p className="text-xs text-muted-foreground" dir="ltr">
                ۰۲۱-۱۲۳۴۵۶۷۸
              </p>
            </Card>

            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-500 dark:bg-emerald-950/40">
                <Mail className="h-5 w-5" />
              </div>
              <h3 className="mb-1 text-sm font-semibold text-foreground">
                ایمیل
              </h3>
              <p className="text-xs text-muted-foreground" dir="ltr">
                support@example.com
              </p>
            </Card>

            <Link href="/contact" className="block">
              <Card className="h-full p-5 transition-shadow hover:shadow-md">
                <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-purple-50 text-purple-500 dark:bg-purple-950/40">
                  <MessageCircle className="h-5 w-5" />
                </div>
                <h3 className="mb-1 text-sm font-semibold text-foreground">
                  فرم تماس
                </h3>
                <p className="text-xs text-muted-foreground">
                  ارسال پیام آنلاین
                </p>
              </Card>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
