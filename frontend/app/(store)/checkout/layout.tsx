import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "تسویه حساب",
  description: "تکمیل اطلاعات ارسال و پرداخت امن سفارش.",
  robots: { index: false, follow: true },
};

export default function CheckoutLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
