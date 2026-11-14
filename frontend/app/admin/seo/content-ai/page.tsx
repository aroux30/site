import { ContentAiSettingsCard } from "@/components/admin/content-ai-settings-card";

/**
 * SEO → Content AI (moved from Settings → Content & Media).
 *
 * The card configures the LLM that suggests SEO titles and meta descriptions
 * for posts. It is an SEO-writing assistant, not a media/editor preference.
 */
export default function ContentAiSeoPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black">هوش مصنوعی محتوا</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          اتصال به سرویس هوش مصنوعی برای پیشنهاد عنوان سئو و توضیحات متا در
          ویرایشگر نوشته.
        </p>
      </div>
      <ContentAiSettingsCard />
    </div>
  );
}
