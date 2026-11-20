"use client";

/**
 * FAQ admin section (سوالات متداول).
 *
 * Own section, not a card inside «محتوا و منوساز»: FAQ entries are page
 * content (the /faq storefront page + the [faq] shortcode consume them),
 * while that dashboard is a layout surface. Owner decision 2026-11-04.
 */

import { RefreshCw } from "lucide-react";
import FaqManagerCard from "@/components/admin/faq-manager-card";

export default function AdminFaqPage() {
  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-foreground">سوالات متداول</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            مدیریت پرسش‌های پرتکرار؛ خوراک صفحه «سوالات متداول» فروشگاه و کد کوتاه درج در صفحات
          </p>
        </div>
      </div>

      <FaqManagerCard />

      {/* Reload hint kept minimal: the card manages its own data and dialogs. */}
      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
        <RefreshCw className="h-3 w-3" />
        تغییرات بلافاصله در صفحه فروشگاه و صفحاتی که کد کوتاه را دارند اعمال می‌شود.
      </p>
    </div>
  );
}
