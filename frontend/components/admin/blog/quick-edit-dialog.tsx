"use client";

import React, { useState, useEffect } from "react";
import { Zap, Sparkles, MessageSquare, Lock, Tag, User as UserIcon, Braces, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  blogAdminApi,
  type BlogPost,
  type BlogPostCategory,
  type BlogPostStatus,
  type PostFormat,
  type PostVisibility,
  type BlogTag,
} from "@/lib/api/blog";
import { quickEditApi } from "@/lib/api/wp-parity";
import { useAdminAuthors } from "@/hooks/use-admin-authors";
import type { AdminUser } from "@/lib/api/users";

interface QuickEditDialogProps {
  post: BlogPost | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  categories: BlogPostCategory[];
  tags: BlogTag[];
  onSaved: () => void;
}

export function QuickEditDialog({
  post,
  open,
  onOpenChange,
  categories,
  tags,
  onSaved,
}: QuickEditDialogProps) {
  const { toast } = useToast();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [status, setStatus] = useState<BlogPostStatus>("draft");
  const [categoryId, setCategoryId] = useState("");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [isFeatured, setIsFeatured] = useState(false);
  const [allowComments, setAllowComments] = useState(true);
  const [visibility, setVisibility] = useState<PostVisibility>("public");
  const [format, setFormat] = useState<PostFormat>("standard");
  const [visibilityPassword, setVisibilityPassword] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [authorId, setAuthorId] = useState("");
  const [meta, setMeta] = useState<Record<string, string>>({});
  const [newMetaKey, setNewMetaKey] = useState("");
  const [metaLoadError, setMetaLoadError] = useState(false);
  const [saving, setSaving] = useState(false);

  // Author reassignment needs a name to pick from. The list is fetched only
  // while the dialog is open, and it walks every page rather than asking for
  // one oversized slice: `listUsers` caps page_size at 100, so a single call
  // silently omitted everyone past the hundred.
  const { authors } = useAdminAuthors(open);

  // Custom fields live in their own table, so the post payload does not carry
  // them. A failed read must be visible rather than silent: an empty form would
  // otherwise save as "delete every custom field" on the next submit.
  useEffect(() => {
    if (!open || !post) return;
    let cancelled = false;
    setMetaLoadError(false);
    (async () => {
      try {
        const rows = await blogAdminApi.listPostMeta(post.id);
        if (cancelled) return;
        const next: Record<string, string> = {};
        for (const row of rows) next[row.meta_key] = row.meta_value ?? "";
        setMeta(next);
      } catch {
        if (!cancelled) {
          setMeta({});
          setMetaLoadError(true);
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [open, post]);

  const authorLabel = (u: AdminUser) => {
    const name = [u.first_name, u.last_name].filter(Boolean).join(" ").trim();
    return name ? `${name} — ${u.phone}` : u.phone;
  };

  useEffect(() => {
    if (post) {
      setTitle(post.title || "");
      setSlug(post.slug || "");
      setStatus(post.status || "draft");
      setCategoryId(post.category_id || "");
      setTagIds((post.tags || []).map((t) => t.id));
      setIsFeatured(post.is_featured || false);
      setAllowComments(post.allow_comments !== false);
      setVisibility(post.visibility || "public");
      setFormat(post.post_format || "standard");
      setVisibilityPassword(post.visibility_password || "");
      setScheduledFor(
        post.scheduled_for ? new Date(post.scheduled_for).toISOString().slice(0, 16) : "",
      );
      setAuthorId(post.author_id || "");
    }
  }, [post]);

  const toggleTag = (id: string) => {
    setTagIds((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
  };

  const handleSave = async () => {
    if (!post || !title.trim()) return;
    // Refuse to save custom fields we failed to read: the endpoint replaces the
    // whole set, so submitting an empty form after a failed read would delete
    // every field the editor cannot see.
    if (metaLoadError) {
      toast({
        title: "فیلدهای سفارشی خوانده نشد",
        description: "برای جلوگیری از حذف ناخواسته، ذخیره انجام نشد. دوباره تلاش کنید.",
        variant: "destructive",
      });
      return;
    }
    setSaving(true);
    try {
      // The quick-edit route, not the full update: it writes exactly the
      // fields this form shows. The full PATCH also rewrites content and tags,
      // which this dialog never loaded, so it silently reset them on every save.
      await quickEditApi.patch(post.id, {
        title: title.trim(),
        slug: slug.trim() || undefined,
        status,
        category_id: categoryId || undefined,
        is_featured: isFeatured,
        allow_comments: allowComments,
        post_format: format,
        visibility,
        visibility_password: visibility === "password" ? visibilityPassword : undefined,
        published_at: scheduledFor ? new Date(scheduledFor).toISOString() : undefined,
        author_id: authorId || undefined,
        tag_ids: tagIds,
        // A blank value means "not set", which the service turns into a delete —
        // the same as clearing the field in the full editor.
        meta: Object.fromEntries(
          Object.entries(meta).map(([k, v]) => [k, v.trim() === "" ? null : v]),
        ),
      });

      toast({ title: "ویرایش سریع با موفقیت ذخیره شد" });
      onOpenChange(false);
      onSaved();
    } catch {
      toast({
        title: "خطا در ذخیره ویرایش سریع",
        description: "لطفاً داده‌های ورودی را بررسی نمایید.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  if (!post) return null;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <div className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-amber-500" />
            <DialogTitle>ویرایش سریع نوشته</DialogTitle>
          </div>
          <DialogDescription>
            تغییر سریع مشخصات و متاداده‌های نوشته بدون نیاز به بارگذاری ویرایشگر کامل متن
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-2">
          {/* Title & Slug */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="grid gap-2">
              <Label htmlFor="qe-title">عنوان نوشته</Label>
              <Input
                id="qe-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="عنوان..."
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="qe-slug">نامک (Slug)</Label>
              <Input
                id="qe-slug"
                value={slug}
                onChange={(e) => setSlug(e.target.value)}
                dir="ltr"
                className="text-left font-mono text-xs"
              />
            </div>
          </div>

          {/* Category, Author & Status */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div className="grid gap-2">
              <Label htmlFor="qe-category">دسته‌بندی</Label>
              <select
                id="qe-category"
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="">بدون دسته</option>
                {categories.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="qe-author" className="flex items-center gap-1">
                <UserIcon className="h-3.5 w-3.5" />
                نویسنده
              </Label>
              <select
                id="qe-author"
                value={authorId}
                onChange={(e) => setAuthorId(e.target.value)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
                disabled={authors.length === 0}
              >
                {authors.length === 0 ? (
                  <option value={authorId}>
                    {post.author_name?.trim() || "نویسنده‌ی فعلی"}
                  </option>
                ) : (
                  <>
                    <option value="">بدون تغییر</option>
                    {authors.map((u) => (
                      <option key={u.id} value={String(u.id)}>
                        {authorLabel(u)}
                      </option>
                    ))}
                  </>
                )}
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="qe-status">وضعیت</Label>
              <select
                id="qe-status"
                value={status}
                onChange={(e) => setStatus(e.target.value as BlogPostStatus)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="draft">پیش‌نویس</option>
                <option value="published">منتشر شده</option>
                <option value="archived">بایگانی</option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="qe-visibility">قابلیت مشاهده</Label>
              <select
                id="qe-visibility"
                value={visibility}
                onChange={(e) => setVisibility(e.target.value as PostVisibility)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="public">عمومی</option>
                <option value="private">خصوصی (مدیران)</option>
                <option value="password">رمزدار</option>
              </select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="qe-format">فرت پست</Label>
              <select
                id="qe-format"
                value={format}
                onChange={(e) => setFormat(e.target.value as PostFormat)}
                className="h-9 rounded-md border border-input bg-background px-3 text-xs"
              >
                <option value="standard">استاندارد</option>
                <option value="gallery">گالری تصویر</option>
                <option value="video">ویدیو</option>
                <option value="audio">صوت</option>
                <option value="quote">نقل‌قول</option>
                <option value="link">پیوند</option>
              </select>
            </div>
          </div>

          {/* Password if visibility is password */}
          {visibility === "password" && (
            <div className="grid gap-2">
              <Label htmlFor="qe-password">رمز عبور نوشته</Label>
              <Input
                id="qe-password"
                type="text"
                value={visibilityPassword}
                onChange={(e) => setVisibilityPassword(e.target.value)}
                placeholder="رمز عبور برای مشاهده محتوا..."
                dir="ltr"
              />
            </div>
          )}

          {/* Scheduled Publish */}
          <div className="grid gap-2">
            <Label htmlFor="qe-scheduled">انتشار زمان‌بندی‌شده</Label>
            <Input
              id="qe-scheduled"
              type="datetime-local"
              value={scheduledFor}
              onChange={(e) => setScheduledFor(e.target.value)}
              dir="ltr"
              className="text-left text-xs"
            />
          </div>

          {/* WordPress Toggles */}
          <div className="flex flex-wrap items-center gap-6 rounded-xl border border-border bg-muted/40 p-3 text-sm">
            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={isFeatured}
                onChange={(e) => setIsFeatured(e.target.checked)}
                className="h-4 w-4 rounded border-input text-emerald-600 focus:ring-emerald-500"
              />
              <span className="flex items-center gap-1 font-medium">
                <Sparkles className="h-4 w-4 text-amber-500" />
                نوشته ویژه / سنجاق شده
              </span>
            </label>

            <label className="flex cursor-pointer items-center gap-2">
              <input
                type="checkbox"
                checked={allowComments}
                onChange={(e) => setAllowComments(e.target.checked)}
                className="h-4 w-4 rounded border-input text-emerald-600 focus:ring-emerald-500"
              />
              <span className="flex items-center gap-1 font-medium">
                <MessageSquare className="h-4 w-4 text-emerald-600" />
                پذیرش دیدگاه‌ها
              </span>
            </label>
          </div>

          {/* Tags */}
          {tags.length > 0 && (
            <div className="grid gap-2">
              <Label className="flex items-center gap-1 text-xs">
                <Tag className="h-3.5 w-3.5" /> برچسب‌ها
              </Label>
              <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-1">
                {tags.map((t) => (
                  <button
                    type="button"
                    key={t.id}
                    onClick={() => toggleTag(t.id)}
                    className={`rounded-full border px-2.5 py-0.5 text-[11px] transition-all ${
                      tagIds.includes(t.id)
                        ? "border-emerald-600 bg-emerald-600/10 font-bold text-emerald-600"
                        : "border-border bg-muted/50 text-muted-foreground hover:border-emerald-500/40"
                    }`}
                  >
                    #{t.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        {/* Custom fields — a third of what makes quick edit worth using, and
              until now reachable only by opening the full editor. */}
          <div className="grid gap-2">
            <Label className="flex items-center gap-1">
              <Braces className="h-3.5 w-3.5" /> فیلدهای سفارشی
            </Label>
            {metaLoadError && (
              <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
                خواندن فی��دهای سفارشی ناموفق بود. ذخیره غیرفعال است تا فیلدهای نمایش‌داده‌نشده حذف نشوند.
              </p>
            )}
            {Object.keys(meta).length === 0 && !metaLoadError && (
              <p className="text-xs text-muted-foreground">فیلد سفارشی برای این نوشته ثبت نشده است.</p>
            )}
            {Object.entries(meta).map(([key, value]) => (
              <div key={key} className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_2fr_auto]">
                <Input
                  value={key}
                  readOnly
                  dir="ltr"
                  aria-label="کلید فیلد"
                  className="text-left font-mono text-xs text-muted-foreground"
                />
                <Input
                  value={value}
                  onChange={(e) => setMeta((prev) => ({ ...prev, [key]: e.target.value }))}
                  placeholder="مقدار (خالی = حذف فیلد)"
                  className="text-xs"
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={() =>
                    setMeta((prev) => {
                      const next = { ...prev };
                      delete next[key];
                      return next;
                    })
                  }
                  aria-label={`حذف فیلد ${key}`}
                >
                  <Trash2 className="h-3.5 w-3.5 text-destructive" />
                </Button>
              </div>
            ))}
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-[minmax(0,1fr)_2fr_auto]">
              <Input
                value={newMetaKey}
                onChange={(e) => setNewMetaKey(e.target.value)}
                placeholder="کلید فیلد جدید"
                dir="ltr"
                className="text-left font-mono text-xs"
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!newMetaKey.trim()}
                onClick={() => {
                  const key = newMetaKey.trim();
                  if (!key) return;
                  setMeta((prev) => (key in prev ? prev : { ...prev, [key]: "" }));
                  setNewMetaKey("");
                }}
              >
                افزودن فیلد
              </Button>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            انصراف
          </Button>
          <Button onClick={handleSave} disabled={saving || !title.trim()}>
            {saving ? "در حال به‌روزرسانی..." : "به‌روزرسانی"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
