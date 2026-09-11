import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "مقایسه کالاها",
  description: "مقایسه مشخصات فنی کالاهای انتخابی شما.",
  robots: { index: false, follow: true },
};

export default function CompareLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
