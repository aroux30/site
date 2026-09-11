import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "گردونه شانس و باشگاه جوایز",
  description: "چرخ گردونه شانس، امتیاز جمع کن و جوایز رایگان دریافت کن.",
};

export default function RewardsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
