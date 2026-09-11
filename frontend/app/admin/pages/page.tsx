"use client";

import React, { useState } from "react";
import Link from "next/link";
import {
  FileText,
  ExternalLink,
  Edit2,
  CheckCircle2,
  Clock,
  Plus,
  Search,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { toPersianDigits } from "@/lib/utils";

interface PageItem {
  id: string;
  title: string;
  slug: string;
  route: string;
  status: "published" | "draft";
  updated_at: string;
}

const initialPages: PageItem[] = [
  { id: "p-1", title: "صفحه اصلی فروشگاه", slug: "home", route: "/", status: "published", updated_at: "۱۴۰۳/۰۶/۱۱" },
  { id: "p-2", title: "درباره ما", slug: "about", route: "/about", status: "published", updated_at: "۱۴۰۳/۰۶/۰۸" },
  { id: "p-3", title: "تماس با ما و پشتیبانی", slug: "contact", route: "/contact", status: "published", updated_at: "۱۴۰۳/۰۶/۰۵" },
  { id: "p-4", title: "سوالات متداول (FAQ)", slug: "faq", route: "/faq", status: "published", updated_at: "۱۴۰۳/۰۵/۲۸" },
  { id: "p-5", title: "قوانین و مقررات استفاده", slug: "terms", route: "/terms", status: "published", updated_at: "۱۴۰۳/۰۵/۲۰" },
  { id: "p-6", title: "سیاست حفظ حریم خصوصی", slug: "privacy", route: "/privacy", status: "published", updated_at: "۱۴۰۳/۰۵/۱۵" },
  { id: "p-7", title: "رویه بازگرداندن کالا", slug: "returns", route: "/returns", status: "published", updated_at: "۱۴۰۳/۰۶/۰۱" },
  { id: "p-8", title: "باشگاه مشتریان و جوایز", slug: "rewards", route: "/rewards", status: "published", updated_at: "۱۴۰۳/۰۶/۰۷" },
];

export default function AdminCMSPagesPage() {
  const [pages] = useState<PageItem[]>(initialPages);
  const [search, setSearch] = useState("");

  const filteredPages = pages.filter(
    (p) => p.title.includes(search) || p.route.includes(search)
  );

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-foreground">مدیریت صفحات فروشگاه (CMS)</h1>
          <p className="text-sm text-muted-foreground">
            مشاهده، ویرایش و مدیریت صفحات اطلاع‌رسانی، شرایط و قوانین
          </p>
        </div>
      </div>

      {/* Filter Bar */}
      <Card className="p-4">
        <div className="relative">
          <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="جستجو بر اساس عنوان یا آدرس صفحه..."
            className="pr-9"
          />
        </div>
      </Card>

      {/* Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-right text-sm">
            <thead className="border-b border-border bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-4 py-3">عنوان صفحه</th>
                <th className="px-4 py-3">مسیر (Route)</th>
                <th className="px-4 py-3">وضعیت انتشار</th>
                <th className="px-4 py-3">آخرین به‌روزرسانی</th>
                <th className="px-4 py-3 text-center">مشاهده و عملیات</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredPages.map((page) => (
                <tr key={page.id} className="transition-colors hover:bg-muted/30">
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5 font-medium text-foreground">
                      <FileText className="h-4 w-4 text-primary" />
                      {page.title}
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">
                    {page.route}
                  </td>
                  <td className="px-4 py-3">
                    <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-600">
                      <CheckCircle2 className="h-3.5 w-3.5" /> منتشر شده
                    </span>
                  </td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {toPersianDigits(page.updated_at)}
                  </td>
                  <td className="px-4 py-3 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <Button variant="outline" size="sm" asChild className="h-8 gap-1.5 text-xs">
                        <Link href={page.route} target="_blank">
                          <ExternalLink className="h-3.5 w-3.5" /> مشاهده در سایت
                        </Link>
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
