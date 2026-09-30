import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ثبت‌نام",
  description: "ساخت حساب کاربری جدید در فروشگاه آنلاین.",
  robots: { index: false, follow: true },
};

export default function RegisterLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
