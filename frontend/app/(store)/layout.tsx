import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { AdminBar, ADMIN_BAR_HEIGHT } from "@/components/layout/admin-bar";
import { FloatingCompareBar } from "@/components/compare/floating-compare-bar";
import { FloatingCartBar } from "@/components/store/floating-cart-bar";
import { MobileBottomNav } from "@/components/layout/mobile-bottom-nav";
import NoticeBanner from "@/components/layout/notice-banner";

export default function StoreLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    // The pt- reserves room for the fixed admin bar. It is unconditional: the
    // bar only renders for a signed-in admin, and making the padding depend on
    // that would shift the whole page on every sign-in and sign-out.
    <div className="flex min-h-screen flex-col" style={{ paddingTop: ADMIN_BAR_HEIGHT }}>
      {/* First focusable element on the page: lets a keyboard user reach the
          content without tabbing through the whole header nav every time. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:right-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-sm focus:text-primary-foreground"
      >
        پرش به محتوا
      </a>
      <AdminBar />
      <Header />
      {/* Admin-scheduled notices targeted at this route. The endpoint and
          the client both existed; nothing rendered them, so a campaign aimed
          at checkout or the home page never reached a customer. */}
      <NoticeBanner />
      <main id="main-content" tabIndex={-1} className="flex-1 pb-16 md:pb-0">{children}</main>
      <FloatingCompareBar />
      <FloatingCartBar />
      <MobileBottomNav />
      <Footer />
    </div>
  );
}
