"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Layout, RefreshCw, Plus, Menu, HelpCircle, Trash2, ChevronUp, ChevronDown, ArrowUp, ArrowDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
import ReusableBlocksCard from "@/components/admin/reusable-blocks-card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";
import {
  singleTypesAdminApi,
  singleTypesApi,
  type HomepageConfig,
  type HeaderMenuConfig,
} from "@/lib/api/content";
import { Settings2, Megaphone, MousePointerClick, Monitor, Palette } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  contentApi,
  contentAdminApi,
  cmsPagesAdminApi,
  type MenuItem,
} from "@/lib/api/content";
import { blogAdminApi } from "@/lib/api/blog";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";

const CMS_CONTENT_QUERY_KEY = "admin-cms-content" as const;
const CMS_MENU_QUERY_KEY = "admin-cms-menu" as const;

const MENU_LOCATIONS = [
  { value: "header_main", label: "هدر اصلی" },
  { value: "header_top", label: "نوار بالای هدر" },
  { value: "footer_col1", label: "فوتر ستون ۱" },
  { value: "footer_col2", label: "فوتر ستون ۲" },
  { value: "mobile_nav", label: "منوی موبایل" },
] as const;

interface HomepageBlock {
  id: string;
  title: string;
  block_type: string;
  config: Record<string, unknown> | null;
  position: number;
  is_active: boolean;
}

interface FAQItem {
  id: string;
  question: string;
  answer_html: string;
  category: string;
  position: number;
  is_active: boolean;
}

export default function AdminCMSPage() {
  const { toast } = useToast();

  // Block create/edit
  const [blockOpen, setBlockOpen] = useState(false);
  const [editingBlock, setEditingBlock] = useState<HomepageBlock | null>(null);
  const [blockTitle, setBlockTitle] = useState("");
  const [blockType, setBlockType] = useState<HomepageBlock["block_type"]>("html_custom");
  const [blockConfig, setBlockConfig] = useState("{}");
  const [blockSaving, setBlockSaving] = useState(false);

  // FAQ create/edit
  const [faqOpen, setFaqOpen] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState("");
  const [faqAnswer, setFaqAnswer] = useState("");
  const [faqCategory, setFaqCategory] = useState("عمومی");
  const [editingFaq, setEditingFaq] = useState<FAQItem | null>(null);
  const [creating, setCreating] = useState(false);

  // Blocks and FAQs load together but fail independently: the old code used
  // Promise.allSettled and kept whichever half succeeded, so a FAQ outage
  // still showed the blocks list. One query keeps that — a throw here would
  // blank both halves.
  const {
    data: cmsData,
    loading,
    reload: fetchData,
  } = useAdminQuery({
    queryKey: [CMS_CONTENT_QUERY_KEY],
    queryFn: async () => {
      const [blocksRes, faqsRes] = await Promise.allSettled([
        // Admin list: includes inactive blocks so they can be re-enabled.
        apiClient.get("/content/admin/blocks"),
        apiClient.get("/content/faqs"),
      ]);
      return {
        blocks:
          blocksRes.status === "fulfilled" && Array.isArray(blocksRes.value.data)
            ? (blocksRes.value.data as HomepageBlock[])
            : [],
        faqs:
          faqsRes.status === "fulfilled" && Array.isArray(faqsRes.value.data?.items)
            ? (faqsRes.value.data.items as FAQItem[])
            : [],
      };
    },
    fallbackError: "بارگذاری CMS با خطا مواجه شد",
  });
  const blocks: HomepageBlock[] = cmsData?.blocks ?? [];
  const faqs: FAQItem[] = cmsData?.faqs ?? [];
  const runMutation = useAdminMutation();

  const openCreateFaq = () => {
    setEditingFaq(null);
    setFaqQuestion("");
    setFaqAnswer("");
    setFaqCategory("عمومی");
    setFaqOpen(true);
  };

  const openEditFaq = (f: FAQItem) => {
    setEditingFaq(f);
    setFaqQuestion(f.question);
    setFaqAnswer(f.answer_html);
    setFaqCategory(f.category);
    setFaqOpen(true);
  };

  const createFAQ = async () => {
    if (!faqQuestion.trim() || !faqAnswer.trim()) {
      toast({ title: "خطا", description: "سوال و پاسخ الزامی است", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      if (editingFaq) {
        await apiClient.patch(`/content/admin/faqs/${editingFaq.id}`, {
          question: faqQuestion,
          answer_html: faqAnswer,
          category: faqCategory,
        });
        toast({ title: "موفق", description: "سوال به‌روزرسانی شد" });
      } else {
        await apiClient.post("/content/admin/faqs", {
          question: faqQuestion,
          answer_html: faqAnswer,
          category: faqCategory,
        });
        toast({ title: "موفق", description: "سوال جدید اضافه شد" });
      }
      setFaqOpen(false);
      fetchData();
    } catch {
      toast({ title: "خطا", description: "ذخیره سوال با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const deleteFaq = async (f: FAQItem) => {
    if (!confirm(`سوال «${f.question}» حذف شود؟`)) return;
    try {
      await apiClient.delete(`/content/admin/faqs/${f.id}`);
      fetchData();
    } catch {
      toast({ title: "خطا", description: "حذف سوال ناموفق بود", variant: "destructive" });
    }
  };

  const toggleFaq = async (f: FAQItem) => {
    try {
      await apiClient.patch(`/content/admin/faqs/${f.id}`, { is_active: !f.is_active });
      fetchData();
    } catch {
      toast({ title: "خطا", description: "تغییر وضعیت ناموفق بود", variant: "destructive" });
    }
  };


  const openCreateBlock = () => {
    setEditingBlock(null);
    setBlockTitle("");
    setBlockType("html_custom");
    setBlockConfig("{}");
    setBlockOpen(true);
  };

  const openEditBlock = (b: HomepageBlock) => {
    setEditingBlock(b);
    setBlockTitle(b.title);
    setBlockType(b.block_type);
    setBlockConfig(JSON.stringify(b.config ?? {}, null, 2));
    setBlockOpen(true);
  };

  const saveBlock = async () => {
    if (!blockTitle.trim()) {
      toast({ title: "خطا", description: "عنوان بلوک الزامی است", variant: "destructive" });
      return;
    }
    let config: Record<string, unknown> | null = null;
    try {
      config = blockConfig.trim() ? JSON.parse(blockConfig) : null;
    } catch {
      toast({ title: "خطا", description: "پیکربندی JSON معتبر نیست", variant: "destructive" });
      return;
    }
    setBlockSaving(true);
    try {
      if (editingBlock) {
        await apiClient.patch(`/content/admin/blocks/${editingBlock.id}`, {
          title: blockTitle.trim(),
          config,
        });
        toast({ title: "موفق", description: "بلوک به‌روزرسانی شد" });
      } else {
        await apiClient.post("/content/admin/blocks", {
          title: blockTitle.trim(),
          block_type: blockType,
          config,
        });
        toast({ title: "موفق", description: "بلوک جدید ساخته شد" });
      }
      setBlockOpen(false);
      fetchData();
    } catch {
      toast({ title: "خطا", description: "ذخیره بلوک ناموفق بود", variant: "destructive" });
    } finally {
      setBlockSaving(false);
    }
  };

  const toggleBlock = async (b: HomepageBlock) => {
    try {
      await apiClient.patch(`/content/admin/blocks/${b.id}`, { is_active: !b.is_active });
      fetchData();
    } catch {
      toast({ title: "خطا", description: "تغییر وضعیت بلوک ناموفق بود", variant: "destructive" });
    }
  };

  const moveBlock = async (b: HomepageBlock, delta: number) => {
    try {
      await apiClient.patch(`/content/admin/blocks/${b.id}`, { position: b.position + delta });
      fetchData();
    } catch {
      toast({ title: "خطا", description: "جابه‌جایی بلوک ناموفق بود", variant: "destructive" });
    }
  };

  const deleteBlock = async (b: HomepageBlock) => {
    if (!confirm(`بلوک «${b.title}» حذف شود؟`)) return;
    try {
      await apiClient.delete(`/content/admin/blocks/${b.id}`);
      fetchData();
    } catch {
      toast({ title: "خطا", description: "حذف بلوک ناموفق بود", variant: "destructive" });
    }
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <Layout className="h-5 w-5 text-primary" />
            مدیریت محتوا و CMS
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            چیدمان بلوک‌های صفحه اصلی، منوساز درختی و سوالات متداول
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchData}>
          <RefreshCw className="h-4 w-4 ms-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Single Types (Strapi-style) */}
          <SingleTypesCard />

          {/* Homepage Blocks */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">بلوک‌های صفحه اصلی</h3>
              <Button size="sm" variant="outline" onClick={openCreateBlock}>
                <Plus className="h-4 w-4 ms-1" />
                بلوک جدید
              </Button>
            </div>
            {blocks.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                هنوز هیچ بلوکی تعریف نشده است
              </p>
            ) : (
              <div className="space-y-2">
                {blocks.map((b) => (
                  <div key={b.id} className={`flex items-center justify-between rounded-lg border p-3 ${!b.is_active ? "opacity-50" : ""}`}>
                    <div>
                      <p className="font-medium text-sm">{b.title}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">{b.block_type}</Badge>
                        <span className="text-[10px] text-muted-foreground">ترتیب {b.position}</span>
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button size="sm" variant="ghost" className="h-7 px-1.5" onClick={() => moveBlock(b, -1)} title="بالا" disabled={b.position <= 0}>
                        <ArrowUp className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-1.5" onClick={() => moveBlock(b, 1)} title="پایین">
                        <ArrowDown className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-1.5" onClick={() => toggleBlock(b)} title={b.is_active ? "غیرفعال" : "فعال"}>
                        {b.is_active ? "خاموش" : "روشن"}
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-1.5" onClick={() => openEditBlock(b)} title="ویرایش">
                        ویرایش
                      </Button>
                      <Button size="sm" variant="ghost" className="h-7 px-1.5 text-destructive" onClick={() => deleteBlock(b)} title="حذف">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Menu Builder */}
          <MenuBuilderCard />

          {/* Reusable blocks (synced patterns) */}
          <ReusableBlocksCard />

          {/* FAQs */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                سوالات متداول
              </h3>
              <Button size="sm" variant="outline" onClick={openCreateFaq}>
                <Plus className="h-4 w-4 ms-1" />
                افزودن
              </Button>
            </div>
            {faqs.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                هنوز هیچ سوالی تعریف نشده است
              </p>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {faqs.map((f) => (
                  <div key={f.id} className={`rounded-lg border p-3 ${!f.is_active ? "opacity-50" : ""}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="font-medium text-sm">{f.question}</p>
                        <Badge variant="outline" className="text-xs mt-1">{f.category}</Badge>
                      </div>
                      <div className="flex shrink-0 gap-1">
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => toggleFaq(f)}>
                          {f.is_active ? "غیرفعال" : "فعال"}
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs" onClick={() => openEditFaq(f)}>
                          ویرایش
                        </Button>
                        <Button size="sm" variant="ghost" className="h-7 px-2 text-destructive" onClick={() => deleteFaq(f)}>
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* Block Create/Edit Dialog */}
      <Dialog open={blockOpen} onOpenChange={setBlockOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingBlock ? "ویرایش بلوک" : "بلوک جدید"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>عنوان</Label>
              <Input value={blockTitle} onChange={(e) => setBlockTitle(e.target.value)} placeholder="بنر اصلی" />
            </div>
            <div className="space-y-2">
              <Label>نوع بلوک</Label>
              <Select value={blockType} onValueChange={(v) => setBlockType(v as HomepageBlock["block_type"])} disabled={!!editingBlock}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="slider">اسلایدر</SelectItem>
                  <SelectItem value="category_grid">شبکه دسته‌بندی</SelectItem>
                  <SelectItem value="featured_products">محصولات ویژه</SelectItem>
                  <SelectItem value="discount_carousel">کاروسل تخفیف</SelectItem>
                  <SelectItem value="banner_grid">شبکه بنر</SelectItem>
                  <SelectItem value="html_custom">HTML سفارشی</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>پیکربندی (JSON)</Label>
              <Textarea dir="ltr" rows={6} className="font-mono text-xs text-left" value={blockConfig} onChange={(e) => setBlockConfig(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBlockOpen(false)}>انصراف</Button>
            <Button onClick={saveBlock} disabled={blockSaving}>
              {blockSaving ? "در حال ذخیره..." : editingBlock ? "به‌روزرسانی" : "ایجاد"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* FAQ Create Dialog */}
      <Dialog open={faqOpen} onOpenChange={setFaqOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingFaq ? "ویرایش سوال متداول" : "افزودن سوال متداول"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>سوال</Label>
              <Input value={faqQuestion} onChange={(e) => setFaqQuestion(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>پاسخ</Label>
              <RichBodyEditor value={faqAnswer} onChange={setFaqAnswer} />
            </div>
            <div className="space-y-2">
              <Label>دسته‌بندی</Label>
              <Input value={faqCategory} onChange={(e) => setFaqCategory(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFaqOpen(false)}>انصراف</Button>
            <Button onClick={createFAQ} disabled={creating}>
              {creating ? "در حال ذخیره..." : editingFaq ? "به‌روزرسانی" : "افزودن"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}


/** ویرایشگر توکن‌های تم (single type "theme") — رنگ‌ها با اعتبارسنجی hex در سرور. */
function ThemeEditor() {
  const { toast } = useToast();
  const [colors, setColors] = useState<Record<string, string> | null>(null);
  const [saving, setSaving] = useState(false);
  const iframeRef = React.useRef<HTMLIFrameElement>(null);

  const COLOR_KEYS = ["primary", "secondary", "accent", "background", "surface", "text", "muted"] as const;
  const COLOR_LABELS: Record<string, string> = {
    primary: "اصلی", secondary: "ثانویه", accent: "تأکیدی", background: "پس‌زمینه",
    surface: "سطح", text: "متن", muted: "محو",
  };

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await singleTypesApi.getTheme();
        if (mounted) setColors(res.value?.colors ?? null);
      } catch {
        // theme single type optional
      }
    })();
    return () => { mounted = false; };
  }, []);

  // Live preview: stream the current colors into the storefront iframe
  // (ThemePreviewBridge applies them as CSS vars). Debounced so dragging a
  // color picker doesn't post on every pixel; the iframe never reloads.
  //
  // "load" of the iframe races the first postMessage: the bridge listener
  // mounts after hydration, so early messages are lost. Re-posting on the
  // iframe's onLoad (below) covers the first paint; the effect covers edits.
  useEffect(() => {
    if (!colors) return;
    const t = setTimeout(() => {
      iframeRef.current?.contentWindow?.postMessage(
        { type: "theme-preview", tokens: { colors } },
        window.location.origin,
      );
    }, 250);
    return () => clearTimeout(t);
  }, [colors]);

  const save = async () => {
    if (!colors) return;
    setSaving(true);
    try {
      const current = await singleTypesApi.getTheme();
      const next = { ...(current.value ?? { name: "default" }), colors };
      await singleTypesAdminApi.upsert("theme", next);
      toast({ title: "تم ذخیره شد", description: "رنگ‌ها بدون دیپلوی روی فروشگاه اعمال می‌شوند" });
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast({ title: "خطا", description: detail ?? "رنگ باید در قالب #RRGGBB باشد", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  if (!colors) return null;

  return (
    <div className="space-y-3 mb-4">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Palette className="h-4 w-4 text-primary" />
        رنگ‌های تم
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {COLOR_KEYS.map((k) => (
          <div key={k} className="space-y-1">
            <label className="text-xs text-muted-foreground">{COLOR_LABELS[k]}</label>
            <div className="flex items-center gap-1">
              <input
                type="color"
                value={colors[k] ?? "#000000"}
                onChange={(e) => setColors({ ...colors, [k]: e.target.value })}
                className="h-8 w-8 cursor-pointer rounded border border-input bg-transparent"
              />
              <Input
                dir="ltr"
                value={colors[k] ?? ""}
                onChange={(e) => setColors({ ...colors, [k]: e.target.value })}
                className="h-8 font-mono text-xs"
              />
            </div>
          </div>
        ))}
      </div>
      <Button size="sm" variant="outline" onClick={save} disabled={saving}>
        {saving ? "در حال ذخیره..." : "ذخیره تم"}
      </Button>

      {/* Live storefront preview — same-origin iframe; the postMessage above
          recolors it without a reload (WordPress customizer parity). */}
      <div className="overflow-hidden rounded-lg border border-border">
        <div className="flex items-center gap-2 border-b border-border bg-muted/40 px-3 py-1.5 text-[11px] text-muted-foreground">
          <Monitor className="h-3.5 w-3.5" />
          پیش‌نمایش زنده فروشگاه
        </div>
        <iframe
          ref={iframeRef}
          src="/"
          title="پیش‌نمایش زنده فروشگاه"
          className="h-[420px] w-full border-0 bg-background"
          onLoad={() => {
            // Re-apply on (re)load: hydration finished by the time this
            // fires, so the bridge listener is guaranteed to exist.
            if (colors) {
              iframeRef.current?.contentWindow?.postMessage(
                { type: "theme-preview", tokens: { colors } },
                window.location.origin,
              );
            }
          }}
        />
      </div>
    </div>
  );
}

/** تایپ‌های تکی (Strapi-style): پیکربندی صفحه اصلی و هدر. */
function SingleTypesCard() {
  const { toast } = useToast();
  const [hp, setHp] = useState<HomepageConfig | null>(null);
  const [hm, setHm] = useState<HeaderMenuConfig | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const [hpRes, hmRes] = await Promise.all([
          singleTypesApi.getHomepageConfig(),
          singleTypesApi.getHeaderMenu(),
        ]);
        if (!mounted) return;
        setHp(hpRes.value);
        setHm(hmRes.value);
      } catch {
        // بدون اخلال در بقیه صفحه — تایپ‌های تکی اختیاری‌اند
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const toggleAnnouncement = async () => {
    if (!hp) return;
    setSaving(true);
    try {
      const next: HomepageConfig = {
        ...hp,
        announcement_bar: { ...hp.announcement_bar, enabled: !hp.announcement_bar.enabled },
      };
      const res = await singleTypesAdminApi.upsert<HomepageConfig>("homepage_config", next);
      setHp(res.value);
      toast({
        title: "ذخیره شد",
        description: next.announcement_bar.enabled
          ? "نوار اطلاع‌رسانی فعال شد"
          : "نوار اطلاع‌رسانی غیرفعال شد",
      });
    } catch {
      toast({ title: "خطا", description: "ذخیره پیکربندی با خطا مواجه شد", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const toggleHeaderCta = async () => {
    if (!hm) return;
    setSaving(true);
    try {
      const next: HeaderMenuConfig = {
        ...hm,
        cta_button: { ...hm.cta_button, visible: !hm.cta_button.visible },
      };
      const res = await singleTypesAdminApi.upsert<HeaderMenuConfig>("header_menu", next);
      setHm(res.value);
      toast({
        title: "ذخیره شد",
        description: next.cta_button.visible ? "دکمه CTA نمایش داده می‌شود" : "دکمه CTA مخفی شد",
      });
    } catch {
      toast({ title: "خطا", description: "ذخیره تنظیمات هدر با خطا مواجه شد", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card className="p-6">
      <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
        <Settings2 className="h-4 w-4" />
        تایپ‌های تکی (پیکربندی)
      </h3>
      <ThemeEditor />
      <div className="space-y-3">
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="flex items-center gap-2">
            <Megaphone className="h-4 w-4 text-primary" />
            <div>
              <p className="font-medium text-sm">نوار اطلاع‌رسانی صفحه اصلی</p>
              <p className="text-xs text-muted-foreground">homepage_config</p>
            </div>
          </div>
          <Button
            size="sm"
            variant={hp?.announcement_bar?.enabled ? "default" : "outline"}
            onClick={toggleAnnouncement}
            disabled={!hp || saving}
          >
            {hp?.announcement_bar?.enabled ? "فعال" : "غیرفعال"}
          </Button>
        </div>
        <div className="flex items-center justify-between rounded-lg border p-3">
          <div className="flex items-center gap-2">
            <MousePointerClick className="h-4 w-4 text-primary" />
            <div>
              <p className="font-medium text-sm">دکمه CTA هدر</p>
              <p className="text-xs text-muted-foreground">header_menu</p>
            </div>
          </div>
          <Button
            size="sm"
            variant={hm?.cta_button?.visible ? "default" : "outline"}
            onClick={toggleHeaderCta}
            disabled={!hm || saving}
          >
            {hm?.cta_button?.visible ? "نمایش" : "مخفی"}
          </Button>
        </div>
      </div>
    </Card>
  );
}

/** منوساز درختی: نمایش و افزودن آیتم‌های ناوبری هر موقعیت. */
function MenuBuilderCard() {
  const { toast } = useToast();
  const [location, setLocation] = useState<string>("header_main");

  // The location list: built-ins plus whatever is in use. Fetched rather than
  // a module constant, because an operator can add a location and a constant
  // would not show it.
  const [newLocation, setNewLocation] = useState("");
  // Explicitly typed: MENU_LOCATIONS is `as const`-ish through its literal
  // values, and a custom location is an arbitrary string — the union from the
  // constant would reject it.
  const [menuLocations, setMenuLocations] = useState<
    Array<{ value: string; label: string }>
  >(MENU_LOCATIONS.map((l) => ({ value: l.value, label: l.label })));

  const loadLocations = useCallback(async () => {
    try {
      const res = await contentApi.listMenuLocations();
      const labelFor = (v: string) =>
        MENU_LOCATIONS.find((l) => l.value === v)?.label ?? v;
      setMenuLocations(
        res.all.map((v) => ({ value: v, label: labelFor(v) })),
      );
    } catch {
      // Keep the built-in list on failure — it is what the picker showed
      // before the endpoint existed.
    }
  }, []);

  useEffect(() => {
    void loadLocations();
  }, [loadLocations]);

  const [menuOpen, setMenuOpen] = useState(false);
  const [menuTitle, setMenuTitle] = useState("");
  const [menuUrl, setMenuUrl] = useState("");
  const [menuPosition, setMenuPosition] = useState("0");
  const [menuParentId, setMenuParentId] = useState<string>("");
  const [editingItem, setEditingItem] = useState<MenuItem | null>(null);
  const [creatingMenu, setCreatingMenu] = useState(false);

  // The page/post picker. WordPress's menu editor lets an operator pick a
  // page or post and fills in its title and URL; before this the only option
  // was typing the path by hand, which meant guessing the slug and getting a
  // 404 for a typo the panel could have prevented. "Custom link" stays
  // available — the picker is a shortcut, not a replacement.
  const [linkSource, setLinkSource] = useState<"custom" | "page" | "post">("custom");
  const [pageOptions, setPageOptions] = useState<Array<{ id: string; title: string; slug: string }>>([]);
  const [postOptions, setPostOptions] = useState<Array<{ id: string; title: string; slug: string }>>([]);
  const [optionsLoading, setOptionsLoading] = useState(false);

  const loadPickerOptions = async (source: "page" | "post") => {
    setOptionsLoading(true);
    try {
      if (source === "page") {
        if (pageOptions.length === 0) {
          const res = await cmsPagesAdminApi.listPages({ status: "published" });
          setPageOptions(
            (res.items ?? []).map((p) => ({ id: p.id, title: p.title, slug: p.slug })),
          );
        }
      } else if (postOptions.length === 0) {
        const res = await blogAdminApi.listPosts({ status: "published", page_size: 100 });
        setPostOptions(
          (res.items ?? []).map((p) => ({ id: p.id, title: p.title, slug: p.slug })),
        );
      }
    } catch {
      toast({
        title: "خواندن فهرست ناموفق بود",
        description: "می‌توانید آدرس را دستی وارد کنید.",
        variant: "destructive",
      });
    } finally {
      setOptionsLoading(false);
    }
  };

  const pickOption = (kind: "page" | "post", slug: string, title: string) => {
    setMenuUrl(kind === "post" ? `/blog/${slug}` : `/${slug}`);
    // Only fill the title when it is empty or was itself just auto-filled, so
    // an operator who typed a custom label does not lose it to a pick.
    if (!menuTitle.trim()) setMenuTitle(title);
  };

  const flatItems = (list: MenuItem[], depth = 0): (MenuItem & { depth: number })[] =>
    list.flatMap((i) => [{ ...i, depth }, ...(i.children ? flatItems(i.children, depth + 1) : [])]);

  // Menu is keyed on `location`: switching the location picker refetches, and
  // switching back serves the earlier tree from cache. Its failure was silent
  // (an empty menu) — keep it silent, since the location list itself is the
  // control the operator uses.
  const {
    data: menuData,
    loading: loadingMenu,
    reload: fetchMenu,
  } = useAdminQuery({
    queryKey: [CMS_MENU_QUERY_KEY, location],
    queryFn: () => contentApi.getMenu(location),
    fallbackError: "دریافت منو ناموفق بود",
  });
  const items: MenuItem[] = menuData ?? [];

  const openCreate = () => {
    setEditingItem(null);
    setMenuTitle("");
    setMenuUrl("");
    setMenuPosition("0");
    setMenuParentId("");
    setMenuOpen(true);
  };

  const openEdit = (item: MenuItem) => {
    setEditingItem(item);
    setMenuTitle(item.title);
    setMenuUrl(item.url);
    setMenuPosition(String(item.position));
    setMenuParentId(item.parent_id ?? "");
    setMenuOpen(true);
  };

  const createItem = async () => {
    if (!menuTitle.trim() || !menuUrl.trim()) {
      toast({ title: "خطا", description: "عنوان و آدرس الزامی است", variant: "destructive" });
      return;
    }
    setCreatingMenu(true);
    try {
      if (editingItem) {
        await apiClient.patch(`/content/admin/menus/${editingItem.id}`, {
          title: menuTitle.trim(),
          url: menuUrl.trim(),
          position: Number.parseInt(menuPosition, 10) || 0,
          parent_id: menuParentId || null,
        });
        toast({ title: "موفق", description: "آیتم منو به‌روزرسانی شد" });
      } else {
        await apiClient.post("/content/admin/menus", {
          location,
          title: menuTitle.trim(),
          url: menuUrl.trim(),
          parent_id: menuParentId || null,
          position: Number.parseInt(menuPosition, 10) || 0,
        });
        toast({ title: "موفق", description: "آیتم منو اضافه شد" });
      }
      setMenuOpen(false);
      fetchMenu();
    } catch {
      toast({ title: "خطا", description: "ذخیره آیتم منو با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreatingMenu(false);
    }
  };

  const deleteItem = async (item: MenuItem) => {
    if (!confirm(`آیتم «${item.title}» حذف شود؟`)) return;
    try {
      await apiClient.delete(`/content/admin/menus/${item.id}`);
      fetchMenu();
    } catch {
      toast({ title: "خطا", description: "حذف آیتم ناموفق بود", variant: "destructive" });
    }
  };

  const toggleItem = async (item: MenuItem) => {
    try {
      await apiClient.patch(`/content/admin/menus/${item.id}`, {
        is_active: item.is_active === false ? true : false,
      });
      fetchMenu();
    } catch {
      toast({ title: "خطا", description: "تغییر وضعیت ناموفق بود", variant: "destructive" });
    }
  };

  /** Move an item one slot up or down among its siblings, then persist the
   *  whole tree in one request. The list is depth-first, so a swap of
   *  positions within the same parent is the only thing that changes. */
  const moveItem = async (item: MenuItem & { depth: number }, direction: -1 | 1) => {
    const flat = flatItems(items);
    const index = flat.findIndex((i) => i.id === item.id);
    const siblingIndex = direction === -1 ? index - 1 : index + 1;
    if (siblingIndex < 0 || siblingIndex >= flat.length) return;
    const sibling = flat[siblingIndex];
    if (!sibling) return;
    if (sibling.parent_id !== item.parent_id) {
      toast({
        title: "خطا",
        description: "فقط آیتم‌های هم‌سطح قابل جابه‌جایی هستند",
        variant: "destructive",
      });
      return;
    }
    const a = item.position;
    const b = sibling.position;
    try {
      await contentAdminApi.reorderMenu(location, [
        { id: item.id, parent_id: item.parent_id ?? null, position: b },
        { id: sibling.id, parent_id: sibling.parent_id ?? null, position: a },
      ]);
      fetchMenu();
    } catch {
      toast({ title: "خطا", description: "جابه‌جایی ناموفق بود", variant: "destructive" });
    }
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-lg font-semibold flex items-center gap-2">
          <Menu className="h-4 w-4" />
          منوساز
        </h3>
        <Button size="sm" variant="outline" onClick={openCreate}>
          <Plus className="h-4 w-4 ms-1" />
          افزودن
        </Button>
      </div>
      <div className="mb-3 space-y-2">
        <Select value={location} onValueChange={setLocation}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {/* The built-ins plus any location already in use. A location an
                operator added would otherwise vanish from the picker that
                created it. */}
            {menuLocations.map((loc) => (
              <SelectItem key={loc.value} value={loc.value}>
                {loc.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* Create a new location — WordPress registers locations from the
            theme; this store lets an operator add one (a campaign bar, a
            landing-page nav) without a deploy. */}
        <div className="flex items-center gap-1.5">
          <Input
            dir="ltr"
            placeholder="مکان جدید، مثلاً campaign_bar"
            value={newLocation}
            onChange={(e) => setNewLocation(e.target.value)}
            className="h-8 text-xs font-mono"
          />
          <Button
            size="sm"
            variant="outline"
            disabled={!newLocation.trim()}
            onClick={() => {
              const slug = newLocation.trim().toLowerCase();
              if (!/^[a-z0-9][a-z0-9_-]{0,31}$/.test(slug)) {
                toast({
                  title: "نام مکان نامعتبر است",
                  description: "فقط a-z، 0-9، _ و - — با حرف یا عدد شروع شود.",
                  variant: "destructive",
                });
                return;
              }
              // A location exists once something is in it, so "create" selects
              // it and the operator adds the first item.
              setLocation(slug);
              setNewLocation("");
            }}
          >
            افزودن مکان
          </Button>
        </div>
      </div>
      {loadingMenu ? (
        <div className="flex items-center justify-center py-6">
          <RefreshCw className="h-4 w-4 animate-spin text-muted-foreground" />
        </div>
      ) : items.length === 0 ? (
        <p className="text-sm text-muted-foreground text-center py-6">
          آیتمی برای این موقعیت تعریف نشده است
        </p>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {flatItems(items).map((item) => (
            <div
              key={item.id}
              className={`flex items-center justify-between rounded-lg border p-3 ${item.is_active === false ? "opacity-50" : ""}`}
              style={{ marginRight: item.depth * 20 }}
            >
              <div>
                <p className="font-medium text-sm">
                  {item.depth > 0 && <span className="text-muted-foreground me-1">{"—".repeat(item.depth)} </span>}
                  {item.title}
                </p>
                <p className="text-xs text-muted-foreground font-mono" dir="ltr">
                  {item.url}
                </p>
              </div>
              <div className="flex items-center gap-1.5">
                <Badge variant="outline" className="text-xs">
                  ترتیب {item.position}
                </Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={() => moveItem(item, -1)}
                  title="یک پله بالا"
                >
                  <ChevronUp className="h-3.5 w-3.5" />
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  className="h-7 w-7 p-0"
                  onClick={() => moveItem(item, 1)}
                  title="یک پله پایین"
                >
                  <ChevronDown className="h-3.5 w-3.5" />
                </Button>
                <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => toggleItem(item)} title={item.is_active === false ? "فعال" : "غیرفعال"}>
                  {item.is_active === false ? "فعال" : "غیرفعال"}
                </Button>
                <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => openEdit(item)} title="ویرایش">
                  ویرایش
                </Button>
                <Button size="sm" variant="ghost" className="h-7 px-2 text-destructive" onClick={() => deleteItem(item)} title="حذف">
                  <Trash2 className="h-3.5 w-3.5" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>{editingItem ? "ویرایش آیتم منو" : "افزودن آیتم منو"}</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {/* Pick what the link points at. A page or post fills the title
                and URL from the real record, so a typo cannot produce a 404
                link; "custom" keeps the old free-text path for anything else. */}
            <div className="space-y-2">
              <Label>نوع پیوند</Label>
              <Select
                value={linkSource}
                onValueChange={(v) => {
                  const source = v as "custom" | "page" | "post";
                  setLinkSource(source);
                  if (source !== "custom") void loadPickerOptions(source);
                }}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="custom">لینک سفارشی (دستی)</SelectItem>
                  <SelectItem value="page">برگه</SelectItem>
                  <SelectItem value="post">نوشته</SelectItem>
                </SelectContent>
              </Select>
            </div>

            {linkSource === "page" && (
              <div className="space-y-2">
                <Label>انتخاب برگه</Label>
                <Select
                  value=""
                  onValueChange={(v) => {
                    const p = pageOptions.find((o) => o.id === v);
                    if (p) pickOption("page", p.slug, p.title);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={optionsLoading ? "در حال خواندن..." : "یک برگه انتخاب کنید"}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {pageOptions.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            {linkSource === "post" && (
              <div className="space-y-2">
                <Label>انتخاب نوشته</Label>
                <Select
                  value=""
                  onValueChange={(v) => {
                    const p = postOptions.find((o) => o.id === v);
                    if (p) pickOption("post", p.slug, p.title);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue
                      placeholder={optionsLoading ? "در حال خواندن..." : "یک نوشته انتخاب کنید"}
                    />
                  </SelectTrigger>
                  <SelectContent>
                    {postOptions.map((p) => (
                      <SelectItem key={p.id} value={p.id}>
                        {p.title}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}

            <div className="space-y-2">
              <Label>عنوان</Label>
              <Input value={menuTitle} onChange={(e) => setMenuTitle(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>آدرس</Label>
              <Input
                dir="ltr"
                placeholder="/products"
                value={menuUrl}
                onChange={(e) => setMenuUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>والد (اختیاری — برای آیتم تودرتو)</Label>
              <Select value={menuParentId} onValueChange={setMenuParentId}>
                <SelectTrigger>
                  <SelectValue placeholder="بدون والد (ریشه)" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">بدون والد (ریشه)</SelectItem>
                  {flatItems(items).map((i) => (
                    <SelectItem key={i.id} value={i.id} disabled={editingItem?.id === i.id}>
                      {"—".repeat(i.depth)} {i.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>ترتیب نمایش</Label>
              <Input
                dir="ltr"
                type="number"
                value={menuPosition}
                onChange={(e) => setMenuPosition(e.target.value)}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setMenuOpen(false)}>
              انصراف
            </Button>
            <Button onClick={createItem} disabled={creatingMenu}>
              {creatingMenu ? "در حال ذخیره..." : editingItem ? "به‌روزرسانی" : "افزودن"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
