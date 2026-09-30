"use client";

/**
 * Reusable blocks (WordPress "synced patterns").
 *
 * Blocks are embedded by token — `[block slug="…"]` — and expanded on read
 * by the backend, so editing a block here updates every page and post that
 * uses it. The token is shown with a copy button because pasting it into a
 * body is the whole workflow: there is nothing to insert through the editor.
 */

import React, { useCallback, useEffect, useState } from "react";
import { Copy, Pencil, Plus, RefreshCw, RotateCcw, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
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
  reusableBlocksApi,
  reusableBlockToken,
  type ReusableBlock,
  type ReusableBlockStatus,
} from "@/lib/api/cms-admin";
import { toPersianDigits } from "@/lib/utils";

const STATUS_LABELS: Record<ReusableBlockStatus, string> = {
  draft: "پیش‌نویس",
  published: "منتشرشده",
  archived: "بایگانی",
};

export default function ReusableBlocksCard() {
  const { toast } = useToast();
  const [blocks, setBlocks] = useState<ReusableBlock[]>([]);
  const [loading, setLoading] = useState(true);
  const [showTrash, setShowTrash] = useState(false);

  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<ReusableBlock | null>(null);
  const [name, setName] = useState("");
  const [bodyHtml, setBodyHtml] = useState("");
  const [status, setStatus] = useState<ReusableBlockStatus>("draft");
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setBlocks(await reusableBlocksApi.list({ includeDeleted: showTrash }));
    } catch {
      toast({ title: "خطا", description: "بارگذاری بلوک‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [showTrash, toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const openCreate = () => {
    setEditing(null);
    setName("");
    setBodyHtml("");
    setStatus("draft");
    setDialogOpen(true);
  };

  const openEdit = (block: ReusableBlock) => {
    setEditing(block);
    setName(block.name);
    setBodyHtml(block.body_html);
    setStatus(block.status);
    setDialogOpen(true);
  };

  const save = async () => {
    if (!name.trim()) return;
    setSaving(true);
    try {
      if (editing) {
        await reusableBlocksApi.update(editing.id, {
          name,
          body_html: bodyHtml,
          status,
        });
      } else {
        await reusableBlocksApi.create({ name, body_html: bodyHtml, status });
      }
      setDialogOpen(false);
      toast({ title: "ذخیره شد" });
      await load();
    } catch {
      toast({ title: "خطا", description: "ذخیره بلوک ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const copyToken = async (block: ReusableBlock) => {
    const token = reusableBlockToken(block.slug);
    try {
      await navigator.clipboard.writeText(token);
      toast({ title: "کپی شد", description: token });
    } catch {
      // Clipboard needs a secure context; showing the token still lets the
      // editor select it by hand rather than silently doing nothing.
      toast({ title: "کپی نشد", description: token, variant: "destructive" });
    }
  };

  const remove = async (block: ReusableBlock) => {
    if (!confirm(`بلوک «${block.name}» به سطل زباله منتقل شود؟`)) return;
    try {
      await reusableBlocksApi.remove(block.id);
      await load();
    } catch {
      toast({ title: "خطا", description: "حذف بلوک ناموفق بود", variant: "destructive" });
    }
  };

  const restore = async (block: ReusableBlock) => {
    try {
      await reusableBlocksApi.restore(block.id);
      await load();
    } catch {
      toast({ title: "خطا", description: "بازگردانی ناموفق بود", variant: "destructive" });
    }
  };

  return (
    <Card className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">بلوک‌های قابل استفاده مجدد</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            یک‌بار بنویسید، در چند صفحه استفاده کنید؛ ویرایش اینجا همه‌جا اعمال می‌شود
          </p>
        </div>
        <div className="flex gap-2">
          <Button size="sm" variant="ghost" onClick={() => setShowTrash((v) => !v)}>
            {showTrash ? "نمایش فعال‌ها" : "سطل زباله"}
          </Button>
          <Button size="sm" variant="outline" onClick={() => void load()}>
            <RefreshCw className="h-4 w-4 ms-1" />
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="h-4 w-4 ms-1" />
            بلوک جدید
          </Button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-8">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : blocks.length === 0 ? (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {showTrash ? "سطل زباله خالی است" : "هنوز بلوکی ساخته نشده است"}
        </p>
      ) : (
        <div className="space-y-2">
          {blocks.map((block) => (
            <div
              key={block.id}
              className={`rounded-lg border p-3 ${block.deleted_at || !block.is_active ? "opacity-50" : ""}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm font-medium">{block.name}</p>
                  <button
                    type="button"
                    onClick={() => void copyToken(block)}
                    dir="ltr"
                    className="mt-1 inline-flex items-center gap-1 rounded bg-muted px-1.5 py-0.5 font-mono text-[10px] hover:bg-accent"
                    title="کپی توکن درج"
                  >
                    <Copy className="h-3 w-3" />
                    {reusableBlockToken(block.slug)}
                  </button>
                  <div className="mt-1 flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {STATUS_LABELS[block.status]}
                    </Badge>
                    {!block.is_active && (
                      <Badge variant="secondary" className="text-xs">غیرفعال</Badge>
                    )}
                  </div>
                </div>
                <div className="flex shrink-0 gap-1">
                  {block.deleted_at ? (
                    <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => void restore(block)}>
                      <RotateCcw className="h-3.5 w-3.5" />
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => openEdit(block)}>
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-destructive"
                        onClick={() => void remove(block)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editing ? "ویرایش بلوک" : "بلوک جدید"}</DialogTitle>
            <DialogDescription>
              این محتوا در هر صفحه‌ای که توکن آن درج شده باشد نمایش داده می‌شود
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <div>
              <Label>نام</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="مثلاً بنر تبلیغاتی" />
            </div>
            <div>
              <Label>وضعیت</Label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value as ReusableBlockStatus)}
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {(Object.keys(STATUS_LABELS) as ReusableBlockStatus[]).map((s) => (
                  <option key={s} value={s}>
                    {STATUS_LABELS[s]}
                  </option>
                ))}
              </select>
              <p className="mt-1 text-[10px] text-muted-foreground">
                فقط بلوک‌های «منتشرشده» در سایت نمایش داده می‌شوند
              </p>
            </div>
            <div>
              <Label>محتوا</Label>
              <RichBodyEditor value={bodyHtml} onChange={setBodyHtml} />
            </div>
            {editing && (
              <p className="text-xs text-muted-foreground" dir="ltr">
                {reusableBlockToken(editing.slug)}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void save()} disabled={saving || !name.trim()}>
              {saving ? "در حال ذخیره…" : "ذخیره"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {blocks.length > 0 && (
        <p className="mt-3 text-[10px] text-muted-foreground">
          {toPersianDigits(String(blocks.length))} بلوک
        </p>
      )}
    </Card>
  );
}
