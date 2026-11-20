"use client";

import React, { useState } from "react";
import { Bookmark, Loader2 } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { pageTemplatesAdminApi } from "@/lib/api/content";
import { useBuilderStore } from "@/stores/builder-store";

interface SavePageTemplateDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const PAGE_TEMPLATE_CATEGORIES = [
  "صفحات فرود (Landing)",
  "صفحات فروشگاهی",
  "درباره ما و معرفی",
  "تماس و ارتباط",
  "وبلاگ و مقالات",
  "عمومی",
];

export function SavePageTemplateDialog({
  open,
  onOpenChange,
}: SavePageTemplateDialogProps) {
  const { toast } = useToast();
  const ast = useBuilderStore((s) => s.ast);
  const [title, setTitle] = useState(ast.title ? `قالب ${ast.title}` : "قالب برگه جدید");
  const [category, setCategory] = useState("صفحات فرود (Landing)");
  const [saving, setSaving] = useState(false);

  React.useEffect(() => {
    if (open) {
      setTitle(ast.title ? `قالب ${ast.title}` : "قالب برگه جدید");
    }
  }, [open, ast.title]);

  const handleSave = async () => {
    if (!title.trim()) {
      toast({
        title: "خطا",
        description: "لطفاً عنوانی برای قالب برگه وارد کنید.",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const slug = `page-tpl-${Math.random().toString(36).slice(2, 10)}`;
      await pageTemplatesAdminApi.create({
        title: title.trim(),
        slug,
        template_type: "page",
        category,
        builder_data: {
          schemaVersion: ast.schemaVersion || 1,
          title: title.trim(),
          slug,
          globalStyles: ast.globalStyles || {},
          rootElements: ast.rootElements,
        },
      });

      toast({
        title: "قالب برگه ذخیره شد",
        description: `قالب کامل برگه «${title.trim()}» با موفقیت در کتابخانه قالب‌ها ثبت شد.`,
      });
      onOpenChange(false);
    } catch (err) {
      console.error("Save page template error:", err);
      toast({
        title: "خطا در ذخیره قالب برگه",
        description: "ثبت قالب در پایگاه‌داده با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2 text-base font-bold">
            <Bookmark className="w-4 h-4 text-primary" />
            <span>ذخیره کل برگه به عنوان قالب (Save Page Template)</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">عنوان قالب برگه</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-8 text-xs"
              placeholder="مثلاً: لندینگ پیج معرفی محصول جدید"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">دسته‌بندی</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PAGE_TEMPLATE_CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="p-2.5 rounded-lg border bg-muted/30 text-muted-foreground text-[11px] leading-relaxed">
            این قالب شامل کلیه سکشن‌ها، کانتینرها، ویجت‌ها ({ast.rootElements.length} عنصر اصلی) و استایل‌های سراسری این برگه خواهد بود.
          </div>
        </div>

        <DialogFooter className="flex items-center justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={saving}>
            انصراف
          </Button>
          <Button size="sm" onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin ms-1" />
                <span>در حال ذخیره...</span>
              </>
            ) : (
              <span>ذخیره قالب برگه</span>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
