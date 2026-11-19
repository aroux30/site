import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { AdminBar, AdminBarSpacer } from "@/components/layout/admin-bar";
import { FloatingBottomDock } from "@/components/store/floating-bottom-dock";
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
    // The spacer reserves room for the fixed admin bar. It is unconditional
    // while the bar shows — the bar only renders for a signed-in admin, and
    // making the padding depend on auth would shift the whole page on every
    // sign-in and sign-out — and collapses only in the «بدون نوار» preview
    // tab, where the bar itself is hidden too.
    <div className="flex min-h-screen flex-col">
      {/* First focusable element on the page: lets a keyboard user reach the
          content without tabbing through the whole header nav every time. */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:start-4 focus:z-[100] focus:rounded-xl focus:bg-primary focus:px-4 focus:py-2.5 focus:text-sm focus:font-bold focus:text-primary-foreground focus:shadow-2xl focus:ring-2 focus:ring-white"
      >
        پرش به محتوا
      </a>
      <AdminBarSpacer />
      <AdminBar />
      <Header />
      {/* Admin-scheduled notices targeted at this route. The endpoint and
          the client both existed; nothing rendered them, so a campaign aimed
          at checkout or the home page never reached a customer. */}
      <NoticeBanner />
      <main id="main-content" tabIndex={-1} className="flex-1 pb-16 md:pb-0">{children}</main>
      {/* The dock owns the viewport-aware bottom offset (above the mobile
          nav + chat FAB) and stacks the compare/cart bars vertically, so the
          two can never render at the same coordinates again. */}
      <FloatingBottomDock>
        <FloatingCompareBar />
        <FloatingCartBar />
      </FloatingBottomDock>
      {/* PluginWidgetLoader lives in the ROOT layout now: it must keep
          watching the route so the body-mounted chat FAB hides on /admin. */}
      <MobileBottomNav />
      <Footer />
    </div>
  );
}
