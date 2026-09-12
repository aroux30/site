"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Layout, RefreshCw, Plus, Menu, HelpCircle, Trash2, ArrowUp, ArrowDown } from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useToast } from "@/components/ui/use-toast";
import apiClient from "@/lib/api/client";

interface HomepageBlock {
  id: string;
  title: string;
  block_type: string;
  position: number;
  is_active: boolean;
}

interface FAQItem {
  id: string;
  question: string;
  answer_html: string;
  category: string;
  position: number;
}

export default function AdminCMSPage() {
  const { toast } = useToast();
  const [blocks, setBlocks] = useState<HomepageBlock[]>([]);
  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [loading, setLoading] = useState(true);

  // FAQ create
  const [faqOpen, setFaqOpen] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState("");
  const [faqAnswer, setFaqAnswer] = useState("");
  const [faqCategory, setFaqCategory] = useState("عمومی");
  const [creating, setCreating] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [blocksRes, faqsRes] = await Promise.allSettled([
        apiClient.get("/content/blocks"),
        apiClient.get("/content/faqs"),
      ]);
      if (blocksRes.status === "fulfilled") {
        setBlocks(Array.isArray(blocksRes.value.data) ? blocksRes.value.data : []);
      }
      if (faqsRes.status === "fulfilled") {
        setFaqs(Array.isArray(faqsRes.value.data.items) ? faqsRes.value.data.items : []);
      }
    } catch {
      toast({ title: "خطا", description: "بارگذاری CMS با خطا مواجه شد", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const createFAQ = async () => {
    if (!faqQuestion.trim() || !faqAnswer.trim()) {
      toast({ title: "خطا", description: "سوال و پاسخ الزامی است", variant: "destructive" });
      return;
    }
    setCreating(true);
    try {
      await apiClient.post("/content/admin/faqs", {
        question: faqQuestion,
        answer_html: faqAnswer,
        category: faqCategory,
      });
      toast({ title: "موفق", description: "سوال جدید اضافه شد" });
      setFaqOpen(false);
      setFaqQuestion("");
      setFaqAnswer("");
      fetchData();
    } catch {
      toast({ title: "خطا", description: "ایجاد سوال با خطا مواجه شد", variant: "destructive" });
    } finally {
      setCreating(false);
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
          <RefreshCw className="h-4 w-4 mr-2" />
          بروزرسانی
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center justify-center p-12">
          <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Homepage Blocks */}
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">بلوک‌های صفحه اصلی</h3>
            {blocks.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-8">
                هنوز هیچ بلوکی تعریف نشده است
              </p>
            ) : (
              <div className="space-y-2">
                {blocks.map((b) => (
                  <div key={b.id} className="flex items-center justify-between rounded-lg border p-3">
                    <div>
                      <p className="font-medium text-sm">{b.title}</p>
                      <Badge variant="outline" className="text-xs mt-1">{b.block_type}</Badge>
                    </div>
                    <Badge className={b.is_active ? "bg-emerald-500/10 text-emerald-500" : "bg-neutral-500/10 text-neutral-500"}>
                      {b.is_active ? "فعال" : "غیرفعال"}
                    </Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* FAQs */}
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold flex items-center gap-2">
                <HelpCircle className="h-4 w-4" />
                سوالات متداول
              </h3>
              <Button size="sm" variant="outline" onClick={() => setFaqOpen(true)}>
                <Plus className="h-4 w-4 mr-1" />
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
                  <div key={f.id} className="rounded-lg border p-3">
                    <p className="font-medium text-sm">{f.question}</p>
                    <Badge variant="outline" className="text-xs mt-1">{f.category}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}

      {/* FAQ Create Dialog */}
      <Dialog open={faqOpen} onOpenChange={setFaqOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>افزودن سوال متداول</DialogTitle>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>سوال</Label>
              <Input value={faqQuestion} onChange={(e) => setFaqQuestion(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>پاسخ</Label>
              <Textarea rows={4} value={faqAnswer} onChange={(e) => setFaqAnswer(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>دسته‌بندی</Label>
              <Input value={faqCategory} onChange={(e) => setFaqCategory(e.target.value)} />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFaqOpen(false)}>انصراف</Button>
            <Button onClick={createFAQ} disabled={creating}>
              {creating ? "در حال افزودن..." : "افزودن"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
