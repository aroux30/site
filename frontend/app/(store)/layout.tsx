import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { FloatingCompareBar } from "@/components/compare/floating-compare-bar";

export default function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen flex-col">
      <Header />
      <main className="flex-1">{children}</main>
      <FloatingCompareBar />
      <Footer />
    </div>
  );
}
