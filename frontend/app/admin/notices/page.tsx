"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Bell, RefreshCw, Plus, Eye, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { sanitizeHtml } from "@/lib/sanitize";

interface Notice {
  id: string;
  title: string;
  content_html: string;
  notice_type: "banner" | "popup" | "alert_bar";
  target_page: string;
  start_at: string;
  end_at: string;
  is_active: boolean;
}

export default function AdminNoticesPage() {
  const { toast } = useToast();
  const [notices, setNotices] = useState<Notice[]>([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [noticeType, setNoticeType] = useState("popup");
  const [targetPage, setTargetPage] = useState("all");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [creating, setCreating] = useState(false);

  const fetchNotices = useCallback(async () => {
    setLoading(true);
    try {
      const res = await apiClient.get("/notifications/notices/admin/all");
      setNotices(Array.isArray(res.data) ? res.data : []);
    } catch {
      toast({ title: "خطا", description: "بارگذاری اعلانات با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchNotices();
  }, [fetchNotices]);

  const createNotice = async () => {
    if (!title.trim() || !content.trim()) {
      toast({ title: "خطا", description: "عنوان و محتوای اطلاعیه الزامی است", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      await apiClient.post("/notifications/notices/admin", {
        title,
        content_html: content,
        notice_type: noticeType,
        target_page: targetPage,
        start_at: startDate ? new Date(startDate).toISOString() : undefined,
        end_at: endDate ? new Date(endDate).toISOString() : undefined,
      });
      toast({ title: "موفق", description: "اطلاعیه جدید ایجاد شد" });
      setCreateOpen(false);
      setTitle("");
      setContent("");
      fetchNotices();
    } catch {
      toast({ title: "خطا", description: "ایجاد اطلاعیه با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const typeLabels: Record<string, string> = {
    banner: "بنر",
    popup: "پاپ‌آپ",
    alert_bar: "نوار هشدار",
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Bell className="h-5 w-5 text-primary" />
            اعلانات زمان‌دار
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            ایجاد و مدیریت اطلاعیه‌ها، بنرها و پاپ‌آپ‌های زمان‌دار
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={fetchNotices}>
            <RefreshCw className="h-4 w-4 mr-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setCreateOpen(true)}>
            <Plus className="h-4 w-4 mr-2" />
            اطلاعیه جدید
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : notices.length === 0 ? (
        <Card className="p-12 text-center">
          <Bell className="h-12 w-12 mx-auto mb-3 opacity-30" />
          <p className="text-sm text-muted-foreground">هنوز هیچ اطلاعیه‌ای ایجاد نشده است</p>
          <Button size="sm" className="mt-4" onClick={() => setCreateOpen(true)}>
            ایجاد اولین اطلاعیه
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {notices.map((n) => (
            <Card key={n.id} className="p-5">
              <div className="flex items-start justify-between">
                <div className="space-y-1">
                  <h4 className="font-semibold text-sm">{n.title}</h4>
                  <div className="flex gap-2">
                    <Badge variant="outline">{typeLabels[n.notice_type]}</Badge>
                    <Badge variant="outline">صفحه: {n.target_page}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground" dir="ltr">
                    {new Date(n.start_at).toLocaleDateString("fa-IR")} - {new Date(n.end_at).toLocaleDateString("fa-IR")}
                  </p>
                </div>
                <Badge className={n.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}>
                  {n.is_active ? "فعال" : "غیرفعال"}
                </Badge>
              </div>
              <div
                className="mt-3 text-xs text-muted-foreground line-clamp-2 prose prose-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: sanitizeHtml(n.content_html) }}
              />
            </Card>
          ))}
        </div>
      )}

      {/* Create Notice Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>ایجاد اطلاعیه جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>عنوان</Label>
              <Input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>محتوا (HTML)</Label>
              <Textarea rows={4} value={content} onChange={(e) => setContent(e.target.value)} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>نوع</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={noticeType}
                  onChange={(e) => setNoticeType(e.target.value)}
                >
                  <option value="popup">پاپ‌آپ</option>
                  <option value="banner">بنر</option>
                  <option value="alert_bar">نوار هشدار</option>
                </select>
              </div>
              <div className="space-y-2">
                <Label>صفحه هدف</Label>
                <select
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={targetPage}
                  onChange={(e) => setTargetPage(e.target.value)}
                >
                  <option value="all">همه صفحات</option>
                  <option value="home">صفحه اصلی</option>
                  <option value="checkout">تسویه‌حساب</option>
                  <option value="dashboard">پنل کاربری</option>
                </select>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>تاریخ شروع</Label>
                <Input type="datetime-local" value={startDate} onChange={(e) => setStartDate(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>تاریخ پایان</Label>
                <Input type="datetime-local" value={endDate} onChange={(e) => setEndDate(e.target.value)} />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>انصراف</Button>
            <Button onClick={createNotice} disabled={creating}>
              {creating ? "در حال ایجاد..." : "ایجاد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
