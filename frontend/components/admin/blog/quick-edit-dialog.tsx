"use client";

import React, { useState, useEffect } from "react";
import { Zap, Sparkles, MessageSquare, Lock, Tag } from "lucide-react";
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
  type PostVisibility,
  type BlogTag,
} from "@/lib/api/blog";

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
  const [visibilityPassword, setVisibilityPassword] = useState("");
  const [scheduledFor, setScheduledFor] = useState("");
  const [saving, setSaving] = useState(false);

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
      setVisibilityPassword(post.visibility_password || "");
      setScheduledFor(
        post.scheduled_for ? new Date(post.scheduled_for).toISOString().slice(0, 16) : "",
      );
    }
  }, [post]);

  const toggleTag = (id: string) => {
    setTagIds((prev) => (prev.includes(id) ? prev.filter((t) => t !== id) : [...prev, id]));
  };

  const handleSave = async () => {
    if (!post || !title.trim()) return;
    setSaving(true);
    try {
      await blogAdminApi.updatePost(post.id, {
        title: title.trim(),
        slug: slug.trim() || undefined,
        status,
        category_id: categoryId || undefined,
        tag_ids: tagIds,
        is_featured: isFeatured,
        allow_comments: allowComments,
        visibility,
        visibility_password: visibility === "password" ? visibilityPassword : undefined,
        scheduled_for: scheduledFor ? new Date(scheduledFor).toISOString() : undefined,
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

          {/* Category & Status */}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
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
