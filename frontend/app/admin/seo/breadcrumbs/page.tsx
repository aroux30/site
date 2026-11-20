import { BreadcrumbSettingsCard } from "@/components/admin/breadcrumb-settings-card";

/**
 * SEO → Breadcrumbs (moved from Settings → Content & Media).
 *
 * The trail text and separator are rendered into the visible breadcrumb nav
 * AND emitted as Google's BreadcrumbList structured data, so this is an SEO
 * surface, not a content-presentation one.
 */
export default function BreadcrumbsSeoPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div>
        <h1 className="text-2xl font-black">مسیر صفحه (Breadcrumbs)</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          مسیر نمایشی بالای نوشته‌ها و محصولات و داده‌ی ساخت‌یافته‌ی
          BreadcrumbList که گوگل می‌خواند.
        </p>
      </div>
      <BreadcrumbSettingsCard />
    </div>
  );
}
