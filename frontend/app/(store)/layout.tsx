import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { FloatingCompareBar } from "@/components/compare/floating-compare-bar";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";

export default function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1 pb-16 md:pb-0">{children}</main>
      <FloatingCompareBar />
      <MobileBottomNav />
      <Footer />
    </div>
  );
}
