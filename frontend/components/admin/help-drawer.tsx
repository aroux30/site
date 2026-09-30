"use client";

/**
 * Contextual admin help drawer (WordPress inline documentation parity).
 *
 * A floating "?" button opens a side panel with the help tabs registered for
 * the section the editor is currently on. Sections map to the first path
 * segment under /admin (e.g. /admin/blog → "blog_posts").
 */

import { useCallback, useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { HelpCircle } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import apiClient from "@/lib/api/client";

interface HelpTab {
  title: string;
  content: string;
}

// Path segment → help section key registered on the backend.
const SECTION_BY_SEGMENT: Record<string, string> = {
  blog: "blog_posts",
  media: "media_library",
  pages: "cms_pages",
  cms: "cms_pages",
  settings: "settings",
  redirects: "seo",
  seo: "seo",
};

export function AdminHelpDrawer() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const [tabs, setTabs] = useState<HelpTab[]>([]);
  const [loading, setLoading] = useState(false);

  const segment = pathname?.split("/")[2] ?? "";
  const section = SECTION_BY_SEGMENT[segment];

  const load = useCallback(async () => {
    if (!section) return;
    setLoading(true);
    try {
      const { data } = await apiClient.get<{ tabs: HelpTab[] }>(
        `/settings/admin/help/${section}`,
      );
      setTabs(data.tabs ?? []);
    } catch {
      setTabs([]);
    } finally {
      setLoading(false);
    }
  }, [section]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  // No help content is registered for this section — show nothing rather than
  // an empty drawer.
  if (!section) return null;

  return (
    <>
      <Button
        variant="outline"
        size="icon"
        onClick={() => setOpen(true)}
        aria-label="راهنمای این صفحه"
        title="راهنمای این صفحه"
        className="h-8 w-8"
      >
        <HelpCircle className="h-4 w-4" />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-sm">
              <HelpCircle className="h-4 w-4" /> راهنمای این بخش
            </DialogTitle>
          </DialogHeader>

          {loading ? (
            <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
          ) : tabs.length === 0 ? (
            <p className="py-6 text-center text-xs text-muted-foreground">
              راهنمایی برای این بخش ثبت نشده است.
            </p>
          ) : (
            <div className="max-h-[60vh] space-y-4 overflow-y-auto">
              {tabs.map((tab) => (
                <div key={tab.title} className="space-y-1.5">
                  <h4 className="text-xs font-semibold text-foreground">{tab.title}</h4>
                  <p className="whitespace-pre-line text-[11px] leading-relaxed text-muted-foreground">
                    {tab.content}
                  </p>
                </div>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}
