"use client";

/**
 * robots.txt card (WordPress parity).
 *
 * P1 "تنظیمات: robots.txt مجازی با دستور قالب". The storefront's /robots.txt is
 * generated; this card writes the operator's extra lines (site option
 * `robots_extra_rules`), appended verbatim after the generated rules — a
 * Crawl-delay, a rule for one crawler — without a deploy.
 */

import { useCallback, useEffect, useState } from "react";
import { Bot, Save } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";
import { useAdminMutation } from "@/lib/api/admin-query";

const EXAMPLE = `User-Agent: SemrushBot
Disallow: /

Crawl-delay: 10`;

export function RobotsSettingsCard() {
  const { toast } = useToast();
  const runMutation = useAdminMutation();
  const [saving, setSaving] = useState(false);
  const [extra, setExtra] = useState("");

  const load = useCallback(async () => {
    try {
      const opts = await siteOptionsApi.list();
      setExtra(opts.robots_extra_rules ?? "");
    } catch {
      toast({ title: "خواندن قواعد robots ناموفق بود", variant: "destructive" });
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    const result = await runMutation(() => siteOptionsApi.set("robots_extra_rules", extra), {
      fallbackError: "ذخیره قواعد robots ناموفق بود",
    });
    setSaving(false);
    if (!result.ok) {
      toast({ title: result.error, variant: "destructive" });
      return;
    }
    toast({ title: "قواعد robots.txt ذخیره شد" });
    await load();
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center gap-2 border-b border-border pb-3">
        <Bot className="h-5 w-5 text-primary" />
        <h2 className="text-base font-bold text-foreground">فایل robots.txt</h2>
      </div>

      <p className="mb-4 text-xs text-muted-foreground">
        قواعد پایه (Allow/Disallow و آدرس نقشه‌ی سایت) به‌صورت خودکار ساخته می‌شوند. خطوط
        زیر به انتهای همان فایل اضافه می‌شوند — برای مسدودکردن یک خزنده‌ی خاص یا افزودن
        <code dir="ltr" className="mx-1">Crawl-delay</code>.
      </p>

      <div className="space-y-2">
        <Label htmlFor="robots-extra">خطوط سفارشی</Label>
        <textarea
          id="robots-extra"
          value={extra}
          onChange={(e) => setExtra(e.target.value)}
          rows={8}
          dir="ltr"
          placeholder={EXAMPLE}
          className="w-full rounded-md border border-input bg-background p-3 font-mono text-xs"
        />
        <p className="text-xs text-muted-foreground">
          هر خط عیناً در <code dir="ltr">/robots.txt</code> درج می‌شود. خالی‌گذاشتن یعنی فقط
          قواعد خودکار. برای اطمینان، فایل منتشرشده را در مرورگر ببینید.
        </p>
      </div>

      <div className="mt-5 flex justify-end">
        <Button onClick={save} disabled={saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره قواعد robots.txt"}
        </Button>
      </div>
    </Card>
  );
}

export default RobotsSettingsCard;