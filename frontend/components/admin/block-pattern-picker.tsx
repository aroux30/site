"use client";

/**
 * الگوهای بلوک (Block Patterns) — کتابخانه الگوهای آماده.
 *
 * الگوها در کد بک‌اند ثبت شده‌اند و جدول یا مهاجرتی ندارند؛ کار این پنجره فقط
 * انتخاب الگو، پر کردن متغیرها و تحویل HTML رندرشده به ویرایشگر است. رندر سمت
 * سرور انجام می‌شود تا یک منبع واحد برای جایگزینی `{{slot}}` و HTML-escape
 * مقادیر داشته باشیم — پیش‌نمایشی که اینجا نشان می‌دهید دقیقاً همان چیزی است
 * که درج می‌شود.
 *
 * انتخابگر به‌صورت کنترل بیرونی ساخته شده: خودش یک Dialog تودرتو باز می‌کند و
 * یک «درج» مستقل با خودش دارد تا بتوان آن را کنار هر ویرایشگر متنی
 * (صفحه، مقاله و…) گذاشت و خروجی را به `body` همان ویرایشگر تحویل داد.
 */

import { useCallback, useMemo, useState } from "react";
import { LayoutTemplate, Loader2, RefreshCw, Search } from "lucide-react";
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
import { useAdminQuery } from "@/lib/api/admin-query";
import {
  blockPatternsApi,
  type BlockPattern,
} from "@/lib/api/block-patterns";
import { toPersianDigits } from "@/lib/utils";

interface BlockPatternPickerProps {
  /** باز/بسته شدن پنجره انتخاب الگو */
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** با HTML رندرشده صدا زده می‌شود؛ خودِ درج با متن موجود در ادغام می‌شود. */
  onInsert: (html: string) => void;
}

export function BlockPatternPicker({
  open,
  onOpenChange,
  onInsert,
}: BlockPatternPickerProps) {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<BlockPattern | null>(null);
  // مقدار هر فیلد؛ کلیدها از `variables` الگوی انتخاب‌شده می‌آیند.
  const [values, setValues] = useState<Record<string, string>>({});
  const [rendering, setRendering] = useState(false);
  const [renderError, setRenderError] = useState<string | null>(null);

  const { data: groups, loading, error, reload } = useAdminQuery({
    // ثابت، چون آرایهٔ درون‌خطی در هر رندر کلید تازه می‌سازد و کش بی‌اثر می‌شود.
    queryKey: ["content", "block-patterns"],
    queryFn: blockPatternsApi.list,
    fallbackError: "بارگذاری الگوهای بلوک ناموفق بود",
  });

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    if (!term || !groups) return groups ?? [];
    return groups
      .map((group) => ({
        ...group,
        patterns: group.patterns.filter((pattern) =>
          [pattern.title, pattern.description, pattern.category, ...pattern.keywords]
            .join(" ")
            .toLowerCase()
            .includes(term),
        ),
      }))
      .filter((group) => group.patterns.length > 0);
  }, [groups, search]);

  const openPattern = useCallback((pattern: BlockPattern) => {
    setSelected(pattern);
    setRenderError(null);
    // فیلدها با متن پیش‌فرض الگو پر می‌شوند؛ ویرایشگر می‌تواند همان را نگه دارد.
    setValues(
      Object.fromEntries(
        pattern.variables.map((variable) => [variable.name, variable.default]),
      ),
    );
  }, []);

  const closePattern = useCallback(() => {
    setSelected(null);
    setRenderError(null);
  }, []);

  const closeAll = useCallback(() => {
    onOpenChange(false);
    // با بستن پنجره، انتخاب و نتیجهٔ رندر نباید به نوبت بعد سرریز کنند.
    setSelected(null);
    setSearch("");
    setRenderError(null);
  }, [onOpenChange]);

  const renderAndInsert = async () => {
    if (!selected) return;
    setRendering(true);
    setRenderError(null);
    try {
      const result = await blockPatternsApi.render(
        selected.slug,
        Object.fromEntries(
          // فقط فیلدهای پرشده فرستاده می‌شوند تا سرور برای بقیه مقدار پیش‌فرض
          // الگو را بگذارد.
          Object.entries(values).filter(([, value]) => value.trim() !== ""),
        ),
      );
      onInsert(result.html);
      closeAll();
    } catch {
      setRenderError("ساخت HTML الگو ناموفق بود. لطفاً دوباره تلاش کنید.");
    } finally {
      setRendering(false);
    }
  };

  return (
    <Dialog
      open={open && !selected}
      onOpenChange={(next) => (next ? onOpenChange(true) : closeAll())}
    >
      <DialogContent className="max-w-3xl" dir="rtl">
        <DialogHeader>
          <DialogTitle>درج الگوی بلوک</DialogTitle>
          <DialogDescription>
            یک بخش آماده انتخاب کنید، متن‌هایش را پر کنید و در انتهای محتوا درج
            شود
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex justify-center py-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        ) : error ? (
          <div className="space-y-3 py-10 text-center">
            <p className="text-sm text-destructive">{error}</p>
            <Button variant="outline" size="sm" onClick={() => void reload()}>
              <RefreshCw className="h-4 w-4 ms-1" />
              تلاش مجدد
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute start-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="جستجو در عنوان، توضیح یا کلیدواژه‌ها…"
                  className="ps-9"
                />
              </div>
              <Button variant="outline" size="sm" onClick={() => void reload()}>
                <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
              </Button>
            </div>

            {filtered.length === 0 ? (
              <p className="py-8 text-center text-sm text-muted-foreground">
                {search.trim()
                  ? "الگویی با این عبارت پیدا نشد"
                  : "هنوز الگویی ثبت نشده است"}
              </p>
            ) : (
              <div className="max-h-[26rem] space-y-4 overflow-y-auto pl-1">
                {filtered.map((group) => (
                  <section key={group.category}>
                    <h4 className="mb-2 text-xs font-semibold text-muted-foreground">
                      {group.category}
                    </h4>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {group.patterns.map((pattern) => (
                        <button
                          key={pattern.slug}
                          type="button"
                          onClick={() => openPattern(pattern)}
                          className="rounded-lg border p-3 text-start transition hover:border-primary hover:bg-accent"
                        >
                          <span className="flex items-center gap-1.5 text-sm font-medium">
                            <LayoutTemplate className="h-4 w-4 text-muted-foreground" />
                            {pattern.title}
                          </span>
                          <span className="mt-1 block text-xs text-muted-foreground">
                            {pattern.description}
                          </span>
                        </button>
                      ))}
                    </div>
                  </section>
                ))}
              </div>
            )}

            {filtered.length > 0 && (
              <p className="text-[10px] text-muted-foreground">
                {toPersianDigits(String(filtered.length))} دسته و{" "}
                {toPersianDigits(
                  String(
                    filtered.reduce((total, group) => total + group.patterns.length, 0),
                  ),
                )}{" "}
                الگو
              </p>
            )}
          </div>
        )}
      </DialogContent>

      {/* فرم متغیرها: پنجرهٔ دوم، تا انتخاب الگو پس از تکمیل فرم باقی بماند. */}
      <Dialog open={Boolean(selected)} onOpenChange={(next) => (next ? undefined : closePattern())}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>{selected?.title ?? "الگو"}</DialogTitle>
            <DialogDescription>
              {selected?.description ??
                "فیلدهای زیر را پر کنید؛ مقادیر خالی با متن پیش‌فرض الگو جایگزین می‌شوند"}
            </DialogDescription>
          </DialogHeader>

          {selected && selected.variables.length > 0 && (
            <div className="max-h-[24rem] space-y-3 overflow-y-auto pl-1">
              {selected.variables.map((variable) => (
                <div key={variable.name} className="grid gap-2">
                  <Label htmlFor={`bp-var-${variable.name}`}>
                    {variable.label}
                  </Label>
                  <Input
                    id={`bp-var-${variable.name}`}
                    value={values[variable.name] ?? ""}
                    onChange={(e) =>
                      setValues((prev) => ({
                        ...prev,
                        [variable.name]: e.target.value,
                      }))
                    }
                    placeholder={variable.default}
                    dir={/^(image_url|cta_url)$/.test(variable.name) ? "ltr" : undefined}
                    className={
                      /^(image_url|cta_url)$/.test(variable.name) ? "text-left" : undefined
                    }
                  />
                </div>
              ))}
            </div>
          )}

          {selected && selected.variables.length === 0 && (
            <p className="py-4 text-center text-sm text-muted-foreground">
              این الگو متغیری ندارد و آمادهٔ درج است
            </p>
          )}

          {renderError && (
            <p className="text-sm text-destructive">{renderError}</p>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={closePattern} disabled={rendering}>
              بازگشت
            </Button>
            <Button onClick={() => void renderAndInsert()} disabled={rendering}>
              {rendering ? "در حال درج…" : "درج در محتوا"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Dialog>
  );
}

export default BlockPatternPicker;
