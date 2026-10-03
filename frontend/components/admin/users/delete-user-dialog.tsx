"use client";

/**
 * Delete a user, and decide who inherits what they wrote.
 *
 * P0 "کاربران: حذف کاربر با واگذاری محتوا". Two gaps met here.
 *
 * The obvious one: seven columns point at `users` with `ON DELETE SET NULL`, so a
 * delete with no heir leaves every post, page, comment and reusable block that
 * person wrote attributed to nobody.
 *
 * The one the audit did not name: `deleteUser` had **no caller at all**. The
 * client method existed, the route existed, and there was no button anywhere in
 * the admin — an operator could create an account and could not remove one. That
 * is worse than the attribution gap, because it is not a partial feature: it is
 * the absence of the feature, sitting behind a working client.
 *
 * The heir list is loaded before the dialog opens, not on click. An operator who
 * opens a dialog and then waits for a list to arrive cannot tell an empty store
 * from a slow one, and the choice they are being asked for — "who takes this
 * person's work" — needs the names in front of them to be a real decision.
 *
 * Content is *offered*, not required. Someone who never wrote a post has nothing
 * to hand over, and making the dialog insist on picking an heir for an empty
 * estate teaches operators that the field is noise.
 */

import { useCallback, useEffect, useState } from "react";
import { AlertTriangle, Loader2, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { usersAdminApi, type AdminUser } from "@/lib/api/users";

interface DeleteUserDialogProps {
  user: AdminUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful delete so the list can refetch. */
  onDeleted: () => void | Promise<void>;
}

interface OwnedCounts {
  owned: Record<string, number>;
  total: number;
  summary: string;
}

export function DeleteUserDialog({
  user,
  open,
  onOpenChange,
  onDeleted,
}: DeleteUserDialogProps) {
  const [owned, setOwned] = useState<OwnedCounts | null>(null);
  const [candidates, setCandidates] = useState<AdminUser[]>([]);
  const [heir, setHeir] = useState("");
  const [busy, setBusy] = useState(false);
  const { toast } = useToast();

  const load = useCallback(async () => {
    if (!user) return;
    setOwned(null);
    setHeir("");
    const id = String(user.id);
    try {
      const [preview, list] = await Promise.all([
        usersAdminApi.previewReassignment(id),
        usersAdminApi.listUsers({ page: 1, page_size: 100 }),
      ]);
      setOwned(preview);
      setCandidates(list.items.filter((u) => String(u.id) !== id));
    } catch {
      // Said rather than shown as "this user owns nothing": those are different
      // answers, and only one of them justifies deleting without a second look.
      toast({
        title: "خواندن محتوای کاربر ناموفق بود",
        description: "پیش از حذف، فهرست محتوای این حساب خوانده نشد.",
        variant: "destructive",
      });
    }
  }, [user, toast]);

  useEffect(() => {
    if (open) void load();
  }, [open, load]);

  if (!user) return null;

  const confirm = async () => {
    setBusy(true);
    try {
      const res = await usersAdminApi.deleteUser(
        String(user.id),
        heir ? { reassign_to: heir } : undefined,
      );
      toast({
        title: "حساب کاربر حذف شد",
        description: res.summary,
      });
      onOpenChange(false);
      await onDeleted();
    } catch (e) {
      const detail =
        e && typeof e === "object" && "response" in e
          ? String(
              (e as { response?: { data?: { detail?: string } } }).response?.data
                ?.detail ?? "",
            )
          : "";
      toast({
        title: "حذف کاربر ناموفق بود",
        description: detail || "حذف این حساب انجام نشد.",
        variant: "destructive",
      });
    } finally {
      setBusy(false);
    }
  };

  const hasContent = (owned?.total ?? 0) > 0;

  return (
    <Dialog open={open} onOpenChange={(o) => !busy && onOpenChange(o)}>
      <DialogContent className="max-w-md" dir="rtl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <AlertTriangle className="h-4 w-4 text-destructive" />
            حذف کاربر {user.first_name || user.phone}
          </DialogTitle>
          <DialogDescription>
            حساب غیرفعال می‌شود و همهٔ نشست‌های او باطل می‌گردد. این کار
            برگشت‌پذیر است و می‌توان حساب را بازگرداند.
          </DialogDescription>
        </DialogHeader>

        {/* What they own, before asking what to do about it. The count decides
            whether the choice below is even relevant, so it comes first. */}
        <div className="rounded-md border border-border/60 px-3 py-2 text-xs">
          <div className="font-medium text-muted-foreground">محتوای ثبت‌شده</div>
          {!owned ? (
            <div className="mt-1 flex items-center gap-1.5 text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
              در حال بررسی...
            </div>
          ) : hasContent ? (
            <div className="mt-1 space-y-0.5">
              {Object.entries(owned.owned).map(([k, v]) => (
                <div key={k} className="flex justify-between gap-2">
                  <span className="font-mono text-[11px]">{k}</span>
                  <span>{owned.total > 0 ? v : 0}</span>
                </div>
              ))}
              <p className="pt-1 text-[11px] text-muted-foreground">
                مجموع: {owned.total} ردیف. اگر جانشینی انتخاب نشود، این محتوا
                بی‌نام می‌ماند.
              </p>
            </div>
          ) : (
            <p className="mt-1 text-muted-foreground">
              این کاربر محتوایی ثبت نکرده است؛ انتخاب جانشین لازم نیست.
            </p>
          )}
        </div>

        {hasContent && (
          <div className="space-y-1.5">
            <Label htmlFor="du-heir">واگذاری محتوا به</Label>
            <select
              id="du-heir"
              value={heir}
              disabled={busy}
              onChange={(e) => setHeir(e.target.value)}
              className="w-full rounded-md border border-input bg-background px-2.5 py-2 text-xs"
            >
              <option value="">— بدون واگذاری؛ محتوا بی‌نام می‌ماند —</option>
              {candidates.map((c) => (
                <option key={String(c.id)} value={String(c.id)}>
                  {c.first_name || ""} {c.last_name || ""} ({c.phone})
                </option>
              ))}
            </select>
            <p className="text-[11px] text-muted-foreground">
              تاریخچهٔ بازنگری و سابقهٔ رویدادها واگذار نمی‌شود — آن‌ها رکوردِ
              «چه کسی چه کرد» هستند و جابه‌جایی‌شان تاریخ را جعل می‌کند.
            </p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            انصراف
          </Button>
          <Button variant="destructive" onClick={() => void confirm()} disabled={busy}>
            {busy ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Trash2 className="h-4 w-4" />
            )}
            حذف کاربر
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}