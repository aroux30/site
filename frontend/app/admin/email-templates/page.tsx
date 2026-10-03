"use client";

/**
 * Email template editor.
 *
 * The four transactional emails were HTML literals in the backend, so changing
 * the wording of an order confirmation meant a code change and a deploy. This
 * is the writing half: pick a template, edit the subject and the body, see
 * which variables it uses, preview it with sample values, save an override.
 *
 * Two things the screen refuses to be wrong about:
 *
 * - **The variable list is not decoration.** A variable the body uses but the
 *   form does not declare cannot be supplied at send time, so the customer
 *   would receive a blank where an order number should be. The backend
 *   refuses the save; this lists what the body actually references so the
 *   author is not guessing which ones to tick.
 * - **"Reset" is not "delete".** It drops the override and puts the built-in
 *   wording back. Deleting a template row without a fallback would leave the
 *   flow with no template at all.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { Mail, Save, RotateCcw, Eye, Code2, TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  emailTemplatesAdminApi,
  type EmailTemplate,
} from "@/lib/api/notifications";
import { toPersianDigits } from "@/lib/utils";

/** Persian labels for the templates a store is most likely to want to reword. */
const TEMPLATE_LABELS: Record<string, string> = {
  order_confirmation: "تأیید سفارش",
  order_shipped: "ارسال سفارش",
  refund_processed: "پردازش بازگشت وجه",
  password_reset: "بازنشانی رمز عبور",
};

/** A default for every variable the built-in templates use, offered as hints. */
const VARIABLE_HINTS: Record<string, string> = {
  store_name: "نام فروشگاه",
  order_number: "شماره سفارش",
  order_id: "شناسه سفارش",
  customer_name: "نام مشتری",
  amount: "مبلغ",
  total: "مبلغ کل",
  tracking_code: "کد رهگیری",
  tracking_url: "لینک رهگیری",
  refund_amount: "مبلغ بازگشتی",
  product_name: "نام محصول",
  quantity: "تعداد",
  link: "لینک",
  code: "کد",
  minutes: "دقیقه",
};

/** Every {{name}} in the body, in the order they appear. */
function variablesUsedIn(text: string): string[] {
  const found: string[] = [];
  for (const m of text.matchAll(/\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g)) {
    // noUncheckedIndexedAccess makes a capture group `string | undefined`.
    const name = m[1];
    if (name && !found.includes(name)) found.push(name);
  }
  return found;
}

export default function EmailTemplatesPage() {
  const { toast } = useToast();
  const [templates, setTemplates] = useState<EmailTemplate[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  const [variables, setVariables] = useState<string[]>([]);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const items = await emailTemplatesAdminApi.list();
      setTemplates(items);
      setSelected((prev) => prev ?? items[0]?.name ?? null);
    } catch {
      toast({ title: "خواندن قالب‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const current = useMemo(
    () => templates.find((t) => t.name === selected) ?? null,
    [templates, selected],
  );

  useEffect(() => {
    if (!current) return;
    setSubject(current.subject ?? "");
    setBody(current.body_template ?? "");
    setVariables(current.variables ?? []);
    setPreview(null);
  }, [current]);

  const usedInBody = useMemo(() => variablesUsedIn(body), [body]);
  const usedInSubject = useMemo(() => variablesUsedIn(subject), [subject]);
  const usedEverywhere = useMemo(
    () => Array.from(new Set([...usedInBody, ...usedInSubject])),
    [usedInBody, usedInSubject],
  );
  /** Used but not declared: these are what the backend will refuse over. */
  const undeclared = usedEverywhere.filter((v) => !variables.includes(v));
  /** Declared but never used: a promise the render will not keep. */
  const unused = variables.filter((v) => !usedEverywhere.includes(v));

  const toggleVariable = (name: string) => {
    setVariables((prev) =>
      prev.includes(name) ? prev.filter((v) => v !== name) : [...prev, name],
    );
  };

  const handleSave = async () => {
    if (!selected) return;
    if (undeclared.length > 0) {
      toast({
        title: "متغیرهای استفاده‌شده ولی اعلام‌نشده",
        description: undeclared.join("، "),
        variant: "destructive",
      });
      return;
    }
    setBusy(true);
    try {
      await emailTemplatesAdminApi.save(selected, {
        subject: subject.trim() || null,
        body_template: body,
        variables,
      });
      toast({
        title: "قالب ذخیره شد",
        description: "ارسال بعدی از همین متن استفاده می‌کند.",
      });
      setPreview(null);
      await load();
    } catch (err) {
      // The backend refuses with the reason in the detail; showing it is the
      // difference between "something is wrong" and "this tag is not allowed".
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "ذخیره قالب ناموفق بود";
      toast({ title: "ذخیره قالب ناموفق بود", description: String(detail), variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const handleReset = async () => {
    if (!selected || !current?.is_custom) return;
    setBusy(true);
    try {
      await emailTemplatesAdminApi.reset(selected);
      toast({ title: "قالب به متن اصلی برگشت" });
      setPreview(null);
      await load();
    } catch {
      toast({ title: "بازنشانی قالب ناموفق بود", variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  const handlePreview = async () => {
    if (!selected) return;
    setBusy(true);
    try {
      const out = await emailTemplatesAdminApi.preview({
        name: selected,
        subject,
        body_template: body,
        variables,
      });
      // The iframe below is sandboxed with no allow-scripts: the template is
      // HTML from an editor, and a stray script must not run in the admin
      // origin.
      setPreview(out.html);
    } catch (err) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "پیش‌نمایش ناموفق بود";
      toast({ title: "پیش‌نمایش ناموفق بود", description: String(detail), variant: "destructive" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-5 p-4 sm:p-6">
      <div>
        <h1 className="flex items-center gap-2 text-xl font-bold">
          <Mail className="h-5 w-5 text-primary" />
          قالب‌های ایمیل
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          متن ایمیل‌های تراکنشی. هر تغییر اینجا بلافاصله روی ایمیل بعدی اثر می‌گذارد؛
          «بازنشانی» متن اصلیِ کد را برمی‌گرداند.
        </p>
      </div>

      {loading ? (
        <p className="text-sm text-muted-foreground">در حال خواندن قالب‌ها...</p>
      ) : templates.length === 0 ? (
        <Card className="p-6 text-center text-sm text-muted-foreground">
          هیچ قالبی برای ویرایش وجود ندارد.
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {templates.map((t) => (
              <Button
                key={t.name}
                variant={selected === t.name ? "default" : "outline"}
                size="sm"
                onClick={() => setSelected(t.name)}
              >
                {TEMPLATE_LABELS[t.name] ?? t.name}
                {t.is_custom && (
                  <span
                    className="ms-1.5 text-[10px] opacity-80"
                    title="متن سفارشی"
                  >
                    ویرایش‌شده
                  </span>
                )}
              </Button>
            ))}
          </div>

          {current && (
            <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
              <Card className="space-y-4 p-5">
                <div className="flex items-center justify-between">
                  <h2 className="text-sm font-bold">
                    {TEMPLATE_LABELS[current.name] ?? current.name}
                  </h2>
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void handlePreview()}
                      disabled={busy}
                    >
                      <Eye className="h-4 w-4" /> پیش‌نمایش
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => void handleReset()}
                      disabled={busy || !current.is_custom}
                      title={
                        current.is_custom
                          ? "بازگرداندن متن اصلی"
                          : "این قالب هنوز متن اصلی را دارد"
                      }
                    >
                      <RotateCcw className="h-4 w-4" /> بازنشانی
                    </Button>
                    <Button size="sm" onClick={() => void handleSave()} disabled={busy}>
                      <Save className="h-4 w-4" /> ذخیره
                    </Button>
                  </div>
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="tpl-subject">موضوع ایمیل</Label>
                  <Input
                    id="tpl-subject"
                    value={subject}
                    onChange={(e) => setSubject(e.target.value)}
                    placeholder="مثلاً: سفارش شما ثبت شد"
                  />
                </div>

                <div className="grid gap-2">
                  <Label htmlFor="tpl-body" className="flex items-center gap-1">
                    <Code2 className="h-3.5 w-3.5" /> متن (HTML)
                  </Label>
                  <Textarea
                    id="tpl-body"
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    rows={14}
                    dir="ltr"
                    className="text-left font-mono text-xs"
                  />
                  <p className="text-[11px] text-muted-foreground">
                    برای متغیرها از <code dir="ltr">{"{{نام}}"}</code> استفاده کنید.
                    استایل inline و جدول مجاز است؛ script و iframe پذیرفته نمی‌شود.
                  </p>
                </div>
              </Card>

              <div className="space-y-4">
                <Card className="p-5">
                  <h3 className="mb-1 text-sm font-bold">متغیرهای این قالب</h3>
                  <p className="mb-3 text-[11px] text-muted-foreground">
                    هر متغیری که در متن استفاده شود باید اینجا اعلام شود، وگرنه
                    ذخیره رد می‌شود: مقداری که اعلام نشده باشد هنگام ارسال خالی
                    می‌ماند.
                  </p>

                  {undeclared.length > 0 && (
                    <p className="mb-3 flex items-start gap-1.5 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-[11px] text-destructive">
                      <TriangleAlert className="mt-0.5 h-3 w-3 shrink-0" />
                      استفاده شده ولی اعلام نشده: {undeclared.join("، ")}
                    </p>
                  )}
                  {unused.length > 0 && (
                    <p className="mb-3 text-[11px] text-muted-foreground">
                      اعلام شده ولی در متن نیست: {unused.join("، ")}
                    </p>
                  )}

                  <div className="flex flex-wrap gap-1.5">
                    {Array.from(
                      new Set([...variables, ...usedEverywhere, ...Object.keys(VARIABLE_HINTS)]),
                    ).map((v) => {
                      const on = variables.includes(v);
                      const used = usedEverywhere.includes(v);
                      return (
                        <button
                          key={v}
                          type="button"
                          onClick={() => toggleVariable(v)}
                          title={VARIABLE_HINTS[v] ?? v}
                          className={`rounded-full border px-2.5 py-0.5 text-[11px] transition-all ${
                            on
                              ? "border-emerald-600 bg-emerald-600/10 font-bold text-emerald-600"
                              : "border-border bg-muted/50 text-muted-foreground hover:border-emerald-500/40"
                          }`}
                        >
                          <span dir="ltr">{v}</span>
                          {used && !on && <span className="ms-1 text-destructive">*</span>}
                        </button>
                      );
                    })}
                  </div>
                  <p className="mt-2 text-[10px] text-muted-foreground">
                    ستاره قرمز یعنی در متن استفاده شده ولی تیک نخورده. (
                    {toPersianDigits(String(usedEverywhere.length))} متغیر در متن)
                  </p>
                </Card>

                {preview && (
                  <Card className="overflow-hidden p-0">
                    <p className="border-b border-border bg-muted/40 px-4 py-2 text-xs font-semibold">
                      پیش‌نمایش با مقادیر نمونه
                    </p>
                    <iframe
                      // sandbox with no allow-scripts: the template is HTML from
                      // an editor, and a stray script must not run in the admin
                      // origin. Not allow-top-navigation either — a link in the
                      // template must not navigate the admin away.
                      sandbox=""
                      title="پیش‌نمایش ایمیل"
                      srcDoc={preview}
                      className="h-[520px] w-full border-0 bg-white"
                    />
                  </Card>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
