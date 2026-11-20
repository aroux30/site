import { LocalSeoSettingsCard } from "@/components/admin/local-seo-settings-card";

/**
 * SEO → Local SEO (moved from Settings → Content & Media).
 *
 * Business type, address, geo coordinates and opening hours are emitted as
 * `LocalBusiness` JSON-LD — the node Google reads for local results and the
 * knowledge panel. This is structured-data configuration, so it lives in SEO.
 */
export default function LocalSeoPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black">سئوی محلی (کسب‌وکار)</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          مشخصات کسب‌وکار که در داده‌ی ساخت‌یافته‌ی LocalBusiness منتشر
          می‌شود — همان چیزی که گوگل برای نتایج محلی می‌خواند.
        </p>
      </div>
      <LocalSeoSettingsCard />
    </div>
  );
}
