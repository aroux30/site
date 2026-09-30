import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "سوالات متداول",
  description:
    "پاسخ سوالات متداول درباره سفارش، ارسال، بازگشت کالا و حساب کاربری در فروشگاه آنلاین ما را بیابید.",
};

export default function FAQLayout({ children }: { children: React.ReactNode }) {
  return children;
}
