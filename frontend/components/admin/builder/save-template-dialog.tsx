"use client";

import React, { useState } from "react";
import { BookmarkPlus, Loader2 } from "lucide-react";
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
import type { BuilderElement } from "@/types/builder";

interface SaveTemplateDialogProps {
  element: BuilderElement;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const TEMPLATE_CATEGORIES = [
  "عمومی",
  "هیرو و بنر",
  "محتوا و ویژگی‌ها",
  "قیمت‌گذاری و تعرفه",
  "فروش و تخفیف",
  "اعتماد و نظرات",
  "پشتیبانی و تماس",
];

export function SaveTemplateDialog({
  element,
  open,
  onOpenChange,
}: SaveTemplateDialogProps) {
  const { toast } = useToast();
  const [title, setTitle] = useState(element.name || "قالب بخش جدید");
  const [category, setCategory] = useState("عمومی");
  const [saving, setSaving] = useState(false);

  // Sync title when element changes or dialog re-opens
  React.useEffect(() => {
    if (open) {
      setTitle(element.name || "قالب بخش جدید");
    }
  }, [open, element.name]);

  const handleSave = async () => {
    if (!title.trim()) {
      toast({
        title: "خطا",
        description: "لطفاً عنوانی برای قالب بنویسید.",
        variant: "destructive",
      });
      return;
    }

    setSaving(true);
    try {
      const slug = `tpl-${Math.random().toString(36).slice(2, 10)}`;
      await pageTemplatesAdminApi.create({
        title: title.trim(),
        slug,
        template_type: "section",
        category,
        builder_data: {
          schemaVersion: 1,
          title: title.trim(),
          slug,
          globalStyles: {},
          rootElements: [element],
        },
      });

      toast({
        title: "قالب ذخیره شد",
        description: `قالب «${title.trim()}» با موفقیت در کتابخانه قالب‌ها ذخیره شد.`,
      });
      onOpenChange(false);
    } catch (err) {
      console.error("Save template error:", err);
      toast({
        title: "خطا در ذخیره قالب",
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
            <BookmarkPlus className="w-4 h-4 text-primary" />
            <span>ذخیره به عنوان قالب بخش (Save Section Template)</span>
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-2 text-xs">
          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">عنوان قالب</Label>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="h-8 text-xs"
              placeholder="مثلاً: هیرو بنر فروش ویژه"
            />
          </div>

          <div className="space-y-1.5">
            <Label className="text-xs font-semibold">دسته‌بندی قالب</Label>
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="h-8 text-xs">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TEMPLATE_CATEGORIES.map((cat) => (
                  <SelectItem key={cat} value={cat}>
                    {cat}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <DialogFooter className="flex items-center justify-end gap-2 pt-2">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} disabled={saving}>
            انصراف
          </Button>
          <Button size="sm" data-testid="save-section-template-submit-btn" onClick={handleSave} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="w-3.5 h-3.5 animate-spin ms-1" />
                <span>در حال ذخیره...</span>
              </>
            ) : (
              <span>ذخیره قالب</span>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
