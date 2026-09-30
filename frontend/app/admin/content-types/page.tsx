"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Database, Plus, RefreshCw, Trash2, ChevronDown, ChevronLeft } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  contentTypesApi,
  type ContentEntryRow,
  type ContentTypeDef,
  type ContentTypeField,
} from "@/lib/api/cms-admin";
import { toPersianDigits } from "@/lib/utils";

const FIELD_TYPES = [
  "string", "text", "richtext", "integer", "decimal", "boolean",
  "date", "datetime", "email", "url", "slug", "enum", "media",
] as const;

export default function AdminContentTypesPage() {
  const { toast } = useToast();
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const [entries, setEntries] = useState<ContentEntryRow[]>([]);
  const [entriesLoading, setEntriesLoading] = useState(false);

  // create-type dialog
  const [open, setOpen] = useState(false);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [kind, setKind] = useState("collection");
  const [fieldsJson, setFieldsJson] = useState(
    '[\n  { "name": "title", "type": "string", "required": true }\n]'
  );
  const [saving, setSaving] = useState(false);

  // create/edit entry dialog
  const [entryOpen, setEntryOpen] = useState(false);
  const [editingEntry, setEditingEntry] = useState<ContentEntryRow | null>(null);
  const [entryJson, setEntryJson] = useState("{}");
  const [entryStatus, setEntryStatus] = useState("draft");
  const [entryLocale, setEntryLocale] = useState("fa");
  const [entrySchedPub, setEntrySchedPub] = useState("");
  const [entrySaving, setEntrySaving] = useState(false);

  // revision dialog
  const [revOpen, setRevOpen] = useState(false);
  const [revEntry, setRevEntry] = useState<ContentEntryRow | null>(null);
  const [revRows, setRevRows] = useState<Array<{ id: string; revision_number: number; status: string; created_at: string | null }>>([]);
  const [revLoading, setRevLoading] = useState(false);

  const {
    data: types = [],
    loading,
    reload: load,
  } = useAdminQuery<ContentTypeDef[]>({
    queryKey: ["admin", "content-types"],
    queryFn: async () => {
      return await contentTypesApi.list();
    },
    fallbackError: "بارگذاری تایپ‌های محتوا ناموفق بود",
  });

  const toggleEntries = async (slugValue: string) => {
    if (openSlug === slugValue) {
      setOpenSlug(null);
      return;
    }
    setOpenSlug(slugValue);
    setEntriesLoading(true);
    try {
      setEntries(await contentTypesApi.listEntries(slugValue));
    } catch {
      setEntries([]);
    } finally {
      setEntriesLoading(false);
    }
  };

  const createType = async () => {
    let fields: ContentTypeField[];
    try {
      fields = JSON.parse(fieldsJson);
      if (!Array.isArray(fields)) throw new Error("not-array");
    } catch {
      toast({ title: "خطا", description: "JSON فیلدها معتبر نیست", variant: "destructive" });
      return;
    }
    if (!slug.trim() || !name.trim()) {
      toast({ title: "خطا", description: "نامک و نام الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      await contentTypesApi.create({ slug: slug.trim(), name: name.trim(), kind, fields });
      toast({ title: "موفق", description: "تایپ محتوا ساخته شد" });
      setOpen(false);
      setSlug(""); setName("");
      load();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "ایجاد ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const openCreateEntry = () => {
    setEditingEntry(null);
    setEntryJson("{}");
    setEntryStatus("draft");
    setEntryLocale("fa");
    setEntrySchedPub("");
    setEntryOpen(true);
  };

  const openEditEntry = (e: ContentEntryRow) => {
    setEditingEntry(e);
    setEntryJson(JSON.stringify(e.data ?? {}, null, 2));
    setEntryStatus(e.status ?? "draft");
    setEntryLocale(e.locale ?? "fa");
    setEntrySchedPub("");
    setEntryOpen(true);
  };

  const saveEntry = async () => {
    if (!openSlug) return;
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(entryJson);
    } catch {
      toast({ title: "خطا", description: "JSON ورودی معتبر نیست", variant: "destructive" });
      return;
    }
    setEntrySaving(true);
    try {
      if (editingEntry) {
        await contentTypesApi.updateEntry(editingEntry.id, {
          data,
          status: entryStatus,
          scheduled_publish_at: entrySchedPub ? new Date(entrySchedPub).toISOString() : undefined,
        });
        toast({ title: "موفق", description: "ورودی به‌روزرسانی شد" });
      } else {
        await contentTypesApi.createEntry(openSlug, {
          data,
          status: entryStatus,
          locale: entryLocale,
          scheduled_publish_at: entrySchedPub ? new Date(entrySchedPub).toISOString() : undefined,
        });
        toast({ title: "موفق", description: "ورودی ساخته شد" });
      }
      setEntryOpen(false);
      setEntries(await contentTypesApi.listEntries(openSlug));
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "ذخیره ورودی ناموفق بود", variant: "destructive" });
    } finally {
      setEntrySaving(false);
    }
  };

  const restoreEntry = async (id: string) => {
    if (!openSlug) return;
    try {
      await contentTypesApi.restoreEntry(id);
      toast({ title: "ورودی بازگردانده شد" });
      await refreshEntries();
    } catch {
      toast({ title: "خطا", description: "بازگردانی ناموفق بود", variant: "destructive" });
    }
  };

  const permanentDeleteEntry = async (id: string) => {
    if (!openSlug || !confirm("حذف دائم ورودی؟ دیگر قابل بازگشت نیست.")) return;
    try {
      await contentTypesApi.permanentDeleteEntry(id);
      toast({ title: "ورودی برای همیشه حذف شد" });
      await refreshEntries();
    } catch {
      toast({ title: "خطا", description: "ابتدا باید به سطل زباله منتقل شود", variant: "destructive" });
    }
  };

  const refreshEntries = async () => {
    if (!openSlug) return;
    setEntries(await contentTypesApi.listEntries(openSlug));
  };

  const openRevisions = async (e: ContentEntryRow) => {
    setRevEntry(e);
    setRevOpen(true);
    setRevLoading(true);
    try {
      setRevRows(await contentTypesApi.revisions(e.id));
    } catch {
      setRevRows([]);
    } finally {
      setRevLoading(false);
    }
  };

  const restoreEntryRevision = async (n: number) => {
    if (!revEntry) return;
    if (!confirm(`بازگردانی به نسخه ${toPersianDigits(String(n))}؟`)) return;
    try {
      await contentTypesApi.restoreRevision(revEntry.id, n);
      toast({ title: "نسخه بازگردانده شد" });
      setRevOpen(false);
      await refreshEntries();
    } catch {
      toast({ title: "خطا", description: "بازگردانی ناموفق بود", variant: "destructive" });
    }
  };

  const trashEntry = async (id: string) => {
    if (!openSlug || !confirm("ورودی به سطل زباله منتقل شود؟")) return;
    try {
      await contentTypesApi.trashEntry(id);
      await refreshEntries();
    } catch {
      toast({ title: "خطا", description: "انتقال به سطل ناموفق بود", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Database className="h-5 w-5 text-primary" />
            سازنده‌ی تایپ محتوا
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            تایپ‌های محتوای سفارشی با فیلدهای معتبرسازی‌شده — به سبک Strapi
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <Button size="sm" onClick={() => setOpen(true)}>
            <Plus className="h-4 w-4 ms-1" />
            تایپ جدید
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : types.length === 0 ? (
        <Card className="p-6">
          <p className="text-sm text-muted-foreground text-center py-4">
            هنوز تایپ محتوایی تعریف نشده است
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {types.map((t) => (
            <Card key={t.id} className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <Button variant="ghost" size="sm" onClick={() => toggleEntries(t.slug)}>
                    {openSlug === t.slug ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronLeft className="h-4 w-4" />
                    )}
                  </Button>
                  <div>
                    <p className="font-medium text-sm">{t.name}</p>
                    <p className="text-xs text-muted-foreground font-mono" dir="ltr">{t.slug}</p>
                  </div>
                  <Badge variant="outline">{t.kind === "single" ? "تکی" : "مجموعه"}</Badge>
                  <Badge variant="secondary">{toPersianDigits(String(t.fields.length))} فیلد</Badge>
                </div>
                {openSlug === t.slug && (
                  <Button size="sm" variant="outline" onClick={openCreateEntry}>
                    <Plus className="h-4 w-4 ms-1" />
                    ورودی جدید
                  </Button>
                )}
              </div>
              {openSlug === t.slug && (
                <div className="mt-4 border-t pt-4">
                  {entriesLoading ? (
                    <div className="flex justify-center py-4">
                      <RefreshCw className="h-4 w-4 animate-spin" />
                    </div>
                  ) : entries.length === 0 ? (
                    <p className="text-xs text-muted-foreground text-center py-3">
                      ورودی‌ای وجود ندارد
                    </p>
                  ) : (
                    <div className="space-y-2">
                      {entries.map((e) => (
                        <div key={e.id} className="flex items-center justify-between rounded border p-2">
                          <div className="text-xs font-mono truncate max-w-md" dir="ltr">
                            {JSON.stringify(e.data).slice(0, 120)}
                          </div>
                          <div className="flex items-center gap-1.5">
                            <Badge
                              variant="outline"
                              className={
                                e.status === "published"
                                  ? "text-emerald-500"
                                  : "text-muted-foreground"
                              }
                            >
                              {e.status ?? "draft"}
                            </Badge>
                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => openEditEntry(e)}>
                              ویرایش
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => openRevisions(e)}>
                              نسخه‌ها
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => restoreEntry(e.id)} title="بازگردانی از سطل (اگر در سطل باشد)">
                              بازگردانی
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => trashEntry(e.id)} title="انتقال به سطل زباله">
                              <Trash2 className="h-3.5 w-3.5 text-destructive" />
                            </Button>
                            <Button size="sm" variant="ghost" className="h-7 px-2 text-xs text-destructive" onClick={() => permanentDeleteEntry(e.id)} title="حذف دائم (فقط از سطل)">
                              حذف دائم
                            </Button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* Create type */}
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>تایپ محتوای جدید</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label>نام</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="اخبار" />
              </div>
              <div className="space-y-2">
                <Label>نامک (لاتین)</Label>
                <Input dir="ltr" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="news" />
              </div>
            </div>
            <div className="space-y-2">
              <Label>نوع</Label>
              <Select value={kind} onValueChange={setKind}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="collection">مجموعه (چند ورودی)</SelectItem>
                  <SelectItem value="single">تکی (یک ورودی)</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>فیلدها (JSON) — انواع: {FIELD_TYPES.join(", ")}</Label>
              <Textarea
                dir="ltr"
                rows={8}
                className="font-mono text-xs text-left"
                value={fieldsJson}
                onChange={(e) => setFieldsJson(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>انصراف</Button>
            <Button onClick={createType} disabled={saving}>
              {saving ? "در حال ساخت..." : "ساخت تایپ"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Create/Edit entry */}
      <Dialog open={entryOpen} onOpenChange={setEntryOpen}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle>
              {editingEntry ? "ویرایش ورودی" : "ورودی جدید"} — {openSlug}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>داده (JSON مطابق اسکیمای تایپ)</Label>
              <Textarea
                dir="ltr"
                rows={8}
                className="font-mono text-xs text-left"
                value={entryJson}
                onChange={(e) => setEntryJson(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <div className="space-y-2">
                <Label>وضعیت</Label>
                <select
                  value={entryStatus}
                  onChange={(e) => setEntryStatus(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                >
                  <option value="draft">پیش‌نویس</option>
                  <option value="published">منتشر شده</option>
                  <option value="archived">بایگانی</option>
                </select>
              </div>
              {!editingEntry && (
                <div className="space-y-2">
                  <Label>زبان</Label>
                  <select
                    value={entryLocale}
                    onChange={(e) => setEntryLocale(e.target.value)}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  >
                    <option value="fa">فارسی</option>
                    <option value="en">English</option>
                    <option value="ar">العربية</option>
                  </select>
                </div>
              )}
              <div className="space-y-2">
                <Label>انتشار زمان‌بندی‌شده</Label>
                <Input
                  type="datetime-local"
                  dir="ltr"
                  value={entrySchedPub}
                  onChange={(e) => setEntrySchedPub(e.target.value)}
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEntryOpen(false)}>انصراف</Button>
            <Button onClick={saveEntry} disabled={entrySaving}>
              {entrySaving ? "در حال ذخیره..." : editingEntry ? "به‌روزرسانی" : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Entry revisions */}
      <Dialog open={revOpen} onOpenChange={setRevOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>تاریخچه نسخه‌های ورودی</DialogTitle>
          </DialogHeader>
          <div className="max-h-72 space-y-2 overflow-y-auto py-3">
            {revLoading ? (
              <div className="flex justify-center py-4">
                <RefreshCw className="h-4 w-4 animate-spin" />
              </div>
            ) : revRows.length === 0 ? (
              <p className="py-4 text-center text-xs text-muted-foreground">نسخه‌ای ثبت نشده است</p>
            ) : (
              revRows.map((r) => (
                <div key={r.id} className="flex items-center justify-between rounded border p-2">
                  <div>
                    <p className="text-xs font-medium">
                      نسخه {toPersianDigits(String(r.revision_number))} — {r.status}
                    </p>
                    {r.created_at && (
                      <p className="text-[10px] text-muted-foreground">
                        {toPersianDigits(new Date(r.created_at).toLocaleString("fa-IR"))}
                      </p>
                    )}
                  </div>
                  <Button size="sm" variant="outline" className="h-7 text-xs" onClick={() => restoreEntryRevision(r.revision_number)}>
                    بازگردانی
                  </Button>
                </div>
              ))
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setRevOpen(false)}>بستن</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
