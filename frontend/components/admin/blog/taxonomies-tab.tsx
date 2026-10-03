"use client";

/**
 * Custom taxonomies tab (WordPress parity).
 *
 * Lets editors define their own classification systems (brand, colour, region…)
 * and manage the terms inside each one. Terms are then attachable to posts
 * through the post editor (`PostTermsPicker`).
 *
 * This tab used to offer nothing but "create". A taxonomy could not be renamed
 * or removed, and a term could not be renamed, re-parented or deleted — even
 * though the API and the typed client had all four calls ready. A typo in a
 * taxonomy name was therefore permanent: the only fix was to build another one
 * and re-enter every term.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Plus, Tag, Layers, RefreshCw, ChevronRight, Pencil, X, Loader2, Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/use-toast";
import {
  taxonomiesApi,
  OBJECT_TYPES,
  type CustomTaxonomy,
  type CustomTaxonomyTerm,
  type ObjectType,
} from "@/lib/api/wp-parity";
import { toPersianDigits } from "@/lib/utils";

/** One term plus its children, ready to render as a tree. */
interface TermNode {
  term: CustomTaxonomyTerm;
  children: TermNode[];
}

/**
 * Turns the flat term list into a tree.
 *
 * A term whose parent is missing from the list (deleted under it, or attached
 * before the tree existed) is promoted to the top level rather than dropped:
 * hiding it would make an operator believe the term no longer exists.
 */
function buildTree(terms: CustomTaxonomyTerm[]): TermNode[] {
  const byId = new Map<string, TermNode>();
  for (const t of terms) byId.set(t.id, { term: t, children: [] });
  const roots: TermNode[] = [];
  for (const node of byId.values()) {
    const pid = node.term.parent_id;
    const parent = pid ? byId.get(pid) : undefined;
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  const byPosition = (a: TermNode, b: TermNode) =>
    (a.term.position ?? 0) - (b.term.position ?? 0) ||
    a.term.name.localeCompare(b.term.name, "fa");
  const sort = (nodes: TermNode[]) => {
    nodes.sort(byPosition);
    nodes.forEach((n) => sort(n.children));
  };
  sort(roots);
  return roots;
}

/** Persian labels for the content types a taxonomy can apply to. */
const OBJECT_LABELS: Record<ObjectType, string> = {
  blog_post: "نوشته‌ها",
  cms_page: "برگه‌ها",
  custom_post_entry: "ورودی‌های سفارشی",
};

export function TaxonomiesTab() {
  const { toast } = useToast();
  const [taxonomies, setTaxonomies] = useState<CustomTaxonomy[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<CustomTaxonomy | null>(null);
  const [terms, setTerms] = useState<CustomTaxonomyTerm[]>([]);
  const [termsLoading, setTermsLoading] = useState(false);
  // Server-side: filtering the received slice would report "no match"
  // for a term that exists beyond the first page.
  const [termSearch, setTermSearch] = useState("");

  const [newName, setNewName] = useState("");
  const [newHierarchical, setNewHierarchical] = useState(false);
  // Defaults to posts and pages: the two types a store actually uses.
  const [newObjectTypes, setNewObjectTypes] = useState<ObjectType[]>([
    "blog_post",
    "cms_page",
  ]);
  const [creating, setCreating] = useState(false);

  const [newTermName, setNewTermName] = useState("");
  const [newTermParent, setNewTermParent] = useState("");
  const [creatingTerm, setCreatingTerm] = useState(false);

  /** Inline-editing state for one row, so the tab does not turn into a form. */
  const [editing, setEditing] = useState<{
    kind: "taxonomy" | "term";
    id: string;
    name: string;
    slug: string;
    description: string;
    parent_id: string;
    object_types: ObjectType[];
  } | null>(null);
  const [saving, setSaving] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const list = await taxonomiesApi.list();
      setTaxonomies(list);
      // Keep the selection pointing at real data: a taxonomy deleted in another
      // tab must not leave its detail pane open on nothing.
      setSelected((prev) =>
        prev ? (list.find((t) => t.id === prev.id) ?? null) : null,
      );
    } catch {
      toast({ title: "خطا در بارگذاری تاکسونومی‌ها", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  const loadTerms = useCallback(
    async (tax: CustomTaxonomy, search?: string) => {
      setTermsLoading(true);
      try {
        setTerms(await taxonomiesApi.listTerms(tax.id, search));
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

  // Debounced: a keystroke-per-request would fire a query per character, and
  // the response for a slow earlier keystroke can land after a faster later
  // one and overwrite it.
  useEffect(() => {
    if (!selected) return;
    const t = setTimeout(() => void loadTerms(selected, termSearch), 250);
    return () => clearTimeout(t);
  }, [selected, termSearch, loadTerms]);

  const tree = useMemo(() => buildTree(terms), [terms]);

  const handleCreate = async () => {
    if (!newName.trim()) return;
    setCreating(true);
    try {
      await taxonomiesApi.create({
        name: newName.trim(),
        hierarchical: newHierarchical,
        object_types: newObjectTypes,
      });
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
      await taxonomiesApi.createTerm(selected.id, {
        name: newTermName.trim(),
        // Empty means "top level"; sending "" would be an invalid UUID.
        ...(newTermParent ? { parent_id: newTermParent } : {}),
      });
      toast({ title: "ترم اضافه شد" });
      setNewTermName("");
      setNewTermParent("");
      await loadTerms(selected);
    } catch {
      toast({ title: "افزودن ترم ناموفق بود", variant: "destructive" });
    } finally {
      setCreatingTerm(false);
    }
  };

  const save = async () => {
    if (!editing || !selected) return;
    const name = editing.name.trim();
    if (!name) return;
    setSaving(true);
    try {
      // Only the fields that changed are sent: a form that posts every field
      // would blank a description it never loaded.
      const current =
        editing.kind === "taxonomy"
          ? taxonomies.find((t) => t.id === editing.id)
          : terms.find((t) => t.id === editing.id);
      if (!current) {
        setEditing(null);
        return;
      }
      const slug = editing.slug.trim();
      const description = editing.description.trim();
      if (editing.kind === "taxonomy") {
        const tax = taxonomies.find((t) => t.id === editing.id);
        await taxonomiesApi.update(editing.id, {
          name,
          ...(slug && slug !== tax?.slug ? { slug } : {}),
          ...(description !== (tax?.description ?? "")
            ? { description: description || null }
            : {}),
          // Only when it changed: resending the same list is harmless but would
          // make every rename look like a configuration change.
          ...((!tax ||
            JSON.stringify(editing.object_types) !==
              JSON.stringify(tax.object_types ?? ["blog_post", "cms_page"]))
            ? { object_types: editing.object_types }
            : {}),
        });
      } else {
        // Narrowed here rather than on a shared `current`, because a taxonomy
        // has no parent_id and asking it for one would type-error rather than
        // compile to a wrong value.
        const term = terms.find((t) => t.id === editing.id);
        await taxonomiesApi.updateTerm(selected.id, editing.id, {
          name,
          ...(slug && slug !== term?.slug ? { slug } : {}),
          ...(description !== (term?.description ?? "")
            ? { description: description || null }
            : {}),
          ...(editing.parent_id !== (term?.parent_id ?? "")
            ? { parent_id: editing.parent_id || null }
            : {}),
        });
      }
      setEditing(null);
      await load();
      if (selected) await loadTerms(selected);
      toast({ title: "تغییر ذخیره شد" });
    } catch {
      toast({ title: "ذخیره تغییر ناموفق بود", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const removeTaxonomy = async (tax: CustomTaxonomy) => {
    if (
      !window.confirm(
        `«${tax.name}» و همه‌ی ترم‌های آن حذف می‌شود و ترم‌هایش از نوشته‌ها جدا می‌شوند. این عمل برگشت‌پذیر نیست.`,
      )
    )
      return;
    try {
      const res = await taxonomiesApi.remove(tax.id);
      toast({
        title: "تاکسونومی حذف شد",
        description: `${toPersianDigits(String(res.taxonomies_deleted))} تاکسونومی، ${toPersianDigits(String(res.terms_deleted))} ترم و ${toPersianDigits(String(res.post_links_deleted))} پیوند نوشته حذف شد.`,
      });
      if (selected?.id === tax.id) setSelected(null);
      await load();
    } catch {
      toast({ title: "حذف تاکسونومی ناموفق بود", variant: "destructive" });
    }
  };

  const removeTerm = async (term: CustomTaxonomyTerm) => {
    const kids = terms.filter((t) => t.parent_id === term.id).length;
    const extra = kids > 0 ? ` ${toPersianDigits(String(kids))} زیرترم آن هم حذف می‌شود.` : "";
    const inUse = (term.post_count ?? 0) > 0;
    const useMsg = inUse
      ? ` این ترم روی ${toPersianDigits(String(term.post_count))} نوشته استفاده شده؛ با حذف، از آن نوشته‌ها جدا می‌شود و خود نوشته‌ها دست‌نخورده می‌مانند.`
      : "";
    if (!window.confirm(`«${term.name}» حذف شود؟${extra}${useMsg}`)) return;
    if (!selected) return;
    try {
      const res = await taxonomiesApi.removeTerm(selected.id, term.id);
      toast({
        title: "ترم حذف شد",
        description: `${toPersianDigits(String(res.terms_deleted))} ترم و ${toPersianDigits(String(res.post_links_deleted))} پیوند نوشته حذف شد.`,
      });
      await loadTerms(selected);
    } catch {
      toast({ title: "حذف ترم ناموفق بود", variant: "destructive" });
    }
  };

  /** One editable row, used for both a taxonomy and a term. */
  const editor = (opts: {
    kind: "taxonomy" | "term";
    id: string;
    name: string;
    slug: string;
    description?: string | null;
    parent_id?: string | null;
    showParent?: boolean;
  }) => {
    const isEditing = editing?.kind === opts.kind && editing.id === opts.id;
    if (!isEditing) return null;
    return (
      <div className="grid w-full grid-cols-1 gap-2 sm:grid-cols-2">
        <Input
          value={editing.name}
          autoFocus
          placeholder="نام"
          aria-label="نام"
          onChange={(e) => setEditing({ ...editing, name: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") setEditing(null);
          }}
          className="h-8 text-xs"
        />
        <Input
          value={editing.slug}
          placeholder="اسلاگ"
          aria-label="اسلاگ"
          dir="ltr"
          onChange={(e) => setEditing({ ...editing, slug: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") setEditing(null);
          }}
          className="h-8 text-left font-mono text-xs"
        />
        <Input
          value={editing.description}
          placeholder="توضیح (اختیاری)"
          aria-label="توضیح"
          onChange={(e) => setEditing({ ...editing, description: e.target.value })}
          onKeyDown={(e) => {
            if (e.key === "Enter") void save();
            if (e.key === "Escape") setEditing(null);
          }}
          className="h-8 text-xs sm:col-span-2"
        />
        {opts.kind === "taxonomy" && (
          <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
            <span className="text-[11px] text-muted-foreground">قابل استفاده در:</span>
            {OBJECT_TYPES.map((t) => (
              <label key={t} className="flex items-center gap-1.5 text-[11px]">
                <input
                  type="checkbox"
                  checked={editing.object_types.includes(t)}
                  onChange={(e) =>
                    setEditing({
                      ...editing,
                      object_types: e.target.checked
                        ? [...editing.object_types, t]
                        : editing.object_types.filter((x) => x !== t),
                    })
                  }
                  className="h-3 w-3"
                />
                {OBJECT_LABELS[t]}
              </label>
            ))}
          </div>
        )}
        {opts.showParent && (
          <select
            value={editing.parent_id}
            aria-label="ترم والد"
            onChange={(e) => setEditing({ ...editing, parent_id: e.target.value })}
            className="h-8 rounded-md border border-input bg-background px-2 text-xs sm:col-span-2"
          >
            <option value="">بدون والد (سطح اول)</option>
            {terms
              .filter((t) => t.id !== editing.id)
              .map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name}
                </option>
              ))}
          </select>
        )}
        <div className="flex items-center gap-2 sm:col-span-2">
          <Button size="sm" onClick={() => void save()} disabled={saving}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "ذخیره"}
          </Button>
          <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    );
  };

  const renderTerm = (node: TermNode, depth: number) => {
    const t = node.term;
    const isEditing = editing?.kind === "term" && editing.id === t.id;
    return (
      <li key={t.id}>
        <div
          className="flex items-center gap-2 rounded-lg border border-border/60 px-2 py-1.5"
          style={{ marginInlineStart: `${depth * 14}px` }}
        >
          {isEditing ? (
            editor({
              kind: "term",
              id: t.id,
              name: t.name,
              slug: t.slug,
              description: t.description,
              parent_id: t.parent_id,
              showParent: true,
            })
          ) : (
            <>
              <span className="text-xs">{t.name}</span>
              <span className="text-[10px] text-muted-foreground" dir="ltr">
                /{t.slug}
              </span>
              {t.description && (
                <span className="truncate text-[10px] text-muted-foreground">
                  — {t.description}
                </span>
              )}
              {t.post_count != null && t.post_count > 0 && (
                <span className="text-[10px] text-muted-foreground">
                  {toPersianDigits(String(t.post_count))} نوشته
                </span>
              )}
              <Button
                size="icon"
                variant="ghost"
                aria-label={`ویرایش ${t.name}`}
                className="h-6 w-6"
                onClick={() =>
                  setEditing({
                    kind: "term",
                    id: t.id,
                    name: t.name,
                    slug: t.slug,
                    description: t.description ?? "",
                    parent_id: t.parent_id ?? "",
                    // A term has no content types of its own — they belong to
                    // the taxonomy. Present only because the editor state is
                    // shared; the term branch never reads it.
                    object_types: [],
                  })
                }
              >
                <Pencil className="h-3 w-3" />
              </Button>
              <Button
                size="icon"
                variant="ghost"
                aria-label={`حذف ${t.name}`}
                className="h-6 w-6 text-destructive"
                onClick={() => void removeTerm(t)}
              >
                <Trash2 className="h-3 w-3" />
              </Button>
            </>
          )}
        </div>
        {node.children.length > 0 && (
          <ul className="mt-1 space-y-1">{node.children.map((c) => renderTerm(c, depth + 1))}</ul>
        )}
      </li>
    );
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
              onKeyDown={(e) => {
                if (e.key === "Enter") void handleCreate();
              }}
            />
            <Button size="sm" onClick={() => void handleCreate()} disabled={creating || !newName.trim()}>
              <Plus className="h-4 w-4" />
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-[11px] text-muted-foreground">قابل استفاده در:</span>
            {OBJECT_TYPES.map((t) => (
              <label key={t} className="flex items-center gap-1.5 text-[11px]">
                <input
                  type="checkbox"
                  checked={newObjectTypes.includes(t)}
                  onChange={(e) =>
                    setNewObjectTypes((prev) =>
                      e.target.checked ? [...prev, t] : prev.filter((x) => x !== t),
                    )
                  }
                  className="h-3 w-3"
                />
                {OBJECT_LABELS[t]}
              </label>
            ))}
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
            {taxonomies.map((tax) => {
              const isEditing = editing?.kind === "taxonomy" && editing.id === tax.id;
              return (
                <div key={tax.id} className="flex items-start gap-1">
                  <button
                    type="button"
                    onClick={() => {
                      if (isEditing) return;
                      setSelected(tax);
                      void loadTerms(tax);
                    }}
                    className={`flex flex-1 items-center justify-between rounded-lg border p-3 text-start transition-colors ${
                      selected?.id === tax.id
                        ? "border-primary bg-primary/5"
                        : "border-border hover:bg-muted/50"
                    }`}
                  >
                    <div className="min-w-0">
                      <div className="truncate text-xs font-medium">{tax.name}</div>
                      <div className="text-[11px] text-muted-foreground" dir="ltr">
                        /{tax.slug}
                      </div>
                      {tax.description && (
                        <div className="truncate text-[10px] text-muted-foreground">
                          {tax.description}
                        </div>
                      )}
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      {tax.hierarchical && (
                        <Badge variant="outline" className="text-[10px]">
                          سلسله‌مراتبی
                        </Badge>
                      )}
                      {(tax.object_types ?? ["blog_post", "cms_page"]).map((t) => (
                        <Badge key={t} variant="secondary" className="text-[10px]">
                          {OBJECT_LABELS[t] ?? t}
                        </Badge>
                      ))}
                      <ChevronRight className="h-4 w-4 text-muted-foreground rtl:rotate-180" />
                    </div>
                  </button>
                  {isEditing ? (
                    editor({
                      kind: "taxonomy",
                      id: tax.id,
                      name: tax.name,
                      slug: tax.slug,
                      description: tax.description,
                    })
                  ) : (
                    <div className="flex shrink-0 gap-1">
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`ویرایش ${tax.name}`}
                        className="h-7 w-7"
                        onClick={() =>
                          setEditing({
                            kind: "taxonomy",
                            id: tax.id,
                            name: tax.name,
                            slug: tax.slug,
                            description: tax.description ?? "",
                            parent_id: "",
                            object_types: tax.object_types ?? [
                              "blog_post",
                              "cms_page",
                            ],
                          })
                        }
                      >
                        <Pencil className="h-3 w-3" />
                      </Button>
                      <Button
                        size="icon"
                        variant="ghost"
                        aria-label={`حذف ${tax.name}`}
                        className="h-7 w-7 text-destructive"
                        onClick={() => void removeTaxonomy(tax)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </div>
                  )}
                </div>
              );
            })}
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
            <div className="space-y-2">
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
              {/* Only meaningful for a hierarchical taxonomy; offering a parent
                  picker otherwise would let a term be nested in a taxonomy that
                  does not claim to nest. */}
              {selected.hierarchical && (
                <select
                  value={newTermParent}
                  aria-label="ترم والد"
                  onChange={(e) => setNewTermParent(e.target.value)}
                  className="h-9 w-full rounded-md border border-input bg-background px-2 text-xs"
                >
                  <option value="">بدون والد (سطح اول)</option>
                  {terms.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.name}
                    </option>
                  ))}
                </select>
              )}
            </div>

            <Input
              value={termSearch}
              onChange={(e) => setTermSearch(e.target.value)}
              placeholder="جست‌وجو در ترم‌های این تاکسونومی…"
              aria-label="جست‌وجو در ترم‌ها"
              className="text-xs"
            />

            {termsLoading ? (
              <p className="py-6 text-center text-xs text-muted-foreground">در حال بارگذاری…</p>
            ) : terms.length === 0 ? (
              <p className="py-6 text-center text-xs text-muted-foreground">
                {termSearch.trim()
                  ? `ترمی با «${termSearch.trim()}» پیدا نشد`
                  : "این تاکسونومی هنوز ترمی ندارد."}
              </p>
            ) : (
              <ul className="space-y-1">
                {tree.map((node) => renderTerm(node, 0))}
              </ul>
            )}
          </>
        )}
      </Card>
    </div>
  );
}