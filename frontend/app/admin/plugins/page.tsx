"use client";

import React, { useState } from "react";
import { Boxes, RefreshCw, Zap } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { toPersianDigits } from "@/lib/utils";

const PLUGINS_QUERY_KEY = "admin-plugins" as const;

interface HookBinding {
  plugin: string;
  priority: number;
  handler: string;
}

interface DeclaredHook {
  name: string;
  kind: "action" | "filter";
  /** False when nothing has bound to it yet. */
  bound: boolean;
  handlers: Array<{ plugin: string; priority: number; enabled: boolean }>;
}

interface RegistryDescription {
  plugins: string[];
  disabled_plugins: string[];
  plugin_states: Record<string, boolean>;
  actions: Record<string, HookBinding[]>;
  filters: Record<string, HookBinding[]>;
  /**
   * Every hook the platform fires, including the points no plugin has bound
   * to. The two maps above only ever describe what is currently registered,
   * so before this the surface a plugin could bind to was four points and the
   * rest were invisible until something used them.
   */
  hooks: DeclaredHook[];
}

/**
 * Plugin/hook registry browser (WordPress "Plugins" parity, introspection).
 *
 * The registry is code-registered (plugins call register_plugin at import),
 * so this page reports what is live and where each hook is bound — the
 * operational view an admin needs to answer "why did my hook not run?".
 */
export default function AdminPluginsPage() {
  const { toast } = useToast();
  const [busyPlugin, setBusyPlugin] = useState<string | null>(null);

  const {
    data: desc,
    loading,
    reload: load,
  } = useAdminQuery({
    queryKey: [PLUGINS_QUERY_KEY],
    queryFn: async () => (await apiClient.get<RegistryDescription>("/content/admin/plugins")).data,
    fallbackError: "خطا در دریافت رجیستری",
    // This page reported load failures as a toast and left the view empty;
    // the description names the permission it needs, which is the operator's
    // actual next step.
    toastOnError: true,
    toastDescription: "دسترسی settings:write لازم است.",
  });
  const runMutation = useAdminMutation();

  const togglePlugin = async (name: string, enabled: boolean) => {
    setBusyPlugin(name);
    const result = await runMutation(
      () => apiClient.post(`/content/admin/plugins/${name}/toggle`, { enabled }),
      {
        fallbackError: "تغییر وضعیت ناموفق بود",
        invalidateKeys: [[PLUGINS_QUERY_KEY]],
      },
    );
    if (result.ok) {
      toast({
        title: enabled ? `پلاگین «${name}» فعال شد` : `پلاگین «${name}» غیرفعال شد`,
        description: enabled
          ? "هوک‌های این پلاگین از این پس اجرا می‌شوند."
          : "هوک‌های این پلاگین تا زمان فعال‌سازی مجدد اجرا نمی‌شوند.",
        variant: "success",
      });
    } else {
      toast({
        title: "تغییر وضعیت ناموفق بود",
        description: "نقطه «core» قابل غیرفعال‌سازی نیست.",
        variant: "destructive",
      });
    }
    setBusyPlugin(null);
  };

  const actionCount = Object.values(desc?.actions ?? {}).reduce((n, h) => n + h.length, 0);
  const filterCount = Object.values(desc?.filters ?? {}).reduce((n, h) => n + h.length, 0);
  // The declared surface, not the bound one: this is the list a plugin author
  // needs, and before it existed the page showed a count of zero for a
  // platform that fires fourteen hooks.
  const declaredHooks = desc?.hooks ?? [];
  const unboundHooks = declaredHooks.filter((h) => !h.bound);

  const hookSection = (
    title: string,
    hooks: Record<string, HookBinding[]>,
    emptyText: string,
  ) => (
    <Card className="p-6">
      <h3 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <Zap className="h-4 w-4 text-primary" />
        {title}
      </h3>
      {Object.keys(hooks).length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <div className="space-y-3">
          {Object.entries(hooks).map(([hook, handlers]) => (
            <div key={hook} className="rounded-lg border p-3">
              <p className="font-mono text-sm font-medium" dir="ltr">
                {hook}
              </p>
              <div className="mt-2 space-y-1">
                {handlers.map((h, i) => (
                  <div
                    key={`${h.plugin}-${i}`}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="font-mono text-muted-foreground" dir="ltr">
                      {h.handler}
                    </span>
                    <span className="flex items-center gap-2">
                      <Badge variant="outline" className="text-[10px]" dir="ltr">
                        {h.plugin}
                      </Badge>
                      <span className="text-muted-foreground">
                        اولویت {toPersianDigits(String(h.priority))}
                      </span>
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Boxes className="h-5 w-5 text-primary" />
            پلاگین‌ها و هوک‌ها
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            نمای عملیاتی رجیستری افزونه‌ها: چه پلاگینی ثبت شده و روی کدام هوک‌ها نشسته است
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={load}>
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex justify-center py-10">
          <RefreshCw className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      ) : !desc ? (
        <Card className="p-8 text-center text-sm text-muted-foreground">
          رجیستری در دسترس نیست
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">پلاگین‌های ثبت‌شده</p>
              <p className="mt-1 text-2xl font-bold">{toPersianDigits(String(desc.plugins.length))}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">اکشن‌ها (actions)</p>
              <p className="mt-1 text-2xl font-bold">{toPersianDigits(String(actionCount))}</p>
            </Card>
            <Card className="p-4">
              <p className="text-xs text-muted-foreground">فیلترها (filters)</p>
              <p className="mt-1 text-2xl font-bold">{toPersianDigits(String(filterCount))}</p>
            </Card>
          </div>

          <Card className="p-6">
            <div className="mb-1 flex flex-wrap items-center justify-between gap-2">
              <h3 className="text-lg font-semibold">نقاط اتصال پلاگین</h3>
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="outline">
                  {toPersianDigits(String(declaredHooks.length))} نقطه
                </Badge>
                <Badge variant="outline">
                  {toPersianDigits(String(unboundHooks.length))} بدون پلاگین
                </Badge>
              </div>
            </div>
            <p className="mb-4 text-xs text-muted-foreground">
              هر نقطه‌ای که یک پلاگین می‌تواند به آن گره بخورد. «بدون پلاگین» یعنی
              هنوز پلاگینی به آن وصل نشده، نه اینکه بی‌اثر است.
            </p>
            {declaredHooks.length === 0 ? (
              <p className="py-4 text-center text-sm text-muted-foreground">
                نقطه‌ی اتصالی اعلام نشده است.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {declaredHooks.map((h) => (
                  <li
                    key={h.name}
                    className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-1.5 text-xs"
                  >
                    <Badge
                      variant="outline"
                      className={
                        h.kind === "action"
                          ? "border-violet-500/40 text-violet-700 dark:text-violet-300"
                          : "border-sky-500/40 text-sky-700 dark:text-sky-300"
                      }
                    >
                      {h.kind === "action" ? "action" : "filter"}
                    </Badge>
                    <span className="font-mono text-[11px]" dir="ltr">
                      {h.name}
                    </span>
                    {h.handlers.length > 0 ? (
                      <span className="text-muted-foreground">
                        {h.handlers
                          .map((x) => `${x.plugin} (${toPersianDigits(String(x.priority))})`)
                          .join("، ")}
                      </span>
                    ) : (
                      <span className="text-muted-foreground/70">بدون پلاگین</span>
                    )}
                  </li>
                ))}
              </ul>
            )}
          </Card>

          <Card className="p-6">
            <h3 className="mb-4 text-lg font-semibold">پلاگین‌های فعال</h3>
            {desc.plugins.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted-foreground">
                هیچ پلاگینی در این فرآیند ثبت نشده است — ثبت پلاگین‌ها در زمان کدگذاری
                (register_plugin) انجام می‌شود و این فهرست در استارت سرور پر می‌شود.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {desc.plugins.map((p) => (
                  <div key={p} className="flex items-center gap-2">
                    <Badge
                      variant={(desc.plugin_states?.[p] ?? true) ? "default" : "destructive"}
                      className="font-mono"
                      dir="ltr"
                    >
                      {p}
                    </Badge>
                    {p !== "core" ? (
                      <button
                        onClick={() => togglePlugin(p, !(desc.plugin_states?.[p] ?? true))}
                        disabled={busyPlugin === p}
                        className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${
                          (desc.plugin_states?.[p] ?? true)
                            ? "bg-primary"
                            : "bg-muted"
                        }`}
                        aria-label={`${p} ${(desc.plugin_states?.[p] ?? true) ? "غیرفعال" : "فعال"}`}
                        title={(desc.plugin_states?.[p] ?? true) ? "غیرفعال‌سازی" : "فعال‌سازی"}
                      >
                        <span
                          className={`absolute top-0.5 h-5 w-5 rounded-full bg-card shadow transition-transform ${
                            (desc.plugin_states?.[p] ?? true) ? "left-0.5" : "right-0.5"
                          }`}
                        />
                      </button>
                    ) : (
                      <span className="text-[10px] text-muted-foreground">(هسته)</span>
                    )}
                  </div>
                ))}
              </div>
            )}
            <p className="mt-3 flex items-center gap-1.5 text-[11px] text-muted-foreground">
              <Zap className="h-3 w-3" />
              پلاگین غیرفعال همچنان ثبت است اما هوک‌هایش اجرا نمی‌شود؛ وضعیت برای همین نصب ذخیره می‌شود.
            </p>
          </Card>

          {hookSection("اکشن‌ها", desc.actions, "هیچ اکشنی ثبت نشده است")}
          {hookSection("فیلترها", desc.filters, "هیچ فیلتری ثبت نشده است")}
        </>
      )}
    </div>
  );
}
