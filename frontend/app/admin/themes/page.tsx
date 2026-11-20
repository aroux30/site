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
  Eye,
  Palette,
  Type,
  Layers,
  Box,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
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
import { toValidHexColor } from "@/lib/builder/color-utils";
import { checkWcagCompliance } from "@/lib/wcag-contrast";

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

const SHADOW_OPTIONS = [
  { label: "بدون سایه (None)", value: "none" },
  { label: "ظریف (Sm)", value: "0 1px 2px 0 rgb(0 0 0 / 0.05)" },
  { label: "استاندارد (Md)", value: "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)" },
  { label: "عمیق (Lg)", value: "0 10px 15px -3px rgb(0 0 0 / 0.1), 0 4px 6px -4px rgb(0 0 0 / 0.1)" },
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
  const [modalTab, setModalTab] = useState<"colors" | "typography" | "preview">("colors");

  // Form states - metadata
  const [formName, setFormName] = useState("");
  const [formSlug, setFormSlug] = useState("");
  const [formDesc, setFormDesc] = useState("");

  // Form states - colors
  const [formPrimary, setFormPrimary] = useState("#059669");
  const [formSecondary, setFormSecondary] = useState("#0d9488");
  const [formBackground, setFormBackground] = useState("#ffffff");
  const [formForeground, setFormForeground] = useState("#09090b");
  const [formSurface, setFormSurface] = useState("#f8fafc");
  const [formMuted, setFormMuted] = useState("#f1f5f9");
  const [formBorder, setFormBorder] = useState("#e2e8f0");
  const [formSuccess, setFormSuccess] = useState("#16a34a");
  const [formWarning, setFormWarning] = useState("#f59e0b");
  const [formDestructive, setFormDestructive] = useState("#e11d48");
  const [formInfo, setFormInfo] = useState("#2563eb");

  // Form states - typography & dimensions
  const [formRadius, setFormRadius] = useState("12px");
  const [formShadow, setFormShadow] = useState(SHADOW_OPTIONS[2]?.value || "none");
  const [formFont, setFormFont] = useState("vazirmatn");
  const [formFontSize, setFormFontSize] = useState("15px");
  const [formContainerWidth, setFormContainerWidth] = useState("1280px");
  const [formContentWidth, setFormContentWidth] = useState("768px");
  const [formSectionSpacing, setFormSectionSpacing] = useState("64px");
  const [formSpacingScale, setFormSpacingScale] = useState("16px");

  const [submitting, setSubmitting] = useState(false);

  // WCAG 2.1 AA Contrast Ratios calculation
  const textBgContrast = useMemo(() => {
    return checkWcagCompliance(formForeground, formBackground);
  }, [formForeground, formBackground]);

  const textSurfaceContrast = useMemo(() => {
    return checkWcagCompliance(formForeground, formSurface);
  }, [formForeground, formSurface]);

  const primaryBtnContrast = useMemo(() => {
    return checkWcagCompliance("#ffffff", formPrimary);
  }, [formPrimary]);

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
    setFormBackground("#ffffff");
    setFormForeground("#09090b");
    setFormSurface("#f8fafc");
    setFormMuted("#f1f5f9");
    setFormBorder("#e2e8f0");
    setFormSuccess("#16a34a");
    setFormWarning("#f59e0b");
    setFormDestructive("#e11d48");
    setFormInfo("#2563eb");
    setFormRadius("12px");
    setFormShadow(SHADOW_OPTIONS[2]?.value || "none");
    setFormFont("vazirmatn");
    setFormFontSize("15px");
    setFormContainerWidth("1280px");
    setFormContentWidth("768px");
    setFormSectionSpacing("64px");
    setFormSpacingScale("16px");
    setModalTab("colors");
    setCreateOpen(true);
  };

  const handleOpenEdit = (theme: SiteTheme) => {
    setEditTheme(theme);
    setFormName(theme.name);
    setFormDesc(theme.description || "");
    const sem = theme.tokens?.semantic || {};
    const col = sem.color || {};
    setFormPrimary(String(col.primary?.$value || "#059669"));
    setFormSecondary(String(col.secondary?.$value || "#0d9488"));
    setFormBackground(String(col.background?.$value || "#ffffff"));
    setFormForeground(String(col.foreground?.$value || "#09090b"));
    setFormSurface(String(col.surface?.$value || "#f8fafc"));
    setFormMuted(String(col.muted?.$value || "#f1f5f9"));
    setFormBorder(String(col.border?.$value || "#e2e8f0"));
    setFormSuccess(String(col.success?.$value || "#16a34a"));
    setFormWarning(String(col.warning?.$value || "#f59e0b"));
    setFormDestructive(String(col.destructive?.$value || "#e11d48"));
    setFormInfo(String(col.info?.$value || "#2563eb"));

    setFormRadius(String(sem.dimension?.radius?.$value || "12px"));
    setFormShadow(String(sem.shadow?.boxShadow?.$value || SHADOW_OPTIONS[2]?.value || "none"));
    const fontVal = String(sem.typography?.fontFamily?.$value || "vazirmatn");
    setFormFont(fontVal.includes("system-ui") && !fontVal.includes("Vazirmatn") ? "system-ui" : "vazirmatn");
    setFormFontSize(String(sem.typography?.fontSize?.$value || "15px"));
    setFormContainerWidth(String(sem.dimension?.containerWidth?.$value || "1280px"));
    setFormContentWidth(String(sem.dimension?.contentWidth?.$value || "768px"));
    setFormSectionSpacing(String(sem.dimension?.sectionSpacing?.$value || "64px"));
    setFormSpacingScale(String(sem.dimension?.spacingScale?.$value || "16px"));
    setModalTab("colors");
  };

  const buildTokensPayload = (baseTokens?: any) => {
    const base = baseTokens || DEFAULT_THEME_TOKENS;
    return {
      ...base,
      semantic: {
        ...(base.semantic || DEFAULT_THEME_TOKENS.semantic),
        color: {
          ...(base.semantic?.color || DEFAULT_THEME_TOKENS.semantic?.color),
          primary: { $value: formPrimary, $type: "color", $description: "Brand Primary" },
          secondary: { $value: formSecondary, $type: "color", $description: "Brand Secondary" },
          background: { $value: formBackground, $type: "color", $description: "Page Background" },
          foreground: { $value: formForeground, $type: "color", $description: "Page Text Color" },
          surface: { $value: formSurface, $type: "color", $description: "Card / Container Surface" },
          muted: { $value: formMuted, $type: "color", $description: "Muted Container / Input" },
          border: { $value: formBorder, $type: "color", $description: "Borders & Dividers" },
          success: { $value: formSuccess, $type: "color", $description: "Success Feedback" },
          warning: { $value: formWarning, $type: "color", $description: "Warning Feedback" },
          destructive: { $value: formDestructive, $type: "color", $description: "Destructive Action" },
          info: { $value: formInfo, $type: "color", $description: "System Info" },
        },
        dimension: {
          ...(base.semantic?.dimension || DEFAULT_THEME_TOKENS.semantic?.dimension),
          radius: { $value: formRadius, $type: "dimension", $description: "Base Border Radius" },
          containerWidth: { $value: formContainerWidth, $type: "dimension", $description: "Max Container Width" },
          contentWidth: { $value: formContentWidth, $type: "dimension", $description: "Readable Content Width" },
          sectionSpacing: { $value: formSectionSpacing, $type: "dimension", $description: "Vertical Section Spacing" },
          spacingScale: { $value: formSpacingScale, $type: "dimension", $description: "Base Spacing Unit" },
        },
        typography: {
          ...(base.semantic?.typography || DEFAULT_THEME_TOKENS.semantic?.typography),
          fontFamily: {
            $value: formFont === "system-ui" ? "system-ui, sans-serif" : "var(--font-vazirmatn, system-ui, sans-serif)",
            $type: "fontFamily",
          },
          fontSize: { $value: formFontSize, $type: "dimension" },
        },
        shadow: {
          boxShadow: { $value: formShadow, $type: "shadow" },
        },
      },
      component: {
        ...(base.component || DEFAULT_THEME_TOKENS.component),
        button: {
          radius: { $value: formRadius, $type: "dimension" },
        },
      },
    };
  };

  const handleSaveCreate = async () => {
    if (!formName.trim() || !formSlug.trim()) {
      toast({ title: "خطا", description: "نام و نامک تم الزامی است.", variant: "destructive" });
      return;
    }

    setSubmitting(true);
    try {
      const tokens = buildTokensPayload();

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
      const updatedTokens = buildTokensPayload(editTheme.tokens);

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
      description: "آیا از بازگردانی توکن‌های تم به این نسخه اطمینان دارید؟ تغییرات فعلی به عنوان نسخه جدید ثبت خواهند شد.",
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
      description: `آیا از حذف تم «${theme.name}» اطمینان دارید؟ این عمل غیرقابل‌بازگشت است.`,
      destructive: true,
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
                    aria-label={`تاریخچه نسخه‌های تم ${theme.name}`}
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
                    aria-label={`کلون تم ${theme.name}`}
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
                      aria-label={`حذف تم ${theme.name}`}
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

      {/* Create / Edit Dialog with Full Token Groups & Live Component Preview */}
      <Dialog open={createOpen || Boolean(editTheme)} onOpenChange={(open) => {
        if (!open) {
          setCreateOpen(false);
          setEditTheme(null);
        }
      }}>
        <DialogContent className="max-w-4xl max-h-[90vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-base font-bold">
              <Paintbrush className="w-4 h-4 text-primary" />
              <span>{editTheme ? `ویرایش توکن‌های تم «${editTheme.name}»` : "ایجاد تم جدید"}</span>
            </DialogTitle>
          </DialogHeader>

          {/* Basic metadata */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 py-1 border-b pb-3">
            <div className="space-y-1">
              <Label className="text-xs">نام تم</Label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                className="h-8 text-xs"
                placeholder="مثلاً: تم سازمانی نیلی"
              />
            </div>
            {!editTheme ? (
              <div className="space-y-1">
                <Label className="text-xs">نامک تم (Slug)</Label>
                <Input
                  value={formSlug}
                  onChange={(e) => setFormSlug(e.target.value)}
                  className="h-8 text-xs font-mono"
                  dir="ltr"
                  placeholder="corporate-indigo"
                />
              </div>
            ) : (
              <div className="space-y-1">
                <Label className="text-xs text-muted-foreground">نامک (غیرقابل تغییر)</Label>
                <Input value={editTheme.slug} disabled className="h-8 text-xs font-mono bg-muted" dir="ltr" />
              </div>
            )}
            <div className="space-y-1">
              <Label className="text-xs">توضیحات تم</Label>
              <Input
                value={formDesc}
                onChange={(e) => setFormDesc(e.target.value)}
                className="h-8 text-xs"
                placeholder="توضیح کوتاه کاربرد تم"
              />
            </div>
          </div>

          {/* Sub-tabs: Colors, Typography & Dimensions, Live Preview */}
          <Tabs value={modalTab} onValueChange={(val: any) => setModalTab(val)} className="w-full">
            <TabsList className="grid grid-cols-3 w-full h-9 mb-3">
              <TabsTrigger value="colors" className="text-xs flex items-center gap-1.5">
                <Palette className="w-3.5 h-3.5" />
                <span>پالت رنگ‌های سازمانی</span>
              </TabsTrigger>
              <TabsTrigger value="typography" className="text-xs flex items-center gap-1.5">
                <Type className="w-3.5 h-3.5" />
                <span>تایپوگرافی، کادر و سایه</span>
              </TabsTrigger>
              <TabsTrigger value="preview" className="text-xs flex items-center gap-1.5 text-primary font-bold">
                <Eye className="w-3.5 h-3.5" />
                <span>پیش‌نمایش زنده کامپوننت‌ها</span>
              </TabsTrigger>
            </TabsList>

            {/* TAB 1: Colors */}
            <TabsContent value="colors" className="space-y-4 py-1">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Brand Colors */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Sparkles className="w-3.5 h-3.5 text-primary" />
                    <span>رنگ‌های اصلی برند (Brand Scale)</span>
                  </h4>

                  {/* Primary */}
                  <div className="space-y-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold">رنگ اصلی (Primary)</span>
                      <span className="font-mono text-muted-foreground text-[11px]">{formPrimary}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={toValidHexColor(formPrimary, "#059669")}
                        onChange={(e) => setFormPrimary(e.target.value)}
                        className="w-7 h-7 rounded cursor-pointer border"
                      />
                      <Input
                        value={formPrimary}
                        onChange={(e) => setFormPrimary(e.target.value)}
                        className="h-7 text-xs font-mono"
                        dir="ltr"
                      />
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {COLOR_PRESETS.map((c) => (
                        <button
                          key={c.hex}
                          type="button"
                          onClick={() => setFormPrimary(c.hex)}
                          className="w-4 h-4 rounded-full border shadow-2xs transition hover:scale-110 flex items-center justify-center"
                          style={{ backgroundColor: c.hex }}
                          title={c.name}
                        >
                          {formPrimary.toLowerCase() === c.hex.toLowerCase() && (
                            <Check className="w-2.5 h-2.5 text-white" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>

                  {/* Secondary */}
                  <div className="space-y-1 pt-1">
                    <div className="flex items-center justify-between text-xs">
                      <span className="font-semibold">رنگ مکمل / ثانویه (Secondary)</span>
                      <span className="font-mono text-muted-foreground text-[11px]">{formSecondary}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="color"
                        value={toValidHexColor(formSecondary, "#0d9488")}
                        onChange={(e) => setFormSecondary(e.target.value)}
                        className="w-7 h-7 rounded cursor-pointer border"
                      />
                      <Input
                        value={formSecondary}
                        onChange={(e) => setFormSecondary(e.target.value)}
                        className="h-7 text-xs font-mono"
                        dir="ltr"
                      />
                    </div>
                  </div>
                </div>

                {/* Surface & Background Colors */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-primary" />
                    <span>سطوح و پس‌زمینه (Surface & Muted)</span>
                  </h4>

                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div>
                      <Label className="text-[11px]">پس‌زمینه (Background)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formBackground, "#ffffff")}
                          onChange={(e) => setFormBackground(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formBackground}
                          onChange={(e) => setFormBackground(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px]">متن اصلی (Foreground)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formForeground, "#09090b")}
                          onChange={(e) => setFormForeground(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formForeground}
                          onChange={(e) => setFormForeground(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px]">سطح کارت (Surface)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formSurface, "#f8fafc")}
                          onChange={(e) => setFormSurface(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formSurface}
                          onChange={(e) => setFormSurface(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px]">خطوط کادر (Border)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formBorder, "#e2e8f0")}
                          onChange={(e) => setFormBorder(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formBorder}
                          onChange={(e) => setFormBorder(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* Status / Feedback Colors */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3 md:col-span-2">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <CheckCircle2 className="w-3.5 h-3.5 text-primary" />
                    <span>رنگ‌های وضعیت و بازخورد (Status Colors)</span>
                  </h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
                    <div>
                      <Label className="text-[11px] text-green-600 font-semibold">موفقیت (Success)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formSuccess, "#16a34a")}
                          onChange={(e) => setFormSuccess(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formSuccess}
                          onChange={(e) => setFormSuccess(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px] text-amber-600 font-semibold">هشدار (Warning)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formWarning, "#f59e0b")}
                          onChange={(e) => setFormWarning(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formWarning}
                          onChange={(e) => setFormWarning(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px] text-rose-600 font-semibold">خطا (Destructive)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formDestructive, "#e11d48")}
                          onChange={(e) => setFormDestructive(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formDestructive}
                          onChange={(e) => setFormDestructive(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                    <div>
                      <Label className="text-[11px] text-blue-600 font-semibold">اطلاعیه (Info)</Label>
                      <div className="flex items-center gap-1.5 mt-1">
                        <input
                          type="color"
                          value={toValidHexColor(formInfo, "#2563eb")}
                          onChange={(e) => setFormInfo(e.target.value)}
                          className="w-6 h-6 rounded cursor-pointer border"
                        />
                        <Input
                          value={formInfo}
                          onChange={(e) => setFormInfo(e.target.value)}
                          className="h-7 text-xs font-mono"
                          dir="ltr"
                        />
                      </div>
                    </div>
                  </div>
                </div>

                {/* WCAG 2.1 AA Contrast Ratio Card */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-2.5 md:col-span-2">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                      <Sparkles className="w-3.5 h-3.5 text-primary" />
                      <span>اعتبارسنجی دسترس‌پذیری کنتراست رنگ (WCAG 2.1 AA)</span>
                    </h4>
                    <span className="text-[10px] text-muted-foreground">حداقل استاندارد: ۴.۵:۱</span>
                  </div>

                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5 text-xs">
                    {/* Text vs Background */}
                    <div className="p-2.5 rounded-lg border bg-background space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-foreground">متن روی پس‌زمینه</span>
                        {textBgContrast?.isNormalTextAA ? (
                          <Badge className="bg-emerald-600 text-white text-[9px] px-1.5 py-0">تأیید AA</Badge>
                        ) : (
                          <Badge variant="destructive" className="text-[9px] px-1.5 py-0">کنتراست ضعیف</Badge>
                        )}
                      </div>
                      <div className="flex items-baseline justify-between text-[11px] text-muted-foreground font-mono">
                        <span>نسبت کنتراست:</span>
                        <span className={textBgContrast?.isNormalTextAA ? "text-emerald-600 font-bold" : "text-destructive font-bold"}>
                          {textBgContrast ? `${textBgContrast.ratio}:1` : "نامعتبر"}
                        </span>
                      </div>
                    </div>

                    {/* Text vs Surface */}
                    <div className="p-2.5 rounded-lg border bg-background space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-foreground">متن روی کارت/سطح</span>
                        {textSurfaceContrast?.isNormalTextAA ? (
                          <Badge className="bg-emerald-600 text-white text-[9px] px-1.5 py-0">تأیید AA</Badge>
                        ) : (
                          <Badge variant="destructive" className="text-[9px] px-1.5 py-0">کنتراست ضعیف</Badge>
                        )}
                      </div>
                      <div className="flex items-baseline justify-between text-[11px] text-muted-foreground font-mono">
                        <span>نسبت کنتراست:</span>
                        <span className={textSurfaceContrast?.isNormalTextAA ? "text-emerald-600 font-bold" : "text-destructive font-bold"}>
                          {textSurfaceContrast ? `${textSurfaceContrast.ratio}:1` : "نامعتبر"}
                        </span>
                      </div>
                    </div>

                    {/* Primary Button text vs Primary color */}
                    <div className="p-2.5 rounded-lg border bg-background space-y-1">
                      <div className="flex items-center justify-between">
                        <span className="text-[11px] font-semibold text-foreground">متن سفید روی دکمه اصلی</span>
                        {primaryBtnContrast?.isLargeTextAA ? (
                          <Badge className="bg-emerald-600 text-white text-[9px] px-1.5 py-0">تأیید AA</Badge>
                        ) : (
                          <Badge variant="destructive" className="text-[9px] px-1.5 py-0">کنتراست ضعیف</Badge>
                        )}
                      </div>
                      <div className="flex items-baseline justify-between text-[11px] text-muted-foreground font-mono">
                        <span>نسبت کنتراست:</span>
                        <span className={primaryBtnContrast?.isLargeTextAA ? "text-emerald-600 font-bold" : "text-destructive font-bold"}>
                          {primaryBtnContrast ? `${primaryBtnContrast.ratio}:1` : "نامعتبر"}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* TAB 2: Typography & Dimensions */}
            <TabsContent value="typography" className="space-y-4 py-1">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Typography Settings */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Type className="w-3.5 h-3.5 text-primary" />
                    <span>تایپوگرافی و فونت</span>
                  </h4>

                  <div className="space-y-2 text-xs">
                    <div className="space-y-1">
                      <Label className="text-[11px]">خانواده فونت سراسری</Label>
                      <Select value={formFont} onValueChange={setFormFont}>
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="vazirmatn">فونت وزیرمتن (Vazirmatn استاندارد RTL)</SelectItem>
                          <SelectItem value="system-ui">فونت سیستمی (System UI)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>

                    <div className="space-y-1">
                      <Label className="text-[11px]">اندازه متن پایه (Base Font Size)</Label>
                      <Select value={formFontSize} onValueChange={setFormFontSize}>
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="14px">14px (فشرده)</SelectItem>
                          <SelectItem value="15px">15px (استاندارد وب فارسی)</SelectItem>
                          <SelectItem value="16px">16px (درشت و خوانا)</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                {/* Dimensions & Shadows */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Box className="w-3.5 h-3.5 text-primary" />
                    <span>شعاع کادر و سایه‌ها (Radius & Shadow)</span>
                  </h4>

                  <div className="space-y-2 text-xs">
                    <div className="space-y-1">
                      <Label className="text-[11px]">شعاع گردی پیش‌فرض (Border Radius)</Label>
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

                    <div className="space-y-1">
                      <Label className="text-[11px]">سطح سایه جعبه‌ای (Box Shadow)</Label>
                      <Select value={formShadow} onValueChange={setFormShadow}>
                        <SelectTrigger className="h-8 text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {SHADOW_OPTIONS.map((s) => (
                            <SelectItem key={s.value} value={s.value}>
                              {s.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>

                {/* Spacing & Layout Tokens (Phase P2 Master Roadmap) */}
                <div className="p-3.5 rounded-xl border bg-muted/20 space-y-3 md:col-span-2">
                  <h4 className="text-xs font-bold text-foreground flex items-center gap-1.5">
                    <Layers className="w-3.5 h-3.5 text-primary" />
                    <span>توکن‌های چیدمان و فاصله‌گذاری (Layout & Spacing Tokens)</span>
                  </h4>

                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
                    <div className="space-y-1">
                      <Label className="text-[11px]">حداکثر عرض کانتینر</Label>
                      <Input
                        value={formContainerWidth}
                        onChange={(e) => setFormContainerWidth(e.target.value)}
                        className="h-8 text-xs font-mono"
                        dir="ltr"
                        placeholder="1280px"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[11px]">عرض متن خوانا (Content)</Label>
                      <Input
                        value={formContentWidth}
                        onChange={(e) => setFormContentWidth(e.target.value)}
                        className="h-8 text-xs font-mono"
                        dir="ltr"
                        placeholder="768px"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[11px]">فاصله عمودی سکشن‌ها</Label>
                      <Input
                        value={formSectionSpacing}
                        onChange={(e) => setFormSectionSpacing(e.target.value)}
                        className="h-8 text-xs font-mono"
                        dir="ltr"
                        placeholder="64px"
                      />
                    </div>
                    <div className="space-y-1">
                      <Label className="text-[11px]">مقیاس فاصله پایه (Scale)</Label>
                      <Input
                        value={formSpacingScale}
                        onChange={(e) => setFormSpacingScale(e.target.value)}
                        className="h-8 text-xs font-mono"
                        dir="ltr"
                        placeholder="16px"
                      />
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            {/* TAB 3: Live Component Preview */}
            <TabsContent value="preview" className="space-y-4 py-1">
              <div
                className="p-5 rounded-2xl border space-y-5 transition-all"
                style={{
                  backgroundColor: formBackground,
                  color: formForeground,
                  fontFamily: formFont === "system-ui" ? "system-ui, sans-serif" : "var(--font-vazirmatn, system-ui, sans-serif)",
                }}
              >
                <div className="border-b pb-3">
                  <h3 className="text-sm font-bold flex items-center gap-2">
                    <span>پیش‌نمایش زنده کامپوننت‌های رابط کاربری با توکن‌های انتخابی</span>
                  </h3>
                  <p className="text-xs opacity-75 mt-0.5">
                    این پیش‌نمایش نحوه اعمال بی‌درنگ رنگ‌ها، شعاع گردی و سایه‌ها روی عناصر سایت را نشان می‌دهد.
                  </p>
                </div>

                {/* 1. Buttons Preview */}
                <div className="space-y-2">
                  <span className="text-xs font-bold block">دکمه‌ها (Buttons):</span>
                  <div className="flex flex-wrap items-center gap-2.5">
                    <button
                      type="button"
                      style={{
                        backgroundColor: formPrimary,
                        color: "#ffffff",
                        borderRadius: formRadius,
                        boxShadow: formShadow !== "none" ? formShadow : undefined,
                      }}
                      className="px-4 py-2 text-xs font-bold transition hover:opacity-90"
                    >
                      دکمه اصلی (Primary)
                    </button>

                    <button
                      type="button"
                      style={{
                        backgroundColor: formSecondary,
                        color: "#ffffff",
                        borderRadius: formRadius,
                      }}
                      className="px-4 py-2 text-xs font-semibold transition hover:opacity-90"
                    >
                      دکمه ثانویه (Secondary)
                    </button>

                    <button
                      type="button"
                      style={{
                        backgroundColor: "transparent",
                        borderColor: formBorder,
                        borderWidth: "1px",
                        borderStyle: "solid",
                        color: formForeground,
                        borderRadius: formRadius,
                      }}
                      className="px-4 py-2 text-xs font-medium transition hover:bg-black/5"
                    >
                      دکمه دورخط (Outline)
                    </button>

                    <button
                      type="button"
                      style={{
                        backgroundColor: formDestructive,
                        color: "#ffffff",
                        borderRadius: formRadius,
                      }}
                      className="px-4 py-2 text-xs font-bold transition hover:opacity-90"
                    >
                      دکمه هشدار (Destructive)
                    </button>
                  </div>
                </div>

                {/* 2. Card Preview */}
                <div className="space-y-2">
                  <span className="text-xs font-bold block">کارت محصول و سطوح (Cards & Surfaces):</span>
                  <div
                    className="p-4 border transition-all max-w-md"
                    style={{
                      backgroundColor: formSurface,
                      borderColor: formBorder,
                      borderRadius: formRadius,
                      boxShadow: formShadow !== "none" ? formShadow : undefined,
                    }}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-bold text-sm">کفش ورزشی سبک رانینگ</span>
                      <span
                        className="px-2 py-0.5 text-[10px] font-bold rounded-full"
                        style={{
                          backgroundColor: formSuccess + "20",
                          color: formSuccess,
                        }}
                      >
                        موجود در انبار
                      </span>
                    </div>
                    <p className="text-xs opacity-80 leading-relaxed mb-3">
                      طراحی ارگونومیک با گردش هوای عالی، کفی طبی چندلایه و مناسب برای پیاده‌روی طولانی.
                    </p>
                    <div className="flex items-center justify-between pt-2 border-t" style={{ borderColor: formBorder }}>
                      <span className="font-bold text-sm font-mono num-fa" style={{ color: formPrimary }}>
                        ۲۵۰,۰۰۰ تومان
                      </span>
                      <button
                        type="button"
                        style={{
                          backgroundColor: formPrimary,
                          color: "#ffffff",
                          borderRadius: formRadius,
                        }}
                        className="px-3 py-1.5 text-xs font-bold"
                      >
                        افزودن به سبد
                      </button>
                    </div>
                  </div>
                </div>

                {/* 3. Form Controls Preview */}
                <div className="space-y-2">
                  <span className="text-xs font-bold block">کنترل‌های فرم (Form Inputs):</span>
                  <div className="flex flex-col sm:flex-row items-center gap-3 max-w-md">
                    <input
                      type="text"
                      placeholder="آدرس ایمیل خود را وارد کنید..."
                      style={{
                        borderColor: formBorder,
                        borderWidth: "1px",
                        borderRadius: formRadius,
                        backgroundColor: formBackground,
                        color: formForeground,
                      }}
                      className="h-8 px-3 text-xs w-full focus:outline-hidden"
                    />
                    <button
                      type="button"
                      style={{
                        backgroundColor: formPrimary,
                        color: "#ffffff",
                        borderRadius: formRadius,
                      }}
                      className="h-8 px-4 text-xs font-bold shrink-0"
                    >
                      عضویت
                    </button>
                  </div>
                </div>

                {/* 4. Badges Preview */}
                <div className="space-y-2">
                  <span className="text-xs font-bold block">نشان‌های وضعیت (Status Badges):</span>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className="px-2.5 py-1 text-xs font-bold rounded-md"
                      style={{ backgroundColor: formSuccess, color: "#ffffff" }}
                    >
                      تأیید شده
                    </span>
                    <span
                      className="px-2.5 py-1 text-xs font-bold rounded-md"
                      style={{ backgroundColor: formWarning, color: "#ffffff" }}
                    >
                      در انتظار پرداخت
                    </span>
                    <span
                      className="px-2.5 py-1 text-xs font-bold rounded-md"
                      style={{ backgroundColor: formDestructive, color: "#ffffff" }}
                    >
                      لغو سفارش
                    </span>
                    <span
                      className="px-2.5 py-1 text-xs font-bold rounded-md"
                      style={{ backgroundColor: formInfo, color: "#ffffff" }}
                    >
                      اطلاعیه سیستم
                    </span>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <DialogFooter className="flex items-center justify-between gap-2 pt-3 border-t">
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
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setModalTab(modalTab === "preview" ? "colors" : "preview")}
                className="text-xs text-primary"
              >
                {modalTab === "preview" ? "بازگشت به تنظیمات" : "مشاهده پیش‌نمایش زنده"}
              </Button>
              <Button size="sm" onClick={editTheme ? handleSaveEdit : handleSaveCreate} disabled={submitting}>
                {submitting ? "در حال ثبت..." : editTheme ? "ثبت ویرایش و ساخت نسخه جدید" : "ایجاد تم"}
              </Button>
            </div>
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
                    className="p-3 rounded-xl border bg-card flex items-center justify-between gap-3 shadow-2xs"
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
        </DialogContent>
      </Dialog>
    </div>
  );
}
