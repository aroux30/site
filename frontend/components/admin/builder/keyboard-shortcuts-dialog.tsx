"use client";

import React from "react";
import { Keyboard, Command } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ShortcutGroup {
  category: string;
  items: { key: string; label: string; desc: string }[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    category: "اقدامات اصلی و تاریخچه",
    items: [
      { key: "Ctrl + S", label: "ذخیره پیش‌نویس", desc: "ثبت تغییرات صفحه در سرور و پیش‌نویس" },
      { key: "Ctrl + Z", label: "بازگشت (Undo)", desc: "بازگرداندن آخرین تغییر انجام‌شده" },
      { key: "Ctrl + Y / Ctrl+Shift+Z", label: "انجام مجدد (Redo)", desc: "اجرای مجدد تغییر بازگردانده‌شده" },
      { key: "Ctrl + D", label: "تکثیر المان", desc: "ایجاد یک نسخه همسان از المان فعال" },
    ],
  },
  {
    category: "کلیپ‌بورد و ویرایش",
    items: [
      { key: "Ctrl + C", label: "کپی المان", desc: "ذخیره المان فعال در کلیپ‌بورد صفحه‌ساز" },
      { key: "Ctrl + V", label: "چسباندن المان", desc: "درج المان کپی‌شده داخل یا بعد از المان فعال" },
      { key: "Delete / Backspace", label: "حذف المان", desc: "حذف المان یا المان‌های انتخاب‌شده" },
      { key: "Escape", label: "لغو انتخاب", desc: "خروج از حالت انتخاب المان و بستن منوها" },
    ],
  },
  {
    category: "ناوبری و تعامل مستقیم (الگوی المنتور)",
    items: [
      { key: "Alt + ↑ / ↓", label: "جابه‌جایی اتمیک", desc: "انتقال المان فعال به سطر بالا یا پایین" },
      { key: "دابل‌کلیک در بوم", label: "ویرایش متن درجا", desc: "تایپ مستقیم متن بدون نیاز به پنل بازرس" },
      { key: "دابل‌کلیک در لایه‌ها", label: "تغییرنام درختی", desc: "تغییر نام المان در ساختار نویگیتور" },
      { key: "کلیک راست", label: "منوی سریع (Context Menu)", desc: "دسترسی به تمامی ابزارهای المان" },
    ],
  },
];

export function KeyboardShortcutsDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl max-h-[85vh] overflow-y-auto select-none" dir="rtl">
        <DialogHeader className="border-b pb-3">
          <div className="flex items-center gap-2 text-primary font-bold">
            <Keyboard className="w-5 h-5" />
            <DialogTitle className="text-base">راهنمای کلیدهای میانبر (الگوی المنتور)</DialogTitle>
          </div>
          <p className="text-xs text-muted-foreground mt-1">
            با استفاده از این میانبرها سرعت ویرایش و طراحی برگه‌ها را چند برابر کنید.
          </p>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {SHORTCUT_GROUPS.map((grp) => (
            <div key={grp.category} className="space-y-2">
              <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                <Command className="w-3.5 h-3.5 text-primary" />
                <span>{grp.category}</span>
              </h4>

              <div className="rounded-xl border border-border/70 divide-y divide-border/50 bg-card overflow-hidden">
                {grp.items.map((item) => (
                  <div
                    key={item.key}
                    className="flex items-center justify-between p-2.5 text-xs hover:bg-muted/40 transition"
                  >
                    <div className="space-y-0.5">
                      <span className="font-semibold text-foreground block">{item.label}</span>
                      <span className="text-[10px] text-muted-foreground">{item.desc}</span>
                    </div>

                    <kbd className="px-2 py-1 text-[11px] font-mono font-bold bg-muted/80 text-foreground border border-border/80 rounded-md shadow-2xs shrink-0" dir="ltr">
                      {item.key}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
