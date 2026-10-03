"use client";

import { useEffect, useState } from "react";

import { usersAdminApi, type AdminUser } from "@/lib/api/users";
import { UserRolesEditor } from "./user-roles-editor";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface Props {
  /** null = create mode, a user = edit mode. */
  user: AdminUser | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called after a successful save so the list can refetch. */
  onSaved: () => void | Promise<void>;
}

interface FormState {
  phone: string;
  email: string;
  first_name: string;
  last_name: string;
  password: string;
  /** Create-mode only. The server assigns this role with the account, so an
   *  operator onboarding a staff member does not have to create them as a
   *  customer and then find the separate roles editor to fix it. */
  role_slug: string;
}

const EMPTY: FormState = {
  phone: "",
  email: "",
  first_name: "",
  last_name: "",
  password: "",
  role_slug: "customer",
};

/** The roles an operator can hand out at creation. Deliberately short: the
 *  full RBAC catalogue is large, and the common onboarding choices are these.
 *  Any other role is still assignable after creation through the roles editor. */
const CREATABLE_ROLES = [
  { value: "customer", label: "مشتری" },
  { value: "vendor", label: "فروشنده" },
  { value: "author", label: "نویسنده" },
  { value: "editor", label: "ویرایشگر" },
  { value: "admin", label: "مدیر" },
] as const;

/**
 * Create or edit one account.
 *
 * Both endpoints existed on the server and had a typed client, but the admin
 * users page was a read-only list with block/unblock and a GDPR download — so
 * an operator could not onboard a staff account at all, and could only reach
 * `POST /users/admin/users` or `PATCH /users/admin/users/{id}` by hand. The
 * role-management page assigns roles to accounts that could only be created out
 * of band.
 */
export function UserDialog({ user, open, onOpenChange, onSaved }: Props) {
  const editing = user !== null;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Re-seed whenever the dialog opens, so a cancelled edit does not leak into
  // the next one and edit-mode shows the target's real values.
  useEffect(() => {
    if (!open) return;
    setError(null);
    setForm(
      editing
        ? {
            phone: user.phone ?? "",
            email: user.email ?? "",
            first_name: user.first_name ?? "",
            last_name: user.last_name ?? "",
            password: "",
            role_slug: "",
          }
        : EMPTY,
    );
  }, [open, user, editing]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function save(): Promise<void> {
    // The phone is this platform's unique login identifier, so an empty one
    // would create an account nobody can sign in to. The server requires it
    // too; checking here saves the round-trip and gives a better message.
    if (!form.phone.trim()) {
      setError("شماره موبایل الزامی است.");
      return;
    }
    // Create requires a password; edit leaves it alone when blank, so an
    // operator editing a name does not silently reset someone's password.
    if (!editing && !form.password) {
      setError("برای حساب جدید رمز عبور لازم است.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      if (editing && user) {
        const payload: Partial<AdminUser> = {
          email: form.email.trim() || undefined,
          first_name: form.first_name.trim() || undefined,
          last_name: form.last_name.trim() || undefined,
        };
        await usersAdminApi.updateUser(user.id, payload);
      } else {
        await usersAdminApi.createUser({
          phone: form.phone.trim(),
          email: form.email.trim() || undefined,
          first_name: form.first_name.trim() || undefined,
          last_name: form.last_name.trim() || undefined,
          password: form.password,
          // Only sent when it is not the default: "customer" is the server's
          // own default, and sending it would need rbac:write for no change.
          role_slugs:
            form.role_slug && form.role_slug !== "customer"
              ? [form.role_slug]
              : undefined,
        });
      }
      await onSaved();
      onOpenChange(false);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "ذخیرهٔ کاربر ناموفق بود. لطفاً دوباره تلاش کنید.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>{editing ? "ویرایش کاربر" : "کاربر جدید"}</DialogTitle>
          <DialogDescription>
            {editing
              ? "تغییر ایمیل روی درخواست تأیید اثر می‌گذارد و لینک تأیید به آدرس جدید می‌رود."
              : "پس از ساخت، ایمیل اطلاع‌رسانی برای صاحب حساب ارسال می‌شود."}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="ud-phone">شماره موبایل</Label>
            <Input
              id="ud-phone"
              dir="ltr"
              value={form.phone}
              // The phone is the login identifier and the backend does not
              // support renaming it; editing it would silently target a
              // different account than the one being opened.
              disabled={editing || busy}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="09120000000"
            />
            {editing && (
              <p className="text-[11px] text-muted-foreground">
                شماره موبایل قابل تغییر نیست؛ شناسهٔ ورود حساب است.
              </p>
            )}
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ud-email">ایمیل</Label>
            <Input
              id="ud-email"
              dir="ltr"
              type="email"
              value={form.email}
              disabled={busy}
              onChange={(e) => set("email", e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <Label htmlFor="ud-first">نام</Label>
              <Input
                id="ud-first"
                value={form.first_name}
                disabled={busy}
                onChange={(e) => set("first_name", e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ud-last">نام خانوادگی</Label>
              <Input
                id="ud-last"
                value={form.last_name}
                disabled={busy}
                onChange={(e) => set("last_name", e.target.value)}
              />
            </div>
          </div>

          {!editing && (
            <div className="space-y-1.5">
              <Label htmlFor="ud-password">رمز عبور</Label>
              <Input
                id="ud-password"
                dir="ltr"
                type="password"
                value={form.password}
                disabled={busy}
                onChange={(e) => set("password", e.target.value)}
                autoComplete="new-password"
              />
              <p className="text-[11px] text-muted-foreground">
                حداقل ۸ نویسه، شامل یک حرف و یک رقم.
              </p>
            </div>
          )}

          {/* Role at creation. Before this, every admin-created account was a
              customer and the operator had to find the separate roles editor
              afterward to make a staff member staff — so onboarding was two
              steps with a wrong state in between. Changing the role needs
              rbac:write, which the server checks; a customer-only create does
              not and never sends this. */}
          {!editing && (
            <div className="space-y-1.5">
              <Label htmlFor="ud-role">نقش</Label>
              <select
                id="ud-role"
                value={form.role_slug}
                disabled={busy}
                onChange={(e) => set("role_slug", e.target.value)}
                className="h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              >
                {CREATABLE_ROLES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Roles are assigned here, on their own, not as a field on the
              account form. The endpoint and the typed client both existed with no
              caller, so an operator could override one permission on a user but
              could not give them a role at all — and a role is what an operator
              reaches for when hiring. It is a separate column of the user, not a
              property of the account row, and folding it into this form would
              make saving the account and saving its roles one operation that
              fails in both directions at once. */}
          {editing && user && (
            <div className="border-t border-border/60 pt-3">
              <UserRolesEditor userId={user.id} />
            </div>
          )}

          {error && (
            <p className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-xs text-destructive">
              {error}
            </p>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            انصراف
          </Button>
          <Button onClick={() => void save()} disabled={busy}>
            {busy
              ? "در حال ذخیره..."
              : editing
                ? "ذخیرهٔ تغییرات"
                : "ایجاد کاربر"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

/** A small trigger button, so the list page does not repeat the dialog. */
export function CreateUserButton({ onClick }: { onClick: () => void }) {
  return (
    <Button size="sm" onClick={onClick} className="bg-emerald-600 hover:bg-emerald-700">
      کاربر جدید
    </Button>
  );
}

/** The per-row edit action, rendered inside the users table. */
export function EditUserButton({
  user,
  onClick,
}: {
  user: AdminUser;
  onClick: () => void;
}) {
  return (
    <Button size="sm" variant="ghost" onClick={onClick}>
      ویرایش
    </Button>
  );
}
