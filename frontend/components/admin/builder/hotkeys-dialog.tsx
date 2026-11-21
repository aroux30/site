"use client";

import React from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Keyboard, Command, MousePointer, Layers, Sparkles } from "lucide-react";

interface HotkeysDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function HotkeysDialog({ open, onOpenChange }: HotkeysDialogProps) {
  const groups = [
    {
      category: "اقدامات و ویرایش عمومی",
      icon: Command,
      items: [
        { label: "بازگردانی آخرین تغییر (Undo)", keys: ["Ctrl", "Z"] },
        { label: "تکرار تغییر بازگردانده شده (Redo)", keys: ["Ctrl", "Shift", "Z"] },
        { label: "کپی المان انتخاب‌شده", keys: ["Ctrl", "C"] },
        { label: "چسباندن المان از کلیپ‌بورد", keys: ["Ctrl", "V"] },
        { label: "چسباندن استایل‌ها (Paste Style)", keys: ["Ctrl", "Shift", "V"] },
        { label: "تکثیر سریع المان", keys: ["Ctrl", "D"] },
        { label: "حذف المان انتخاب‌شده", keys: ["Delete"] },
        { label: "لغو انتخاب المان", keys: ["Escape"] },
      ],
    },
    {
      category: "تعامل مستقیم با بوم و لایه‌ها",
      icon: MousePointer,
      items: [
        { label: "ویرایش مستقیم متن روی بوم (Inline Edit)", keys: ["دابل‌کلیک"] },
        { label: "منوی پیشرفته گزینه‌ها (Context Menu)", keys: ["راست‌کلیک"] },
        { label: "تغییر نام لایه در ساختار درختی", keys: ["دابل‌کلیک روی لایه"] },
        { label: "انتقال المان به بالا / پایین", keys: ["Alt", "↑ / ↓"] },
        { label: "جابه‌جایی المان با درگ", keys: ["کشیدن با دستگیره"] },
      ],
    },
    {
      category: "ناوبری و نماهای استودیو",
      icon: Layers,
      items: [
        { label: "راهنمای کلیدهای میانبر (این پنجره)", keys: ["Shift", "?"] },
        { label: "چرخش بین ویوپورت‌های ریسپانسیو (Elementor)", keys: ["Ctrl", "Shift", "M"] },
        { label: "سوییچ بین تب‌های بلوک‌ها و لایه‌ها", keys: ["کلیک روی تب"] },
        { label: "انتخاب ساختار کانتینر جدید", keys: ["کلیک + در کانتینر"] },
        { label: "بازنشانی استایل‌های سراسری", keys: ["دیالوگ استایل سراسری"] },
      ],
    },
  ];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto" dir="rtl" data-testid="hotkeys-modal">
        <DialogHeader>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-primary/10 text-primary">
              <Keyboard className="w-5 h-5" />
            </div>
            <div>
              <DialogTitle className="text-base font-bold">
                راهنمای کلیدهای میانبر صفحه‌ساز (Elementor Hotkeys Parity)
              </DialogTitle>
              <DialogDescription className="text-xs text-muted-foreground mt-0.5">
                کلیدهای میانبر و حرکات ماوس برای طراحی سریع‌تر صفحات و بخش‌ها
              </DialogDescription>
            </div>
          </div>
        </DialogHeader>

        <div className="space-y-5 py-2">
          {groups.map((grp) => {
            const Icon = grp.icon;
            return (
              <div key={grp.category} className="space-y-2">
                <div className="flex items-center gap-1.5 text-xs font-bold text-foreground border-b border-border/60 pb-1.5">
                  <Icon className="w-4 h-4 text-primary" />
                  <span>{grp.category}</span>
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  {grp.items.map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center justify-between p-2 rounded-lg bg-muted/40 border border-border/50 text-xs"
                    >
                      <span className="text-muted-foreground text-[11px] font-medium">{item.label}</span>
                      <div className="flex items-center gap-1 shrink-0 ms-2">
                        {item.keys.map((k) => (
                          <kbd
                            key={k}
                            className="px-1.5 py-0.5 rounded bg-background border border-border/80 shadow-2xs font-mono text-[10px] font-bold text-foreground"
                          >
                            {k}
                          </kbd>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
