import Link from "next/link";
import type { Metadata } from "next";
import { NotFoundReporter } from "@/components/seo/notfound-reporter";

/** The 404 document needs a title of its own — without it the tab and the
 *  console listing show a bare URL — and `noindex` is the belt to the 404
 *  status's braces (a misconfigured proxy can strip the status; the meta
 *  tag survives). */
export const metadata: Metadata = {
  title: "صفحه مورد نظر یافت نشد",
  robots: { index: false, follow: true },
};

export default function NotFound() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-4">
      {/* Feeds the SEO 404 monitor. Renders nothing; fires one keepalive
          POST so the operator can see what is broken (SEO → 404). */}
      <NotFoundReporter />
      <div className="mx-auto max-w-md text-center">
        <h1 className="mb-2 text-8xl font-bold text-primary">۴۰۴</h1>
        <h2 className="mb-4 text-2xl font-semibold text-foreground">
          صفحه مورد نظر یافت نشد
        </h2>
        <p className="mb-8 text-muted-foreground">
          متأسفانه صفحه‌ای که به دنبال آن هستید وجود ندارد یا منتقل شده است.
        </p>
        <Link
          href="/"
          className="inline-flex h-11 items-center justify-center rounded-md bg-primary px-8 text-sm font-medium text-primary-foreground ring-offset-background transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          بازگشت به صفحه اصلی
        </Link>
      </div>
    </main>
  );
}
