"use client";

/**
 * Custom taxonomies tab (WordPress parity).
 *
 * Lets editors define their own classification systems (brand, color, region…)
 * and create terms inside each one. Terms are then attachable to posts.
 */

import { useCallback, useEffect, useState } from "react";
import { Plus, Tag, Layers, RefreshCw, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  taxonomiesApi,
  type CustomTaxonomy,
  type CustomTaxonomyTerm,
} from "@/lib/api/wp-parity";

export function TaxonomiesTab() {
  const { toast } = useToast();
  const [taxonomies, setTaxonomies] = useState<CustomTaxonomy[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CustomTaxonomy | null>(null);
  const [terms, setTerms] = useState<CustomTaxonomyTerm[]>([]);
  const [termsLoading, setTermsLoading] = useState(false);

  const [newName, setNewName] = useState("");
  const [newHierarchical, setNewHierarchical] = useState(false);
  const [creating, setCreating] = useState(false);

  const [newTermName, setNewTermName] = useState("");
  const [creatingTerm, setCreatingTerm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setTaxonomies(await taxonomiesApi.list());
    } catch {
      toast({ title: "خطا در بارگذاری تاکسونومی‌ها", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadTerms = useCallback(
    async (tax: CustomTaxonomy) => {
      setTermsLoading(true);
      try {
        setTerms(await taxonomiesApi.listTerms(tax.id));
      } catch {
        toast({ title: "خطا در بارگذاری ترم‌ها", variant: "destructive" });
      } finally {
        setTermsLoading(false);
      }
    },
    [toast],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await taxonomiesApi.create({ name: newName.trim(), hierarchical: newHierarchical });
      toast({ title: "تاکسونومی ساخته شد" });
      setNewName("");
      setNewHierarchical(false);
      await load();
    } catch {
      toast({ title: "ساخت تاکسونومی ناموفق بود", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const handleCreateTerm = async () => {
    if (!selected || !newTermName.trim()) return;
    setCreatingTerm(true);
    try {
      await taxonomiesApi.createTerm(selected.id, { name: newTermName.trim() });
      toast({ title: "ترم اضافه شد" });
      setNewTermName("");
      await loadTerms(selected);
    } catch {
      toast({ title: "افزودن ترم ناموفق بود", variant: "destructive" });
    } finally {
      setCreatingTerm(false);
    }
  };

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {/* Taxonomy list */}
      <Card className="p-4 space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            <Layers className="h-4 w-4" /> تاکسونومی‌های سفارشی
          </h3>
          <Button variant="ghost" size="sm" onClick={() => void load()} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>

        <div className="space-y-2 rounded-lg border border-border p-3">
          <Label htmlFor="tax-name" className="text-xs">
            نام تاکسونومی جدید
          </Label>
          <div className="flex gap-2">
            <Input
              id="tax-name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              placeholder="مثلاً: برند، رنگ، منطقه"
              className="text-xs"
            />
            <Button size="sm" onClick={() => void handleCreate()} disabled={creating || !newName.trim()}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <label className="flex items-center gap-2 text-[11px] text-muted-foreground">
            <input
              type="checkbox"
              checked={newHierarchical}
              onChange={(e) => setNewHierarchical(e.target.checked)}
              className="h-3.5 w-3.5"
            />
            سلسله‌مراتبی (والد/فرزند)
          </label>
        </div>

        {loading ? (
          <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
        ) : taxonomies.length === 0 ? (
          <p className="py-6 text-center text-xs text-muted-foreground">
            هنوز تاکسونومی سفارشی ساخته نشده است.
          </p>
        ) : (
          <div className="space-y-2">
            {taxonomies.map((tax) => (
              <button
                key={tax.id}
                type="button"
                onClick={() => {
                  setSelected(tax);
                  void loadTerms(tax);
                }}
                className={`flex w-full items-center justify-between rounded-lg border p-3 text-start transition-colors ${
                  selected?.id === tax.id
                    ? "border-primary bg-primary/5"
                    : "border-border hover:bg-muted/50"
                }`}
              >
                <div>
                  <div className="text-xs font-medium">{tax.name}</div>
                  <div className="text-[11px] text-muted-foreground" dir="ltr">
                    /{tax.slug}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {tax.hierarchical && (
                    <Badge variant="outline" className="text-[10px]">
                      سلسله‌مراتبی
                    </Badge>
                  )}
                  <ChevronRight className="h-4 w-4 text-muted-foreground rtl:rotate-180" />
                </div>
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Terms of the selected taxonomy */}
      <Card className="p-4 space-y-4">
        <h3 className="flex items-center gap-2 text-sm font-semibold">
          <Tag className="h-4 w-4" />
          {selected ? `ترم‌های «${selected.name}»` : "ترم‌ها"}
        </h3>

        {!selected ? (
          <p className="py-8 text-center text-xs text-muted-foreground">
            یک تاکسونومی را از فهرست کنار انتخاب کنید.
          </p>
        ) : (
          <>
            <div className="flex gap-2">
              <Input
                value={newTermName}
                onChange={(e) => setNewTermName(e.target.value)}
                placeholder="نام ترم جدید"
                className="text-xs"
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleCreateTerm();
                }}
              />
              <Button
                size="sm"
                onClick={() => void handleCreateTerm()}
                disabled={creatingTerm || !newTermName.trim()}
              >
                <Plus className="h-4 w-4" />
              </Button>
            </div>

            {termsLoading ? (
              <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
            ) : terms.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                این تاکسونومی هنوز ترمی ندارد.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {terms.map((term) => (
                  <Badge key={term.id} variant="secondary" className="gap-1 text-[11px]">
                    {term.name}
                  </Badge>
                ))}
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
