"use client";

/** Application passwords (WordPress parity).
 *
 * A phone app or a personal script needs to act on the user's behalf. This is
 * how they do it without the account password ever leaving the password field,
 * and how one client is revoked without cutting off the others.
 *
 * The token is shown exactly once. Only its hash is stored, so a token that
 * gets lost is replaced, never looked up — hence the copy-and-acknowledge step
 * before the field is cleared.
 */
import { useCallback, useEffect, useState } from "react";
import { Check, Copy, KeyRound, Loader2, Plus, ShieldOff, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import { applicationPasswordsApi } from "@/lib/api/auth";
import type { ApplicationPassword } from "@/lib/api/auth";
import { toPersianDigits } from "@/lib/utils";

const SCOPE_PRESETS: { value: string; label: string }[] = [
  { value: "", label: "دسترسی کامل" },
  { value: "orders:read", label: "فقط مشاهده سفارش‌ها" },
];

export function ApplicationPasswordsCard() {
  const { toast } = useToast();
  const [items, setItems] = useState<ApplicationPassword[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [scope, setScope] = useState("");
  const [fresh, setFresh] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await applicationPasswordsApi.list());
    } catch {
      toast({ variant: "destructive", title: "خواندن رمزهای برنامه ناموفق بود." });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async () => {
    const label = name.trim();
    if (!label) return;
    setBusy("create");
    try {
      const created = await applicationPasswordsApi.create({
        name: label,
        scopes: scope ? [scope] : [],
      });
      setFresh(created.token);
      setCopied(false);
      setName("");
      await load();
    } catch {
      toast({ variant: "destructive", title: "ساختن رمز برنامه ناموفق بود." });
    } finally {
      setBusy(null);
    }
  };

  const revoke = async (id: string, label: string) => {
    if (!window.confirm(`رمز برنامه «${label}» باطل شود؟ هر کلاینتی که از آن استفاده می‌کند بلافاصله قطع می‌شود.`)) {
      return;
    }
    setBusy(id);
    try {
      await applicationPasswordsApi.revoke(id);
      await load();
      toast({ title: "رمز برنامه باطل شد." });
    } catch {
      toast({ variant: "destructive", title: "ابطال ناموفق بود." });
    } finally {
      setBusy(null);
    }
  };

  const copy = async () => {
    if (!fresh) return;
    try {
      await navigator.clipboard.writeText(fresh);
      setCopied(true);
    } catch {
      toast({ variant: "destructive", title: "کپی خودکار ممکن نشد؛ دستی کپی کنید." });
    }
  };

  const formatDate = (value?: string | null) => {
    if (!value) return "—";
    try {
      return new Intl.DateTimeFormat("fa-IR", { dateStyle: "medium" }).format(
        new Date(value),
      );
    } catch {
      return "—";
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <KeyRound className="h-4 w-4" />
          رمزهای برنامه
        </CardTitle>
        <CardDescription>
          برای اپلیکیشن موبایل یا اسکریپت شخصی، به‌جای رمز عبور حساب از این توکن‌ها استفاده کنید.
          هر توکن را جداگانه می‌توانید باطل کنید.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {fresh && (
          <div className="space-y-2 rounded-md border border-amber-500/50 bg-amber-500/5 p-3">
            <p className="text-sm font-medium">
              این توکن فقط همین یک‌بار نمایش داده می‌شود. همین حالا ذخیره‌اش کنید.
            </p>
            <div className="flex gap-2">
              <Input readOnly value={fresh} dir="ltr" className="font-mono text-xs" />
              <Button size="sm" variant="outline" onClick={() => void copy()}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <Button size="sm" onClick={() => setFresh(null)}>
              ذخیره کردم
            </Button>
          </div>
        )}

        <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto]">
          <Input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="نام کلاینت، مثلاً «گوشی من»"
          />
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value)}
            className="rounded-md border border-input bg-background px-3 py-2 text-sm"
          >
            {SCOPE_PRESETS.map((p) => (
              <option key={p.value} value={p.value}>
                {p.label}
              </option>
            ))}
          </select>
          <Button
            onClick={() => void create()}
            disabled={!name.trim() || busy === "create"}
          >
            {busy === "create" ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            ساختن
          </Button>
        </div>

        {loading ? (
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">هنوز رمز برنامه‌ای نساخته‌اید.</p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => (
              <li
                key={item.id}
                className="flex items-center gap-2 border-b border-border/50 py-2 last:border-0"
              >
                <div className="flex-1">
                  <p className="text-sm font-medium">{item.name}</p>
                  <p className="text-xs text-muted-foreground" dir="ltr">
                    {item.token_prefix}…
                    {item.last_used_at
                      ? ` · آخرین استفاده: ${formatDate(item.last_used_at)}`
                      : " · هنوز استفاده نشده"}
                  </p>
                </div>
                {item.is_active ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={busy === item.id}
                    onClick={() => void revoke(item.id, item.name)}
                  >
                    {busy === item.id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Trash2 className="h-3.5 w-3.5 text-destructive" />
                    )}
                    ابطال
                  </Button>
                ) : (
                  <Badge variant="secondary">
                    <ShieldOff className="mr-1 h-3 w-3" />
                    باطل‌شده
                  </Badge>
                )}
              </li>
            ))}
          </ul>
        )}

        {items.length > 0 && (
          <p className="text-xs text-muted-foreground">
            مجموع {toPersianDigits(items.length)} رمز برنامه ثبت شده است.
          </p>
        )}
      </CardContent>
    </Card>
  );
}
