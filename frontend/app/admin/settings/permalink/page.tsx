import type { Metadata } from "next";
import { Link2 } from "lucide-react";
import { PermalinkSettingsCard } from "@/components/admin/permalink-settings-card";

export const metadata: Metadata = {
  title: "پیوندهای یکتا | فروشگاه",
};

/**
 * WordPress options-permalink.php parity. The permalink rows used to live in
 * the «تنظیمات محتوا» card on /admin/settings, buried between comment and
 * media options — WP gives URL structure its own screen under Settings, and
 * so does this page (a child of «تنظیمات» in the sidebar).
 */
export default function AdminPermalinkSettingsPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary/10 text-primary ring-1 ring-primary/20">
          <Link2 className="h-5 w-5" />
        </div>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">پیوندهای یکتا</h1>
          <p className="text-xs text-muted-foreground sm:text-sm">
            قالب آدرس‌های نوشته‌های وبلاگ و پیشوندهای آرشیو دسته و برچسب
          </p>
        </div>
      </div>
      <PermalinkSettingsCard />
    </div>
  );
}
