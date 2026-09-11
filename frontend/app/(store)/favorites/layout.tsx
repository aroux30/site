import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "علاقه‌مندی‌های من",
  description: "فهرست کالاهای نشان‌شده شما.",
  robots: { index: false, follow: true },
};

export default function FavoritesLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
