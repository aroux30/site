import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "ورود به حساب کاربری",
  description: "با شماره موبایل یا رمز عبور وارد حساب کاربری خود شوید.",
  robots: { index: false, follow: true },
};

export default function LoginLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
