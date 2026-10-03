"use client";

/**
 * BulkEditDialog — change a field across many posts at once.
 *
 * The list had bulk *actions* (publish, draft, archive, trash) and nothing else,
 * so moving 20 posts into a new category meant opening 20 editors. WordPress
 * separates the two ideas and so does this: the actions change state, this
 * changes fields.
 *
 * Every control starts empty and empty means "leave alone" — nothing is sent
 * unless the operator fills it in. That is the whole design: a bulk form that
 * always submitted every field would silently reset the category, the tags and
 * the author of every selected post the moment you changed the comments flag.
 */
import { useEffect, useMemo, useState } from "react";
import { Loader2, PencilLine } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import {
  blogAdminApi,
  type BlogPost,
  type BlogPostCategory,
  type BlogPostStatus,
  type BlogTag,
  type PostFormat,
  type PostVisibility,
} from "@/lib/api/blog";
import { useAdminAuthors } from "@/hooks/use-admin-authors";
import { toPersianDigits } from "@/lib/utils";

interface BulkEditDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  posts: BlogPost[];
  categories: BlogPostCategory[];
  tags: BlogTag[];
  onDone: () => void;
}

/** Which fields the operator filled in. Absent = untouched. */
interface BulkEdits {
  category_id?: string;
  author_id?: string;
  post_format?: PostFormat;
  allow_comments?: boolean;
  is_featured?: boolean;
  visibility?: PostVisibility;
  status?: BlogPostStatus;
  tag_ids?: string[];
}

const POST_FORMATS: { value: PostFormat; label: string }[] = [
  { value: "standard", label: "استاندارد" },
  { value: "gallery", label: "گالری تصویر" },
  { value: "video", label: "ویدیو" },
  { value: "audio", label: "صوت" },
  { value: "quote", label: "نقل‌قول" },
  { value: "link", label: "پیوند" },
];

export function BulkEditDialog({
  open,
  onOpenChange,
  posts,
  categories,
  tags,
  onDone,
}: BulkEditDialogProps) {
  const { toast } = useToast();
  const { authors } = useAdminAuthors(open);

  // "" means "no change" for the string fields; the booleans are tri-state
  // because a checkbox has no empty position.
  const [categoryId, setCategoryId] = useState("");
  const [authorId, setAuthorId] = useState("");
  const [format, setFormat] = useState<PostFormat | "">("");
  const [visibility, setVisibility] = useState<PostVisibility | "">("");
  const [status, setStatus] = useState<BlogPostStatus | "">("");
  const [comments, setComments] = useState<"keep" | "open" | "closed">("keep");
  const [featured, setFeatured] = useState<"keep" | "yes" | "no">("keep");
  const [tagIds, setTagIds] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!open) return;
    setCategoryId("");
    setAuthorId("");
    setFormat("");
    setVisibility("");
    setStatus("");
    setComments("keep");
    setFeatured("keep");
    setTagIds([]);
  }, [open]);

  const edits = useMemo<{ payload: BulkEdits; count: number }>(() => {
    const payload: BulkEdits = {};
    let n = 0;
    if (categoryId) {
      payload.category_id = categoryId;
      n += 1;
    }
    if (authorId) {
      payload.author_id = authorId;
      n += 1;
    }
    if (format) {
      payload.post_format = format;
      n += 1;
    }
    if (visibility) {
      payload.visibility = visibility;
      n += 1;
    }
    if (status) {
      payload.status = status;
      n += 1;
    }
    if (comments !== "keep") {
      payload.allow_comments = comments === "open";
      n += 1;
    }
    if (featured !== "keep") {
      payload.is_featured = featured === "yes";
      n += 1;
    }
    if (tagIds.length > 0) {
      payload.tag_ids = tagIds;
      n += 1;
    }
    return { payload, count: n };
  }, [categoryId, authorId, format, visibility, status, comments, featured, tagIds]);

  const run = async () => {
    if (edits.count === 0) {
      toast({ title: "هیچ فیلدی انتخاب نشده است", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      const res = await blogAdminApi.bulkPosts(
        posts.map((p) => p.id),
        "edit",
        edits.payload,
      );
      if (res.failed > 0) {
        toast({
          title: `${toPersianDigits(String(res.ok))} مورد انجام شد، ${toPersianDigits(String(res.failed))} مورد ناموفق`,
          description: "برخی نوشته‌ها مال شما نیستند یا در وضعیت مناسبی نبودند.",
          variant: "destructive",
        });
      } else {
        toast({
          title: `${toPersianDigits(String(res.ok))} نوشته ویرایش شد`,
          description: "برای هر نوشته یک نسخه در تاریخچه ثبت شد.",
        });
      }
      onOpenChange(false);
      onDone();
    } catch {
      toast({
        title: "ویرایش گروهی ناموفق بود",
        description: "هیچ نوشته‌ای تغییر نکرد.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  const select = (
    id: string,
    value: string,
    onChange: (v: string) => void,
    children: React.ReactNode,
    label: string,
  ) => (
    <div className="grid gap-2">
      <label htmlFor={id} className="text-xs font-medium text-muted-foreground">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="h-9 rounded-md border border-input bg-background px-3 text-xs"
      >
        {children}
      </select>
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-2xl overflow-y-auto" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <PencilLine className="h-4 w-4" />
            ویرایش گروهی — {toPersianDigits(String(posts.length))} نوشته
          </DialogTitle>
          <DialogDescription>
            فقط فیلدهایی که مقدار بگیرند تغییر می‌کنند؛ بقیه دست‌نخورده می‌مانند.
          </DialogDescription>
        </DialogHeader>

        <div className="grid grid-cols-1 gap-4 py-2 sm:grid-cols-2">
          {select(
            "bulk-category",
            categoryId,
            setCategoryId,
            <>
              <option value="">بدون تغییر</option>
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </>,
            "دسته‌بندی",
          )}

          {select(
            "bulk-author",
            authorId,
            setAuthorId,
            <>
              <option value="">بدون تغییر</option>
              {authors.map((u) => (
                <option key={u.id} value={String(u.id)}>
                  {[u.first_name, u.last_name].filter(Boolean).join(" ").trim() || u.phone}
                </option>
              ))}
            </>,
            "نویسنده",
          )}

          {select(
            "bulk-format",
            format,
            (v) => setFormat(v as PostFormat | ""),
            <>
              <option value="">بدون تغییر</option>
              {POST_FORMATS.map((f) => (
                <option key={f.value} value={f.value}>
                  {f.label}
                </option>
              ))}
            </>,
            "فرت پست",
          )}

          {select(
            "bulk-visibility",
            visibility,
            (v) => setVisibility(v as PostVisibility | ""),
            <>
              <option value="">بدون تغییر</option>
              <option value="public">عمومی</option>
              <option value="private">خصوصی (مدیران)</option>
              <option value="password">رمزدار</option>
            </>,
            "قابلیت مشاهده",
          )}

          {select(
            "bulk-status",
            status,
            (v) => setStatus(v as BlogPostStatus | ""),
            <>
              <option value="">بدون تغییر</option>
              <option value="draft">پیش‌نویس</option>
              <option value="pending_review">در انتظار بازبینی</option>
              <option value="published">منتشر شده</option>
              <option value="archived">بایگانی</option>
            </>,
            "وضعیت",
          )}

          {select(
            "bulk-comments",
            comments,
            (v) => setComments(v as "keep" | "open" | "closed"),
            <>
              <option value="keep">بدون تغییر</option>
              <option value="open">باز</option>
              <option value="closed">بسته</option>
            </>,
            "دیدگاه‌ها",
          )}

          {select(
            "bulk-featured",
            featured,
            (v) => setFeatured(v as "keep" | "yes" | "no"),
            <>
              <option value="keep">بدون تغییر</option>
              <option value="yes">ویژه</option>
              <option value="no">عادی</option>
            </>,
            "نوشته‌ی ویژه",
          )}

          <div className="grid gap-2">
            <span className="text-xs font-medium text-muted-foreground">برچسب‌ها</span>
            <div className="flex max-h-32 flex-wrap gap-1 overflow-y-auto rounded-md border border-input p-2">
              {tags.length === 0 ? (
                <span className="text-xs text-muted-foreground">برچسبی وجود ندارد</span>
              ) : (
                tags.map((t) => {
                  const on = tagIds.includes(t.id);
                  return (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() =>
                        setTagIds((prev) =>
                          on ? prev.filter((x) => x !== t.id) : [...prev, t.id],
                        )
                      }
                      className={
                        "rounded-full border px-2 py-0.5 text-[11px] transition " +
                        (on
                          ? "border-primary bg-primary/10 text-primary"
                          : "border-border text-muted-foreground hover:border-primary/40")
                      }
                    >
                      {t.name}
                    </button>
                  );
                })
              )}
            </div>
            <span className="text-[11px] text-muted-foreground">
              {tagIds.length === 0
                ? "بدون انتخاب = برچسب‌های دست‌نخورده می‌مانند"
                : `برچسب‌های انتخابی جایگزین ${toPersianDigits(String(tagIds.length))} برچسب قبلی می‌شوند`}
            </span>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={saving}>
            انصراف
          </Button>
          <Button onClick={() => void run()} disabled={saving || edits.count === 0}>
            {saving ? (
              <>
                <Loader2 className="h-4 w-4 ms-1 animate-spin" />
                در حال اعمال...
              </>
            ) : (
              `اعمال روی ${toPersianDigits(String(posts.length))} نوشته`
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}