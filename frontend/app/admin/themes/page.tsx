"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  Paintbrush,
  Plus,
  RefreshCw,
  CheckCircle2,
  Copy,
  History,
  RotateCcw,
  Trash2,
  Sliders,
  Check,
  Sparkles,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  themesAdminApi,
  type SiteTheme,
  type ThemeRevision,
} from "@/lib/api/themes";
import { DEFAULT_THEME_TOKENS } from "@/lib/builder/theme-schema";

const COLOR_PRESETS = [
  { name: "زمردی (Emerald)", hex: "#059669" },
  { name: "یشمی روشن", hex: "#10b981" },
  { name: "فیروزه‌ای (Teal)", hex: "#0d9488" },
  { name: "آبی درباری", hex: "#2563eb" },
  { name: "بنفش سلطنتی", hex: "#7c3aed" },
  { name: "یاقوتی (Rose)", hex: "#e11d48" },
  { name: "کهربایی (Amber)", hex: "#f59e0b" },
  { name: "زغالی (Slate)", hex: "#334155" },
];

const RADIUS_OPTIONS = [
  { label: "بدون گردی (0px)", value: "0px" },
  { label: "کوچک (6px)", value: "6px" },
  { label: "متوسط (10px)", value: "10px" },
  { label: "استاندارد (12px)", value: "12px" },
  { label: "بزرگ (16px)", value: "16px" },
  { label: "خیلی بزرگ (24px)", value: "24px" },
];

export default function AdminThemesPage() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [themes, setThemes] = useState<SiteTheme[]>([]);
  const [loading, setLoading] = useState(false);

  // Modals state
  const [createOpen, setCreateOpen] = useState(false);
  const [editTheme, setEditTheme] = useState<SiteTheme | null>(null);
  const [revisionsTheme, setRevisionsTheme] = useState<SiteTheme | null>(null);
  const [revisions, setRevisions] = useState<ThemeRevision[]>([]);
  const [loadingRevisions, setLoadingRevisions] = useState(false);
  const [cloneTheme, setCloneTheme] = useState<SiteTheme | null>(null);

  // Form states
  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formDesc, setFormDesc] = useState("");
  const [formPrimary, setFormPrimary] = useState("#059669");
  const [formSecondary, setFormSecondary] = useState("#0d9488");
  const [formRadius, setFormRadius] = useState("12px");
  const [formFont, setFormFont] = useState("vazirmatn");
  const [submitting, setSubmitting] = useState(false);

  const fetchThemes = useCallback(async () => {
    setLoading(true);
    try {
      const data = await themesAdminApi.list();
      setThemes(data);
    } catch (err) {
      console.error("Failed to load themes:", err);
      toast({
        title: "خطا در بارگذاری تم‌ها",
        description: "امکان دریافت لیست تم‌ها وجود ندارد.",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    fetchThemes();
  }, [fetchThemes]);

  const handleActivate = async (theme: SiteTheme) => {
    try {
      await themesAdminApi.activate(theme.id);
      toast({
        title: "تم فعال شد",
        description: `تم «${theme.name}» به عنوان تم پیش‌فرض و سراسری سایت فعال گردید.`,
      });
      fetchThemes();
    } catch (err) {
      console.error("Failed to activate theme:", err);
      toast({
        title: "خطا در فعال‌سازی",
        description: "عملیات فعال‌سازی تم با خطا مواجه شد.",
        variant: "destructive",
      });
    }
  };

  const handleOpenCreate = () => {
    setFormName("تم جدید");
    setFormSlug(`theme-${Math.random().toString(36).slice(2, 8)}`);
    setFormDesc("");
    setFormPrimary("#059669");
    setFormSecondary("#0d9488");
    setFormRadius("12px");
    setFormFont("vazirmatn");
    setCreateOpen(true);
  };

  const handleOpenEdit = (theme: SiteTheme) => {
    setEditTheme(theme);
    setFormName(theme.name);
    setFormDesc(theme.description || "");
    const sem = theme.tokens?.semantic || {};
    setFormPrimary(String(sem.color?.primary?.$value || "#059669"));
    setFormSecondary(String(sem.color?.secondary?.$value || "#0d9488"));
    setFormRadius(String(sem.dimension?.radius?.$value || "12px"));
    setFormFont(String(sem.typography?.fontFamily?.$value || "vazirmatn"));
  };

  const handleSaveCreate = async () => {
    if (!formName.trim() || !formSlug.trim()) {
      toast({ title: "خطا", description: "نام و نامک تم الزامی است.", variant: "destructive" });
      return;
    }

    setSubmitting(true);
    try {
      const tokens = {
        ...DEFAULT_THEME_TOKENS,
        semantic: {
          ...DEFAULT_THEME_TOKENS.semantic,
          color: {
            ...DEFAULT_THEME_TOKENS.semantic?.color,
            primary: { $value: formPrimary, $type: "color" },
            secondary: { $value: formSecondary, $type: "color" },
          },
          dimension: {
            ...DEFAULT_THEME_TOKENS.semantic?.dimension,
            radius: { $value: formRadius, $type: "dimension" },
          },
        },
      };

      await themesAdminApi.create({
        name: formName.trim(),
        slug: formSlug.trim(),
        description: formDesc.trim() || undefined,
        tokens,
      });

      toast({ title: "تم ایجاد شد", description: `تم «${formName.trim()}» با موفقیت افزوده شد.` });
      setCreateOpen(false);
      fetchThemes();
    } catch (err) {
      console.error("Create theme error:", err);
      toast({ title: "خطا", description: "ایجاد تم ناموفق بود.", variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleSaveEdit = async () => {
    if (!editTheme) return;
    setSubmitting(true);
    try {
      const updatedTokens = {
        ...(editTheme.tokens || DEFAULT_THEME_TOKENS),
        semantic: {
          ...(editTheme.tokens?.semantic || DEFAULT_THEME_TOKENS.semantic),
          color: {
            ...(editTheme.tokens?.semantic?.color || DEFAULT_THEME_TOKENS.semantic?.color),
            primary: { $value: formPrimary, $type: "color" },
            secondary: { $value: formSecondary, $type: "color" },
          },
          dimension: {
            ...(editTheme.tokens?.semantic?.dimension || DEFAULT_THEME_TOKENS.semantic?.dimension),
            radius: { $value: formRadius, $type: "dimension" },
          },
        },
      };

      await themesAdminApi.update(editTheme.id, {
        name: formName.trim(),
        description: formDesc.trim() || undefined,
        tokens: updatedTokens,
      });

      toast({ title: "تم به‌روزرسانی شد", description: "تغییرات توکن‌ها با موفقیت در نسخه جدید ثبت شد." });
      setEditTheme(null);
      fetchThemes();
    } catch (err) {
      console.error("Update theme error:", err);
      toast({ title: "خطا", description: "به‌روزرسانی تم ناموفق بود.", variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleOpenRevisions = async (theme: SiteTheme) => {
    setRevisionsTheme(theme);
    setLoadingRevisions(true);
    try {
      const revs = await themesAdminApi.listRevisions(theme.id);
      setRevisions(revs);
    } catch (err) {
      console.error("Failed to load revisions:", err);
    } finally {
      setLoadingRevisions(false);
    }
  };

  const handleRestoreRevision = async (themeId: string, revId: string) => {
    const ok = await confirm({
      title: "بازگردانی نسخه تم",
      message: "آیا از بازگردانی توکن‌های تم به این نسخه اطمینان دارید؟ تغییرات فعلی به عنوان نسخه جدید ثبت خواهند شد.",
    });
    if (!ok) return;

    try {
      await themesAdminApi.restoreRevision(themeId, revId);
      toast({ title: "نسخه بازگردانی شد", description: "توکن‌های تم به نسخه انتخابی بازگشتند." });
      setRevisionsTheme(null);
      fetchThemes();
    } catch (err) {
      console.error("Restore revision error:", err);
      toast({ title: "خطا", description: "بازگردانی نسخه تم ناموفق بود.", variant: "destructive" });
    }
  };

  const handleSaveClone = async () => {
    if (!cloneTheme || !formName.trim() || !formSlug.trim()) return;
    setSubmitting(true);
    try {
      await themesAdminApi.clone(cloneTheme.id, {
        name: formName.trim(),
        slug: formSlug.trim(),
      });
      toast({ title: "تم کلون شد", description: `نسخه کپی تم «${formName.trim()}» ایجاد شد.` });
      setCloneTheme(null);
      fetchThemes();
    } catch (err) {
      console.error("Clone theme error:", err);
      toast({ title: "خطا", description: "کلون تم ناموفق بود.", variant: "destructive" });
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (theme: SiteTheme) => {
    const ok = await confirm({
      title: "حذف تم",
      message: `آیا از حذف تم «${theme.name}» اطمینان دارید؟ این عمل غیرقابل‌بازگشت است.`,
      confirmVariant: "destructive",
    });
    if (!ok) return;

    try {
      await themesAdminApi.delete(theme.id);
      toast({ title: "تم حذف شد", description: `تم «${theme.name}» با موفقیت حذف گردید.` });
      fetchThemes();
    } catch (err: any) {
      toast({
        title: "خطا در حذف تم",
        description: err?.response?.data?.error?.message || "امکان حذف تم فعال وجود ندارد.",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b pb-5">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Paintbrush className="w-6 h-6 text-primary" />
            <span>مدیریت تم‌ها و استایل سازمانی (Theme Studio)</span>
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            مدیریت تم‌های فعال سایت، توکن‌های طراحی (DTCG)، پالت رنگ سازمانی و تاریخچه نسخه‌ها
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchThemes} disabled={loading}>
            <RefreshCw className={`w-4 h-4 ms-1.5 ${loading ? "animate-spin" : ""}`} />
            <span>بروزرسانی</span>
          </Button>
          <Button size="sm" onClick={handleOpenCreate}>
            <Plus className="w-4 h-4 ms-1.5" />
            <span>ایجاد تم جدید</span>
          </Button>
        </div>
      </div>

      {/* Theme Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {themes.map((theme) => {
          const sem = theme.tokens?.semantic || {};
          const primaryColor = String(sem.color?.primary?.$value || theme.css_variables?.["--primary"] || "#059669");
          const secondaryColor = String(sem.color?.secondary?.$value || theme.css_variables?.["--secondary"] || "#0d9488");
          const radiusVal = String(sem.dimension?.radius?.$value || theme.css_variables?.["--radius"] || "12px");

          return (
            <Card
              key={theme.id}
              className={`p-5 flex flex-col justify-between space-y-4 transition shadow-sm ${
                theme.is_active ? "border-2 border-primary bg-primary/5" : "bg-card"
              }`}
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="font-bold text-base text-foreground line-clamp-1">{theme.name}</span>
                  {theme.is_active ? (
                    <Badge className="bg-primary text-primary-foreground font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" />
                      <span>تم فعال سایت</span>
                    </Badge>
                  ) : (
                    <Badge variant="outline" className="text-muted-foreground">
                      غیرفعال
                    </Badge>
                  )}
                </div>

                <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                  {theme.description || "بدون توضیحات"}
                </p>

                {/* Swatches & Specs */}
                <div className="p-3 rounded-xl bg-background border flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="text-[11px] text-muted-foreground">رنگ‌ها:</span>
                    <div className="flex items-center gap-1">
                      <span
                        className="w-4 h-4 rounded-full border shadow-2xs"
                        style={{ backgroundColor: primaryColor }}
                        title={`اصلی: ${primaryColor}`}
                      />
                      <span
                        className="w-4 h-4 rounded-full border shadow-2xs"
                        style={{ backgroundColor: secondaryColor }}
                        title={`ثانویه: ${secondaryColor}`}
                      />
                    </div>
                  </div>
                  <div className="text-[11px] text-muted-foreground font-mono">
                    شعاع: {radiusVal}
                  </div>
                </div>
              </div>

              {/* Actions Footer */}
              <div className="pt-2 border-t flex items-center justify-between gap-1 flex-wrap">
                <div className="flex items-center gap-1">
                  {!theme.is_active && (
                    <Button
                      size="sm"
                      variant="default"
                      onClick={() => handleActivate(theme)}
                      className="h-8 text-xs font-semibold"
                    >
                      فعال‌سازی
                    </Button>
                  )}
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => handleOpenEdit(theme)}
                    className="h-8 text-xs"
                    title="ویرایش توکن‌ها"
                  >
                    <Sliders className="w-3.5 h-3.5 ms-1" />
                    <span>ویرایش</span>
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => handleOpenRevisions(theme)}
                    className="h-8 text-xs text-muted-foreground hover:text-foreground"
                    title="تاریخچه نسخه‌ها"
                  >
                    <History className="w-3.5 h-3.5" />
                  </Button>
                </div>

                <div className="flex items-center gap-0.5">
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => {
                      setCloneTheme(theme);
                      setFormName(`${theme.name} (کپی)`);
                      setFormSlug(`${theme.slug}-copy`);
                    }}
                    className="h-8 w-8 p-0 text-muted-foreground hover:text-foreground"
                    title="کلون تم"
                  >
                    <Copy className="w-3.5 h-3.5" />
                  </Button>
                  {!theme.is_active && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(theme)}
                      className="h-8 w-8 p-0 text-destructive hover:bg-destructive/10"
                      title="حذف تم"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </Button>
                  )}
                </div>
              </div>
            </Card>
          );
        })}
      </div>

      {/* Create / Edit Dialog */}
      <Dialog open={createOpen || Boolean(editTheme)} onOpenChange={(open) => {
        if (!open) {
          setCreateOpen(false);
          setEditTheme(null);
        }
      }}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Paintbrush className="w-4 h-4 text-primary" />
              <span>{editTheme ? `ویرایش توکن‌های تم «${editTheme.name}»` : "ایجاد تم جدید"}</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="space-y-1.5">
              <Label className="text-xs">نام تم</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="h-8 text-xs"
                placeholder="مثلاً: تم سازمانی نیلی"
              />
            </div>

            {!editTheme && (
              <div className="space-y-1.5">
                <Label className="text-xs">نامک تم (Slug)</Label>
                <Input
                  value={formSlug}
                  onChange={(e) => setFormSlug(e.target.value)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                  placeholder="corporate-indigo"
                />
              </div>
            )}

            <div className="space-y-1.5">
              <Label className="text-xs">توضیحات تم</Label>
              <Input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                className="h-8 text-xs"
                placeholder="توضیح کوتاه کاربرد تم"
              />
            </div>

            {/* Primary Color Picker */}
            <div className="space-y-1.5 pt-2 border-t">
              <Label className="text-xs font-semibold">رنگ اصلی برند (Primary Color)</Label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={formPrimary}
                  onChange={(e) => setFormPrimary(e.target.value)}
                  className="w-8 h-8 rounded-lg cursor-pointer border border-border"
                />
                <Input
                  value={formPrimary}
                  onChange={(e) => setFormPrimary(e.target.value)}
                  className="h-8 font-mono text-xs"
                  dir="ltr"
                />
              </div>
              <div className="flex flex-wrap gap-1 mt-1">
                {COLOR_PRESETS.map((c) => (
                  <button
                    key={c.hex}
                    type="button"
                    onClick={() => setFormPrimary(c.hex)}
                    className="w-5 h-5 rounded-full border border-border shadow-2xs transition hover:scale-110 flex items-center justify-center"
                    style={{ backgroundColor: c.hex }}
                    title={c.name}
                  >
                    {formPrimary.toLowerCase() === c.hex.toLowerCase() && (
                      <Check className="w-3 h-3 text-white drop-shadow" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Secondary Color Picker */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">رنگ ثانویه / مکمل (Secondary Color)</Label>
              <div className="flex items-center gap-2">
                <input
                  type="color"
                  value={formSecondary}
                  onChange={(e) => setFormSecondary(e.target.value)}
                  className="w-8 h-8 rounded-lg cursor-pointer border border-border"
                />
                <Input
                  value={formSecondary}
                  onChange={(e) => setFormSecondary(e.target.value)}
                  className="h-8 font-mono text-xs"
                  dir="ltr"
                />
              </div>
            </div>

            {/* Radius Select */}
            <div className="space-y-1.5">
              <Label className="text-xs font-semibold">شعاع گردی کادرها (Border Radius)</Label>
              <Select value={formRadius} onValueChange={setFormRadius}>
                <SelectTrigger className="h-8 text-xs">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RADIUS_OPTIONS.map((r) => (
                    <SelectItem key={r.value} value={r.value}>
                      {r.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <DialogFooter className="flex items-center justify-end gap-2 pt-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setCreateOpen(false);
                setEditTheme(null);
              }}
              disabled={submitting}
            >
              انصراف
            </Button>
            <Button size="sm" onClick={editTheme ? handleSaveEdit : handleSaveCreate} disabled={submitting}>
              {submitting ? "در حال ثبت..." : editTheme ? "ثبت ویرایش و ساخت نسخه جدید" : "ایجاد تم"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Revisions History Dialog */}
      <Dialog open={Boolean(revisionsTheme)} onOpenChange={(open) => !open && setRevisionsTheme(null)}>
        <DialogContent className="max-w-lg" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <History className="w-4 h-4 text-primary" />
              <span>تاریخچه نسخه‌های تم «{revisionsTheme?.name}»</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-3 py-2 text-xs max-h-80 overflow-y-auto">
            {loadingRevisions ? (
              <p className="text-center py-6 text-muted-foreground">در حال بارگذاری نسخه‌ها...</p>
            ) : revisions.length === 0 ? (
              <p className="text-center py-6 text-muted-foreground">نسخه‌ای برای این تم ثبت نشده است.</p>
            ) : (
              revisions.map((rev) => {
                const sem = rev.tokens?.semantic || {};
                const pColor = String(sem.color?.primary?.$value || "#059669");
                const sColor = String(sem.color?.secondary?.$value || "#0d9488");
                const rVal = String(sem.dimension?.radius?.$value || "12px");

                return (
                  <div
                    key={rev.id}
                    className="p-3 rounded-xl border bg-card flex items-center justify-between gap-3 shadow-xs"
                  >
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-foreground">نسخه {rev.version}</span>
                        {rev.change_summary && (
                          <span className="text-[11px] text-muted-foreground">({rev.change_summary})</span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 text-[11px] text-muted-foreground font-mono">
                        <span className="w-3 h-3 rounded-full border" style={{ backgroundColor: pColor }} />
                        <span>اصلی: {pColor}</span>
                        <span className="w-3 h-3 rounded-full border ms-1" style={{ backgroundColor: sColor }} />
                        <span>ثانویه: {sColor}</span>
                        <span className="ms-1">شعاع: {rVal}</span>
                      </div>
                      <span className="text-[10px] text-muted-foreground block">
                        {new Date(rev.created_at).toLocaleString("fa-IR")}
                      </span>
                    </div>

                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => handleRestoreRevision(rev.theme_id, rev.id)}
                      className="h-7 text-xs gap-1 shrink-0"
                    >
                      <RotateCcw className="w-3 h-3" />
                      <span>بازگردانی</span>
                    </Button>
                  </div>
                );
              })
            )}
          </div>

          <DialogFooter>
            <Button size="sm" variant="outline" onClick={() => setRevisionsTheme(null)}>
              بستن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Clone Theme Dialog */}
      <Dialog open={Boolean(cloneTheme)} onOpenChange={(open) => !open && setCloneTheme(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Copy className="w-4 h-4 text-primary" />
              <span>کلون و کپی از تم «{cloneTheme?.name}»</span>
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-2 text-xs">
            <div className="space-y-1.5">
              <Label className="text-xs">نام تم جدید</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="h-8 text-xs"
              />
            </div>
            <div className="space-y-1.5">
              <Label className="text-xs">نامک تم جدید (Slug)</Label>
              <Input
                value={formSlug}
                onChange={(e) => setFormSlug(e.target.value)}
                className="h-8 text-xs font-mono"
                dir="ltr"
              />
            </div>
          </div>

          <DialogFooter className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" size="sm" onClick={() => setCloneTheme(null)} disabled={submitting}>
              انصراف
            </Button>
            <Button size="sm" onClick={handleSaveClone} disabled={submitting}>
              {submitting ? "در حال کلون..." : "ایجاد نسخه کپی"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
