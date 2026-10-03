"use client";

/**
 * User settings card — who may register, and what a new account becomes.
 *
 * Both were previously absent, which meant registration was always open and
 * every new account was a `customer` with no way to change either. A store in
 * pre-launch needs the first off; a wholesale shop that only takes accounts
 * from businesses needs the second set.
 *
 * The default-role field is a text input rather than a picker of roles on
 * purpose: the server refuses a privileged slug, and a dropdown full of
 * roles it will silently reject is worse than a field that says what to type.
 */

import { useCallback, useEffect, useState } from "react";
import { Save, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useToast } from "@/components/ui/use-toast";
import { siteOptionsApi } from "@/lib/api/wp-parity";

const FIELDS: Array<{
  key: string;
  label: string;
  placeholder: string;
  dir?: "ltr" | "rtl";
  hint?: string;
}> = [
  {
    key: "registration_enabled",
    label: "ثبت‌نام باز باشد",
    placeholder: "1",
    dir: "ltr",
    hint: "۱ = هر کسی می‌تواند حساب بسازد. ۰ = فرم ثبت‌نام بسته می‌شود (کاربران موجود همچنان وارد می‌شوند).",
  },
  {
    key: "registration_default_role",
    label: "نقش پیش‌فرض حساب تازه",
    placeholder: "customer",
    dir: "ltr",
    hint: "نامک (slug) نقش. نقش‌های مدیریتی از سرور رد می‌شوند و به customer برمی‌گردند.",
  },
];

export function UserSettingsCard() {
  const { toast } = useToast();
  const [values, setValues] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await siteOptionsApi.list();
      const next: Record<string, string> = {};
      for (const f of FIELDS) {
        const raw = data[f.key];
        next[f.key] = raw === null || raw === undefined ? "" : String(raw);
      }
      setValues(next);
    } catch {
      toast({
        title: "خواندن تنظیمات کاربران ناموفق بود",
        description: "مقادیر فعلی نمایش داده نشد.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const save = async () => {
    setSaving(true);
    try {
      for (const f of FIELDS) {
        await siteOptionsApi.set(f.key, values[f.key] ?? "");
      }
      toast({ title: "تنظیمات کاربران ذخیره شد" });
      await load();
    } catch {
      toast({
        title: "ذخیره‌ی تنظیمات کاربران ناموفق بود",
        variant: "destructive",
      });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-4 space-y-4" dir="rtl">
      <div className="flex items-center gap-2">
        <Users className="h-4 w-4" />
        <h3 className="text-sm font-bold">کاربران و ثبت‌نام</h3>
      </div>

      {FIELDS.map((f) => (
        <div key={f.key} className="space-y-1.5">
          <Label htmlFor={`uopt-${f.key}`} className="text-xs">
            {f.label}
          </Label>
          <Input
            id={`uopt-${f.key}`}
            value={values[f.key] ?? ""}
            disabled={loading || saving}
            onChange={(e) =>
              setValues((prev) => ({ ...prev, [f.key]: e.target.value }))
            }
            placeholder={f.placeholder}
            dir={f.dir ?? "rtl"}
            className={f.dir === "ltr" ? "text-left" : ""}
          />
          {f.hint && (
            <p className="text-[11px] text-muted-foreground">{f.hint}</p>
          )}
        </div>
      ))}

      <div className="flex gap-2">
        <Button size="sm" onClick={save} disabled={loading || saving}>
          <Save className="h-4 w-4 ms-1" />
          {saving ? "در حال ذخیره..." : "ذخیره"}
        </Button>
        <Button size="sm" variant="outline" onClick={load} disabled={loading || saving}>
          بازخوانی
        </Button>
      </div>
    </Card>
  );
}
