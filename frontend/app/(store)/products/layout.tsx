import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "فروشگاه محصولات | لیست قیمت کالاها",
  description:
    "جستجو و مقایسه هزاران کالای دیجیتال با بهترین قیمت، گارانتی رسمی و ارسال سریع به سراسر ایران.",
};

export default function ProductsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
