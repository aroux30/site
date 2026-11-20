import { SearchVisibilityCard } from "@/components/admin/search-visibility-card";

/**
 * SEO → Search visibility (moved from Settings → General and Content & Media).
 *
 * `blog_public` is the WordPress "Search engine visibility" switch: it writes
 * the noindex directive into robots.txt. It is a search-engine concern, so the
 * SEO area owns it — the general settings screen now links here instead of
 * carrying a second copy.
 */
export default function SearchVisibilityPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black">نمایش در موتورهای جست‌وجو</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          مجاز کردن یا پنهان‌کردن کل سایت برای خزنده‌ها — همان تنظیم
          <code dir="ltr" className="mx-1">blog_public</code>
          وردپرس.
        </p>
      </div>
      <SearchVisibilityCard />
    </div>
  );
}
