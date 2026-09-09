"use client";

import Link from "next/link";
import {
  Phone,
  Mail,
  MapPin,
  Clock,
  Shield,
  Truck,
  Award,
  RotateCcw,
  Instagram,
  Twitter,
  Send,
} from "lucide-react";

const quickLinks = [
  { href: "/", label: "صفحه اصلی" },
  { href: "/products", label: "محصولات" },
  { href: "/products?sale=true", label: "تخفیف‌ها" },
  { href: "/blog", label: "بلاگ" },
];

const customerServiceLinks = [
  { href: "/faq", label: "سوالات متداول" },
  { href: "/terms", label: "شرایط استفاده" },
  { href: "/privacy", label: "حریم خصوصی" },
  { href: "/returns", label: "رویه بازگشت کالا" },
];

const trustBadges = [
  {
    icon: Shield,
    title: "پرداخت امن",
    description: "درگاه معتبر بانکی",
  },
  {
    icon: Truck,
    title: "ارسال سریع",
    description: "تحویل اکسپرس",
  },
  {
    icon: Award,
    title: "ضمانت اصالت",
    description: "تضمین اصل بودن کالا",
  },
  {
    icon: RotateCcw,
    title: "۷ روز ضمانت بازگشت",
    description: "بازگشت بدون دردسر",
  },
];

const socialLinks = [
  { href: "#", icon: Instagram, label: "اینستاگرام" },
  { href: "#", icon: Twitter, label: "توییتر" },
  { href: "#", icon: Send, label: "تلگرام" },
];

export function Footer() {
  const currentYear = new Date().getFullYear();
  // Convert to Persian digits
  const persianYear = String(currentYear).replace(/\d/g, (d) =>
    String.fromCharCode(0x06f0 + Number(d)),
  );

  return (
    <footer className="border-t border-border bg-card">
      {/* ===== Trust Badges Section ===== */}
      <div className="border-b border-border bg-muted/30">
        <div className="container mx-auto px-4 py-8">
          <div className="grid grid-cols-2 gap-4 sm:gap-6 lg:grid-cols-4">
            {trustBadges.map((badge) => (
              <div
                key={badge.title}
                className="flex flex-col items-center gap-3 rounded-xl border border-border bg-background p-4 text-center shadow-sm transition-shadow hover:shadow-md sm:flex-row sm:text-right"
              >
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
                  <badge.icon className="h-6 w-6" />
                </div>
                <div>
                  <h4 className="text-sm font-semibold text-foreground">
                    {badge.title}
                  </h4>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {badge.description}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* ===== Main Footer ===== */}
      <div className="container mx-auto px-4 py-10 lg:py-12">
        <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4 lg:gap-12">
          {/* Column 1: About */}
          <div className="sm:col-span-2 lg:col-span-1">
            <Link href="/" className="mb-4 inline-flex items-center gap-2.5">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-lg font-black text-primary-foreground shadow-sm">
                ف
              </div>
              <span className="text-xl font-bold text-foreground">
                فروشگاه آنلاین
              </span>
            </Link>
            <p className="mb-5 text-sm leading-7 text-muted-foreground">
              فروشگاه اینترنتی با تنوع بالای محصولات، ارسال سریع و رایگان،
              ضمانت اصالت کالا و پشتیبانی ۲۴ ساعته. خریدی آسان، مطمئن و لذت‌بخش
              را با ما تجربه کنید.
            </p>

            {/* Social Media */}
            <div className="flex items-center gap-2">
              {socialLinks.map((social) => (
                <a
                  key={social.label}
                  href={social.href}
                  className="flex h-9 w-9 items-center justify-center rounded-lg border border-border text-muted-foreground transition-colors hover:border-primary hover:bg-primary/5 hover:text-primary"
                  aria-label={social.label}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <social.icon className="h-4 w-4" />
                </a>
              ))}
            </div>
          </div>

          {/* Column 2: Quick Links */}
          <div>
            <h3 className="mb-4 text-sm font-bold text-foreground">
              دسترسی سریع
            </h3>
            <ul className="space-y-3">
              {quickLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 3: Customer Service */}
          <div>
            <h3 className="mb-4 text-sm font-bold text-foreground">
              خدمات مشتریان
            </h3>
            <ul className="space-y-3">
              {customerServiceLinks.map((link) => (
                <li key={link.href}>
                  <Link
                    href={link.href}
                    className="text-sm text-muted-foreground transition-colors hover:text-primary"
                  >
                    {link.label}
                  </Link>
                </li>
              ))}
            </ul>
          </div>

          {/* Column 4: Contact */}
          <div>
            <h3 className="mb-4 text-sm font-bold text-foreground">
              تماس با ما
            </h3>
            <ul className="space-y-4">
              <li>
                <div className="flex items-start gap-2.5">
                  <Phone className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">شماره تماس</p>
                    <span
                      dir="ltr"
                      className="text-sm font-medium text-foreground"
                    >
                      ۰۲۱-۱۲۳۴۵۶۷۸
                    </span>
                  </div>
                </div>
              </li>
              <li>
                <div className="flex items-start gap-2.5">
                  <Mail className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">ایمیل</p>
                    <span
                      dir="ltr"
                      className="text-sm font-medium text-foreground"
                    >
                      support@example.com
                    </span>
                  </div>
                </div>
              </li>
              <li>
                <div className="flex items-start gap-2.5">
                  <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">آدرس</p>
                    <span className="text-sm text-foreground">
                      تهران، خیابان ولیعصر، پلاک ۱۲۳
                    </span>
                  </div>
                </div>
              </li>
              <li>
                <div className="flex items-start gap-2.5">
                  <Clock className="mt-0.5 h-4 w-4 shrink-0 text-primary" />
                  <div>
                    <p className="text-xs text-muted-foreground">ساعت کاری</p>
                    <span className="text-sm text-foreground">
                      شنبه تا پنج‌شنبه ۹ تا ۱۸
                    </span>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </div>

      {/* ===== Bottom Bar ===== */}
      <div className="border-t border-border bg-muted/30">
        <div className="container mx-auto px-4 py-4">
          <div className="flex flex-col items-center justify-between gap-3 sm:flex-row">
            <p className="text-xs text-muted-foreground">
              © {persianYear} فروشگاه آنلاین. تمامی حقوق مادی و معنوی محفوظ
              است.
            </p>
            <div className="flex items-center gap-4">
              <Link
                href="/privacy"
                className="text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                حریم خصوصی
              </Link>
              <span className="text-xs text-border">|</span>
              <Link
                href="/terms"
                className="text-xs text-muted-foreground transition-colors hover:text-foreground"
              >
                شرایط استفاده
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
}
