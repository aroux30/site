import { IndexingSettingsCard } from "@/components/admin/indexing-settings-card";

/**
 * SEO → Instant Indexing (moved from Settings → Content & Media).
 *
 * IndexNow submission is purely an indexing concern — it tells Bing/Yandex
 * about a freshly published URL. It never belonged next to "comments per page".
 */
export default function InstantIndexingPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">ایندکس فوری</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          معرفی خودکار نوشته‌های تازه‌منتشرشده به Bing و Yandex از طریق
          IndexNow، و وضعیت اتصال Google Indexing API.
        </p>
      </div>
      <IndexingSettingsCard />
    </div>
  );
}
