"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  FileText,
  Mail,
  Trash2,
  CheckCircle2,
  Clock,
  Eye,
  RefreshCw,
  Search,
  Filter,
  Check,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  formSubmissionsAdminApi,
  type FormSubmissionItem,
} from "@/lib/api/content";

export default function AdminFormsPage() {
  const { toast } = useToast();
  const [submissions, setSubmissions] = useState<FormSubmissionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [searchFormId, setSearchFormId] = useState("");
  const [page, setPage] = useState(1);
  const [selectedSubmission, setSelectedSubmission] = useState<FormSubmissionItem | null>(null);

  const fetchSubmissions = useCallback(async () => {
    setLoading(true);
    try {
      const res = await formSubmissionsAdminApi.list({
        form_id: searchFormId.trim() || undefined,
        unread_only: unreadOnly,
        page,
        page_size: 20,
      });
      setSubmissions(res.items || []);
      setTotal(res.total || 0);
    } catch (err) {
      console.error("Failed to load submissions:", err);
      toast({
        title: "خطا در بارگذاری",
        description: "دریافت لیست پیام‌های فرم با خطا مواجه شد.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [searchFormId, unreadOnly, page, toast]);

  useEffect(() => {
    fetchSubmissions();
  }, [fetchSubmissions]);

  const handleToggleRead = async (item: FormSubmissionItem, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const updated = await formSubmissionsAdminApi.markRead(item.id, !item.is_read);
      setSubmissions((prev) =>
        prev.map((s) => (s.id === item.id ? { ...s, is_read: updated.is_read } : s))
      );
      toast({
        title: updated.is_read ? "علامت‌گذاری به عنوان خوانده‌شده" : "علامت‌گذاری به عنوان خوانده‌نشده",
      });
    } catch {
      toast({ title: "خطا در تغییر وضعیت", variant: "destructive" });
    }
  };

  const handleDelete = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await formSubmissionsAdminApi.delete(id);
      setSubmissions((prev) => prev.filter((s) => s.id !== id));
      setTotal((prev) => Math.max(0, prev - 1));
      if (selectedSubmission?.id === id) setSelectedSubmission(null);
      toast({ title: "پیام حذف شد" });
    } catch {
      toast({ title: "خطا در حذف پیام", variant: "destructive" });
    }
  };

  return (
    <div className="p-6 space-y-6 max-w-7xl mx-auto" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b pb-4">
        <div className="space-y-1">
          <h1 className="text-xl font-bold flex items-center gap-2 text-foreground">
            <Mail className="w-5 h-5 text-primary" />
            <span>پیام‌ها و فرم‌های دریافتی (Form Submissions)</span>
          </h1>
          <p className="text-xs text-muted-foreground leading-relaxed">
            مشاهده و مدیریت اطلاعات ارسال‌شده توسط کاربران از طریق فرم‌های Visual Page Builder
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={fetchSubmissions}
            disabled={loading}
            className="h-8 gap-1.5 text-xs"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
            <span>بروزرسانی</span>
          </Button>
        </div>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 bg-muted/40 p-3 rounded-xl border">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 sm:w-64">
            <Search className="w-3.5 h-3.5 absolute start-2.5 top-2.5 text-muted-foreground" />
            <Input
              value={searchFormId}
              onChange={(e) => setSearchFormId(e.target.value)}
              placeholder="جستجو با شناسه فرم (Form ID)..."
              className="ps-8 h-8 text-xs bg-background"
            />
          </div>
          <Button
            variant={unreadOnly ? "default" : "outline"}
            size="sm"
            onClick={() => setUnreadOnly(!unreadOnly)}
            className="h-8 gap-1.5 text-xs shrink-0"
          >
            <Filter className="w-3.5 h-3.5" />
            <span>{unreadOnly ? "فقط خوانده‌نشده‌ها" : "همه پیام‌ها"}</span>
          </Button>
        </div>

        <div className="text-xs text-muted-foreground self-center">
          مجموع پیام‌ها: <span className="font-bold text-foreground">{total}</span>
        </div>
      </div>

      {/* Submissions List */}
      {loading ? (
        <div className="py-20 text-center text-xs text-muted-foreground flex flex-col items-center gap-2">
          <RefreshCw className="w-5 h-5 animate-spin text-primary" />
          <span>در حال دریافت پیام‌ها...</span>
        </div>
      ) : submissions.length === 0 ? (
        <div className="py-20 border border-dashed rounded-2xl text-center space-y-2 text-muted-foreground">
          <FileText className="w-8 h-8 opacity-30 mx-auto" />
          <p className="text-xs font-semibold text-foreground">هیچ پیامی یافت نشد</p>
          <p className="text-[11px]">
            فرم‌های ساخته شده با ویجت Form Builder پس از ارسال اطلاعات توسط کاربران در این بخش لیست می‌شوند.
          </p>
        </div>
      ) : (
        <div className="rounded-xl border overflow-hidden bg-card shadow-xs">
          <div className="overflow-x-auto">
            <table className="w-full text-right text-xs">
              <thead className="bg-muted/60 border-b text-muted-foreground">
                <tr>
                  <th className="p-3 font-semibold">وضعیت</th>
                  <th className="p-3 font-semibold">شناسه فرم</th>
                  <th className="p-3 font-semibold">برگه مبدا</th>
                  <th className="p-3 font-semibold">خلاصه داده‌ها</th>
                  <th className="p-3 font-semibold">تاریخ ثبت</th>
                  <th className="p-3 font-semibold text-center">عملیات</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {submissions.map((sub) => {
                  const dataEntries = Object.entries(sub.data || {});
                  return (
                    <tr
                      key={sub.id}
                      onClick={() => setSelectedSubmission(sub)}
                      className={`hover:bg-muted/40 transition cursor-pointer ${
                        !sub.is_read ? "bg-primary/5 font-semibold" : ""
                      }`}
                    >
                      <td className="p-3">
                        {sub.is_read ? (
                          <Badge variant="outline" className="text-[10px] text-muted-foreground">
                            خوانده شده
                          </Badge>
                        ) : (
                          <Badge className="bg-primary text-primary-foreground text-[10px]">
                            جدید
                          </Badge>
                        )}
                      </td>
                      <td className="p-3 font-mono text-[11px] text-foreground">
                        {sub.form_id}
                      </td>
                      <td className="p-3 text-muted-foreground">
                        {sub.page_slug || "نامشخص"}
                      </td>
                      <td className="p-3 max-w-xs truncate text-muted-foreground">
                        {dataEntries
                          .slice(0, 3)
                          .map(([k, v]) => `${k}: ${String(v)}`)
                          .join(" | ")}
                      </td>
                      <td className="p-3 text-muted-foreground text-[11px] whitespace-nowrap">
                        {new Date(sub.created_at).toLocaleString("fa-IR")}
                      </td>
                      <td className="p-3 text-center whitespace-nowrap" onClick={(e) => e.stopPropagation()}>
                        <div className="flex items-center justify-center gap-1">
                          <button
                            type="button"
                            onClick={(e) => {
                              setSelectedSubmission(sub);
                            }}
                            className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-foreground"
                            title="مشاهده جزئیات کامل"
                          >
                            <Eye className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleToggleRead(sub, e)}
                            className="p-1.5 hover:bg-muted rounded text-muted-foreground hover:text-primary"
                            title={sub.is_read ? "تبدیل به خوانده‌نشده" : "علامت‌گذاری خوانده‌شده"}
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={(e) => handleDelete(sub.id, e)}
                            className="p-1.5 hover:bg-destructive/10 rounded text-destructive"
                            title="حذف پیام"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Details Dialog */}
      <Dialog
        open={Boolean(selectedSubmission)}
        onOpenChange={(open) => !open && setSelectedSubmission(null)}
      >
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Mail className="w-4 h-4 text-primary" />
              <span>جزئیات پیام فرم: {selectedSubmission?.form_id}</span>
            </DialogTitle>
          </DialogHeader>

          {selectedSubmission && (
            <div className="space-y-4 py-2 text-xs">
              <div className="grid grid-cols-2 gap-2 p-3 bg-muted/40 rounded-xl border text-[11px]">
                <div>
                  <span className="text-muted-foreground">تاریخ ارسال:</span>{" "}
                  <span className="font-semibold">
                    {new Date(selectedSubmission.created_at).toLocaleString("fa-IR")}
                  </span>
                </div>
                <div>
                  <span className="text-muted-foreground">برگه:</span>{" "}
                  <span className="font-semibold">
                    {selectedSubmission.page_slug || "نامشخص"}
                  </span>
                </div>
                {selectedSubmission.ip_address && (
                  <div>
                    <span className="text-muted-foreground">آدرس IP:</span>{" "}
                    <span className="font-mono">{selectedSubmission.ip_address}</span>
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <span className="font-bold text-foreground block">داده‌های ثبت‌شده فیلدها:</span>
                <div className="space-y-2 max-h-60 overflow-y-auto p-3 bg-card border rounded-xl divide-y">
                  {Object.entries(selectedSubmission.data || {}).map(([key, val]) => (
                    <div key={key} className="pt-2 first:pt-0">
                      <span className="text-muted-foreground font-semibold block text-[11px]">
                        {key}:
                      </span>
                      <p className="text-foreground leading-relaxed whitespace-pre-wrap mt-0.5">
                        {String(val)}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          <DialogFooter className="flex items-center justify-between gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setSelectedSubmission(null)}
            >
              بستن
            </Button>
            {selectedSubmission && (
              <Button
                variant={selectedSubmission.is_read ? "secondary" : "default"}
                size="sm"
                onClick={(e) => {
                  handleToggleRead(selectedSubmission, e);
                  setSelectedSubmission(null);
                }}
              >
                {selectedSubmission.is_read ? "علامت خوانده‌نشده" : "علامت به عنوان خوانده‌شده"}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
