import { ImageSeoSettingsCard } from "@/components/admin/image-seo-settings-card";

/**
 * SEO → Image SEO (moved from Settings → Content & Media).
 *
 * Image alt/title/caption defaults are search-visible metadata: they feed the
 * `ImageObject` structured data and Google Images. They belonged under the SEO
 * menu from the start; this page is the permanent home.
 */
export default function ImageSeoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">سئوی تصویر</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          متن جایگزین، عنوان و زیرنویس خودکار برای فایل‌های تازه — ورودی
          داده‌های ساخت‌یافته و جست‌وجوی تصویر.
        </p>
      </div>
      <ImageSeoSettingsCard />
    </div>
  );
}
