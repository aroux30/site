import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "مجله و بلاگ",
  description: "مقالات راهنمای خرید، بررسی تخصصی کالاها و اخبار تکنولوژی.",
};

export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
