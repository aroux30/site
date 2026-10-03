"use client";

/** Quick edit for a CMS page, mirroring the post dialog.
 *
 *  WordPress's quick edit is how a moderator fixes a title or flips a page to
 *  draft without leaving the list, and posts here have had it for a while.
 *  Without a page equivalent, correcting a page's slug meant opening the full
 *  editor — which loads the body, the SEO fields and the media picker, for a
 *  two-second change.
 *
 *  Deliberately only the fields a page actually has. The post dialog also
 *  edits author, category, tags and post format, none of which a page has;
 *  showing them greyed out would be noise, and inventing a mapping would be
 *  worse.
 */

import { useCallback, useEffect, useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
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
import { Switch } from "@/components/ui/switch";
import { useToast } from "@/components/ui/use-toast";
import { cmsPagesAdminApi } from "@/lib/api/content";
import type {
  CmsPage,
  CmsPageStatus,
  CmsPageVisibility,
} from "@/lib/api/content";

interface QuickEditPageDialogProps {
  page: CmsPage | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}

const STATUSES: Array<{ value: CmsPageStatus; label: string }> = [
  { value: "draft", label: "پیش‌نویس" },
  { value: "pending_review", label: "در انتظار بررسی" },
  { value: "published", label: "منتشرشده" },
  { value: "archived", label: "بایگانی" },
];

const VISIBILITIES: Array<{ value: CmsPageVisibility; label: string }> = [
  { value: "public", label: "عمومی" },
  { value: "private", label: "خصوصی" },
  { value: "password", label: "رمزدار" },
];

export function QuickEditPageDialog({
  page,
  open,
  onOpenChange,
  onSaved,
}: QuickEditPageDialogProps) {
  const { toast } = useToast();
  const [title, setTitle] = useState("");
  const [slug, setSlug] = useState("");
  const [status, setStatus] = useState<CmsPageStatus>("draft");
  const [visibility, setVisibility] = useState<CmsPageVisibility>("public");
  const [password, setPassword] = useState("");
  const [allowComments, setAllowComments] = useState(false);
  const [scheduledFor, setScheduledFor] = useState("");
  const [saving, setSaving] = useState(false);

  /* Reload from the row every time the dialog opens.
   *
   * Reading the fields into state once and leaving them there is how a quick
   * edit ends up saving somebody else's change: two people open the same page,
   * the second one sees what the first typed, and saving writes it back. The
   * row it opens with is the one that was just fetched.
   */
  useEffect(() => {
    if (!page) return;
    setTitle(page.title ?? "");
    setSlug(page.slug ?? "");
    setStatus((page.status as CmsPageStatus) ?? "draft");
    setVisibility(page.visibility ?? "public");
    // The hash never comes back, so the field starts empty and is only sent
    // when typed — sending "" would clear a password that is already set.
    setPassword("");
    setAllowComments(page.allow_comments ?? false);
    setScheduledFor(page.scheduled_publish_at ? page.scheduled_publish_at.slice(0, 16) : "");
  }, [page]);

  const save = useCallback(async () => {
    if (!page) return;
    if (!title.trim()) {
      toast({ title: "عنوان صفحه الزامی است", variant: "destructive" });
      return;
    }
    setSaving(true);
    try {
      await cmsPagesAdminApi.updatePage(page.id, {
        title: title.trim(),
        slug: slug.trim() || undefined,
        status,
        visibility,
        allow_comments: allowComments,
        scheduled_publish_at: scheduledFor
          ? new Date(scheduledFor).toISOString()
          : null,
        ...(password.trim() ? { visibility_password: password.trim() } : {}),
      });
      toast({ title: "صفحه به‌روزرسانی شد" });
      onOpenChange(false);
      onSaved();
    } catch {
      toast({
        title: "ذخیرهٔ سریع ناموفق بود",
        description: "نامک ممکن است تکراری یا رزرو شده باشد.",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  }, [
    page, title, slug, status, visibility, password, allowComments,
    scheduledFor, onOpenChange, onSaved, toast,
  ]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-xl" dir="rtl">
        <DialogHeader>
          <DialogTitle>ویرایش سریع صفحه</DialogTitle>
          <DialogDescription>
            عنوان، نامک، وضعیت و حریم خصوصی — بدون باز کردن ویرایشگر کامل.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="qe-page-title">عنوان</Label>
            <Input id="qe-page-title" value={title} dir="rtl"
              onChange={(e) => setTitle(e.target.value)} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="qe-page-slug">نامک</Label>
            <Input id="qe-page-slug" value={slug} dir="ltr"
              onChange={(e) => setSlug(e.target.value)}
              className="text-left font-mono" />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>وضعیت</Label>
              <Select value={status} onValueChange={(v) => setStatus(v as CmsPageStatus)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {STATUSES.map((s) => (
                    <SelectItem key={s.value} value={s.value}>{s.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>حریم خصوصی</Label>
              <Select
                value={visibility}
                onValueChange={(v) => setVisibility(v as CmsPageVisibility)}
              >
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {VISIBILITIES.map((v) => (
                    <SelectItem key={v.value} value={v.value}>{v.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Only rendered when it means something. A password field shown for a
              public page invites somebody to type one into a page that is not
              password-protected, which then does nothing and looks broken. */}
          {visibility === "password" && (
            <div className="space-y-1.5">
              <Label htmlFor="qe-page-password">رمز عبور</Label>
              <Input id="qe-page-password" type="password" dir="ltr"
                value={password} onChange={(e) => setPassword(e.target.value)}
                className="text-left"
                placeholder={page?.visibility_password_set ? "رمز تنظیم شده — برای تغییر بنویسید" : "رمز عبور"} />
            </div>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="qe-page-scheduled">زمان‌بندی انتشار</Label>
            <Input id="qe-page-scheduled" type="datetime-local"
              value={scheduledFor} dir="ltr"
              onChange={(e) => setScheduledFor(e.target.value)}
              className="text-left" />
          </div>

          <div className="flex items-center gap-2">
            <Switch id="qe-page-comments" checked={allowComments}
              onCheckedChange={setAllowComments} />
            <Label htmlFor="qe-page-comments" className="text-sm">
              دیدگاه‌ها باز باشد
            </Label>
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            انصراف
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? "در حال ذخیره..." : "ذخیره"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
