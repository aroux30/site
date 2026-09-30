"use client";

import { useState, useMemo, useEffect } from "react";
import Link from "next/link";
import {
  Search,
  ShoppingCart,
  Truck,
  RotateCcw,
  UserCircle,
  Phone,
  Mail,
  MessageCircle,
  HelpCircle,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import cleanHtml from "@/lib/sanitize-html";
import { safeJsonLd } from "@/lib/safe-json-ld";

interface FAQItem {
  id: string;
  question: string;
  answer_html: string;
  category: string;
  position: number;
}

interface FAQListResponse {
  items: FAQItem[];
  total: number;
  schema_json_ld: Record<string, unknown>;
}

interface FAQCategory {
  id: string;
  title: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
  items: FAQItem[];
}

const CATEGORY_STYLES = [
  { icon: ShoppingCart, color: "text-blue-500 bg-blue-50 dark:bg-blue-950/40" },
  { icon: Truck, color: "text-emerald-500 bg-emerald-50 dark:bg-emerald-950/40" },
  { icon: RotateCcw, color: "text-orange-500 bg-orange-50 dark:bg-orange-950/40" },
  { icon: UserCircle, color: "text-purple-500 bg-purple-50 dark:bg-purple-950/40" },
];

function stripHtml(html: string): string {
  return html.replace(/<[^>]*>/g, " ");
}

function groupFaqs(items: FAQItem[]): FAQCategory[] {
  const order: string[] = [];
  const byCat = new Map<string, FAQItem[]>();
  for (const item of items) {
    const cat = item.category || "عمومی";
    if (!byCat.has(cat)) {
      byCat.set(cat, []);
      order.push(cat);
    }
    byCat.get(cat)!.push(item);
  }
  return order.map((cat, i) => {
    const style = CATEGORY_STYLES[i % CATEGORY_STYLES.length]!;
    return {
      id: `cat-${i}`,
      title: cat,
      icon: style.icon,
      color: style.color,
      items: byCat.get(cat)!,
    };
  });
}

export default function FAQPage() {
  const [searchQuery, setSearchQuery] = useState("");
  const [faqs, setFaqs] = useState<FAQItem[]>([]);
  const [schemaJsonLd, setSchemaJsonLd] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  // FAQs are admin-managed (content module). The page must reflect the CMS,
  // not a baked-in list — otherwise editor changes never reach customers.
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const res = await fetch("/api/v1/content/faqs", { credentials: "include" });
        if (!res.ok) throw new Error("faq fetch failed");
        const data = (await res.json()) as FAQListResponse;
        if (!mounted) return;
        setFaqs(Array.isArray(data.items) ? data.items : []);
        setSchemaJsonLd(data.schema_json_ld ?? null);
      } catch {
        if (mounted) setFaqs([]);
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, []);

  const categories = useMemo(() => groupFaqs(faqs), [faqs]);

  const filteredCategories = useMemo(() => {
    if (!searchQuery.trim()) return categories;

    const query = searchQuery.trim().toLowerCase();
    return categories
      .map((category) => ({
        ...category,
        items: category.items.filter(
          (item) =>
            item.question.toLowerCase().includes(query) ||
            stripHtml(item.answer_html).toLowerCase().includes(query)
        ),
      }))
      .filter((category) => category.items.length > 0);
  }, [categories, searchQuery]);

  const totalResults = filteredCategories.reduce(
    (acc, cat) => acc + cat.items.length,
    0
  );

  return (
    <div className="container-page">
      {/* FAQPage JSON-LD — generated server-side by the CMS from live FAQs */}
      {schemaJsonLd && (
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: safeJsonLd(schemaJsonLd) }}
        />
      )}
      {/* Breadcrumb */}
      <div className="mb-6 flex items-center gap-2 text-sm text-muted-foreground">
        <Link href="/" className="transition-colors hover:text-primary">
          صفحه اصلی
        </Link>
        <span>/</span>
        <span className="font-medium text-foreground">سوالات متداول</span>
      </div>

      {/* Hero Section */}
      <section className="mb-12 rounded-2xl bg-gradient-to-l from-primary-600 to-secondary-600 p-8 text-white sm:p-14">
        <div className="mx-auto max-w-2xl text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-white/15 backdrop-blur-sm">
            <HelpCircle className="h-8 w-8" />
          </div>
          <h1 className="mb-3 text-3xl font-bold sm:text-4xl">
            سوالات متداول
          </h1>
          <p className="mb-8 text-lg leading-relaxed text-white/90">
            پاسخ سوالات رایج خود را در اینجا بیابید. اگر پاسخ سوال خود را
            نیافتید، با تیم پشتیبانی ما تماس بگیرید.
          </p>

          {/* Search Input */}
          <div className="relative mx-auto max-w-md">
            <Search className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="جستجو در سوالات متداول..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="h-12 rounded-xl border-white/20 bg-white ps-12 text-foreground shadow-lg placeholder:text-muted-foreground"
            />
          </div>
        </div>
      </section>

      {/* Search Results Info */}
      {searchQuery.trim() && (
        <div className="mb-6 flex items-center justify-between">
          <p className="text-sm text-muted-foreground">
            {totalResults > 0 ? (
              <>
                <span className="font-medium text-foreground">
                  {totalResults}
                </span>{" "}
                نتیجه برای &laquo;{searchQuery}&raquo; یافت شد
              </>
            ) : (
              <>نتیجه‌ای برای &laquo;{searchQuery}&raquo; یافت نشد</>
            )}
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setSearchQuery("")}
            className="text-xs"
          >
            پاک کردن جستجو
          </Button>
        </div>
      )}

      {/* FAQ Categories */}
      {loading ? (
        <div className="rounded-2xl border border-border bg-card p-12 text-center text-sm text-muted-foreground">
          در حال بارگذاری سوالات متداول…
        </div>
      ) : filteredCategories.length > 0 ? (
        <div className="space-y-10">
          {filteredCategories.map((category) => {
            const CategoryIcon = category.icon;
            return (
            <section key={category.id}>
              {/* Category Header */}
              <div className="mb-4 flex items-center gap-3">
                <div
                  className={`flex h-10 w-10 items-center justify-center rounded-xl ${category.color}`}
                >
                  <CategoryIcon className="h-5 w-5" />
                </div>
                <h2 className="text-xl font-bold text-foreground">
                  {category.title}
                </h2>
              </div>

              {/* Accordion */}
              <Card className="overflow-hidden">
                <Accordion type="single" collapsible className="w-full">
                  {category.items.map((item, index) => (
                    <AccordionItem
                      key={index}
                      value={`${category.id}-${index}`}
                      className="border-border px-6"
                    >
                      <AccordionTrigger className="text-right text-sm font-medium leading-relaxed sm:text-base">
                        {item.question}
                      </AccordionTrigger>
                      <AccordionContent className="text-sm leading-7 text-muted-foreground">
                        <div
                          className="[&_a]:text-primary [&_a]:underline [&_ul]:my-2 [&_ul]:list-disc [&_ul]:ps-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:ps-5 [&_strong]:text-foreground"
                          dangerouslySetInnerHTML={{ __html: cleanHtml(item.answer_html) }}
                        />
                      </AccordionContent>
                    </AccordionItem>
                  ))}
                </Accordion>
              </Card>
            </section>
            );
          })}
        </div>
      ) : (
        <div className="rounded-2xl border border-border bg-card p-12 text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-muted text-muted-foreground">
            <Search className="h-8 w-8" />
          </div>
          <h3 className="mb-2 text-lg font-semibold text-foreground">
            نتیجه‌ای یافت نشد
          </h3>
          <p className="mb-6 text-sm text-muted-foreground">
            سوال مورد نظر شما در لیست سوالات متداول یافت نشد. لطفاً با تیم
            پشتیبانی ما تماس بگیرید.
          </p>
          <Link href="/contact">
            <Button>تماس با پشتیبانی</Button>
          </Link>
        </div>
      )}

      {/* Contact Support CTA */}
      <section className="mt-16 mb-4 rounded-2xl border border-border bg-card p-8 sm:p-12">
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="mb-3 text-2xl font-bold text-foreground">
            پاسخ سوال خود را نیافتید؟
          </h2>
          <p className="mb-8 text-muted-foreground">
            تیم پشتیبانی ما آماده پاسخگویی به سوالات شماست. از طریق یکی از
            روش‌های زیر با ما در ارتباط باشید.
          </p>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-blue-50 text-blue-500 dark:bg-blue-950/40">
                <Phone className="h-5 w-5" />
              </div>
              <h3 className="mb-1 text-sm font-semibold text-foreground">
                تماس تلفنی
              </h3>
              <p className="text-xs text-muted-foreground" dir="ltr">
                ۰۲۱-۱۲۳۴۵۶۷۸
              </p>
            </Card>

            <Card className="p-5 transition-shadow hover:shadow-md">
              <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-500 dark:bg-emerald-950/40">
                <Mail className="h-5 w-5" />
              </div>
              <h3 className="mb-1 text-sm font-semibold text-foreground">
                ایمیل
              </h3>
              <p className="text-xs text-muted-foreground" dir="ltr">
                support@example.com
              </p>
            </Card>

            <Link href="/contact" className="block">
              <Card className="h-full p-5 transition-shadow hover:shadow-md">
                <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-lg bg-purple-50 text-purple-500 dark:bg-purple-950/40">
                  <MessageCircle className="h-5 w-5" />
                </div>
                <h3 className="mb-1 text-sm font-semibold text-foreground">
                  فرم تماس
                </h3>
                <p className="text-xs text-muted-foreground">
                  ارسال پیام آنلاین
                </p>
              </Card>
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
