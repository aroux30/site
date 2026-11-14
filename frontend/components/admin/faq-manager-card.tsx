"use client";

/**
 * FAQ manager card — lives on its own admin section (/admin/faq).
 *
 * The card used to sit inside the «محتوا و منوساز» dashboard, which is a
 * layout surface (homepage blocks, menu builder, reusable blocks); FAQ
 * entries are page *content*, consumed by the /faq storefront page and any
 * page that embeds the [faq] shortcode — so they got their own section.
 */

import { useState } from "react";
import { CircleHelp, Plus, Trash2 } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import RichBodyEditor from "@/components/admin/RichBodyEditor";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { useConfirm } from "@/components/ui/confirm-dialog";
import apiClient from "@/lib/api/client";
import { useAdminQuery } from "@/lib/api/admin-query";

const FAQ_QUERY_KEY = "admin-faqs" as const;

interface FAQItem {
  id: string;
  question: string;
  answer_html: string;
  category: string;
  position: number;
  is_active: boolean;
}

export default function FaqManagerCard() {
  const { toast } = useToast();
  const confirm = useConfirm();

  const [faqOpen, setFaqOpen] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState("");
  const [faqAnswer, setFaqAnswer] = useState("");
  const [faqCategory, setFaqCategory] = useState("عمومی");
  const [editingFaq, setEditingFaq] = useState<FAQItem | null>(null);
  const [creating, setCreating] = useState(false);

  const { data, loading, reload } = useAdminQuery({
    queryKey: [FAQ_QUERY_KEY],
    queryFn: async () => {
      const res = await apiClient.get("/content/faqs");
      return {
        faqs: Array.isArray(res.data?.items)
          ? (res.data.items as FAQItem[])
          : [],
      };
    },
    fallbackError: "بارگذاری سوالات متداول با خطا مواجه شد",
  });
  const faqs: FAQItem[] = data?.faqs ?? [];

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
      reload();
    } catch {
      toast({ title: "خطا", description: "ذخیره سوال با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const deleteFaq = async (f: FAQItem) => {
    const ok = await confirm({
      title: "حذف سوال",
      description: `سوال «${f.question}» حذف شود؟`,
      confirmLabel: "حذف",
      destructive: true,
    });
    if (!ok) return;
    try {
      await apiClient.delete(`/content/admin/faqs/${f.id}`);
      reload();
    } catch {
      toast({ title: "خطا", description: "حذف سوال ناموفق بود", variant: "destructive" });
    }
  };

  const toggleFaq = async (f: FAQItem) => {
    try {
      await apiClient.patch(`/content/admin/faqs/${f.id}`, { is_active: !f.is_active });
      reload();
    } catch {
      toast({ title: "خطا", description: "تغییر وضعیت ناموفق بود", variant: "destructive" });
    }
  };

  return (
    <>
      <Card className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold flex items-center gap-2">
            <CircleHelp className="h-4 w-4" />
            سوالات متداول
          </h3>
          <Button size="sm" variant="outline" onClick={openCreateFaq}>
            <Plus className="h-4 w-4 ms-1" />
            افزودن
          </Button>
        </div>
        {loading ? (
          <p className="text-sm text-muted-foreground text-center py-8">در حال بارگذاری…</p>
        ) : faqs.length === 0 ? (
          <p className="text-sm text-muted-foreground text-center py-8">
            هنوز هیچ سوالی تعریف نشده است
          </p>
        ) : (
          <div className="space-y-2 max-h-[32rem] overflow-y-auto">
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
        {/* The shortcode is the whole point of this section being separate:
            an operator copies this token into any page body and the live
            entries render there (details/summary accordion). */}
        <p className="mt-4 rounded-lg bg-muted/40 border border-border px-3 py-2 text-xs text-muted-foreground" dir="rtl">
          درج در هر صفحه: کد کوتاه <code dir="ltr" className="font-mono text-foreground">[faq]</code> —
          یا فقط یک دسته: <code dir="ltr" className="font-mono text-foreground">[faq category=&quot;پرداخت&quot;]</code>
        </p>
      </Card>

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
    </>
  );
}
