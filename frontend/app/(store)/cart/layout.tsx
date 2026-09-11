import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "سبد خرید",
  description: "بررسی و ویرایش اقلام سبد خرید شما.",
  robots: { index: false, follow: true },
};

export default function CartLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
