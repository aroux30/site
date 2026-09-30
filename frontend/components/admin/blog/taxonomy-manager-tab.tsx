"use client";

/** Blog categories and tags.
 *
 * Neither had an admin screen: the list was fetched for the post filter and
 * nothing could rename or remove an entry, so the taxonomy could only grow.
 * This tab is where both are created, edited and deleted.
 *
 * Deleting a category orphans its posts rather than destroying them — the
 * response says how many, and the confirm states it before the call.
 */
import { useCallback, useEffect, useState } from "react";
import { Loader2, Pencil, Plus, Tag, Trash2, X, FolderTree } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";
import { fetchCategoryTree, fetchBlogCategories, fetchBlogTags, blogTaxonomyApi } from "@/lib/api/blog";
import type { BlogPostCategory, BlogTag } from "@/lib/api/blog";
import { toPersianDigits } from "@/lib/utils";

type Kind = "category" | "tag";

/** Flatten the forest into <option> rows, indenting by depth. */
function flattenTree(
  nodes: BlogPostCategory[],
  depth = 0,
): { id: string; label: string }[] {
  return nodes.flatMap((n) => [
    { id: n.id, label: `${"— ".repeat(depth)}${n.name}` },
    ...flattenTree(n.children ?? [], depth + 1),
  ]);
}


export function TaxonomyManagerTab() {
  const { toast } = useToast();
  const [categories, setCategories] = useState<BlogPostCategory[]>([]);
  const [tree, setTree] = useState<BlogPostCategory[]>([]);
  const [tags, setTags] = useState<BlogTag[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [newName, setNewName] = useState<Record<Kind, string>>({ category: "", tag: "" });
  const [newParent, setNewParent] = useState("");
  const [editing, setEditing] = useState<{ kind: Kind; id: string; name: string } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [c, t, tr] = await Promise.all([
        fetchBlogCategories(),
        fetchBlogTags(),
        fetchCategoryTree(),
      ]);
      setCategories(c);
      setTags(t);
      setTree(tr);
    } catch {
      toast({ variant: "destructive", title: "خواندن دسته‌بندی‌ها ناموفق بود." });
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
  }, [load]);

  const create = async (kind: Kind) => {
    const name = (newName[kind] || "").trim();
    if (!name) return;
    setBusy(`create-${kind}`);
    try {
      await fetch(`/admin/blog/${kind === "category" ? "categories" : "tags"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          kind === "category" ? { name, parent_id: newParent || null } : { name },
        ),
      });
      setNewName((v) => ({ ...v, [kind]: "" }));
      await load();
      toast({ title: kind === "category" ? "دسته‌بندی ساخته شد." : "برچسب ساخته شد." });
    } catch {
      toast({ variant: "destructive", title: "ساختن آن ناموفق بود." });
    } finally {
      setBusy(null);
    }
  };

  const save = async () => {
    if (!editing) return;
    const name = editing.name.trim();
    if (!name) return;
    setBusy(`edit-${editing.id}`);
    try {
      if (editing.kind === "category") {
        await blogTaxonomyApi.updateCategory(editing.id, { name });
      } else {
        await blogTaxonomyApi.updateTag(editing.id, { name });
      }
      setEditing(null);
      await load();
      toast({ title: "تغییر ذخیره شد." });
    } catch {
      toast({ variant: "destructive", title: "ذخیره تغییر ناموفق بود." });
    } finally {
      setBusy(null);
    }
  };

  const remove = async (kind: Kind, id: string, name: string, count: number) => {
    const verb = kind === "category" ? "دسته‌بندی" : "برچسب";
    const message =
      count > 0
        ? `«${name}» ${toPersianDigits(count)} نوشته دارد. با حذف آن نوشته‌ها حذف نمی‌شوند و فقط از این ${verb} جدا می‌شوند. مطمئنید؟`
        : `«${name}» حذف شود؟`;
    if (!window.confirm(message)) return;

    setBusy(`del-${id}`);
    try {
      const res =
        kind === "category"
          ? await blogTaxonomyApi.deleteCategory(id)
          : await blogTaxonomyApi.deleteTag(id);
      await load();
      toast({
        title: `${verb} حذف شد.`,
        description:
          res.orphaned_posts > 0
            ? `${toPersianDigits(res.orphaned_posts)} نوشته بدون ${verb} باقی ماند.`
            : undefined,
      });
    } catch {
      toast({ variant: "destructive", title: `حذف ${verb} ناموفق بود.` });
    } finally {
      setBusy(null);
    }
  };

  const renderRow = (
    kind: Kind,
    item: { id: string; name: string; post_count?: number; parent_id?: string | null },
  ) => {
    const isEditing = editing?.kind === kind && editing.id === item.id;
    return (
      <li
        key={item.id}
        className="flex items-center gap-2 border-b border-border/50 py-2 last:border-0"
      >
        {isEditing ? (
          <>
            <Input
              value={editing.name}
              autoFocus
              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
              onKeyDown={(e) => {
                if (e.key === "Enter") void save();
                if (e.key === "Escape") setEditing(null);
              }}
              className="h-8"
            />
            <Button size="sm" onClick={() => void save()} disabled={busy === `edit-${item.id}`}>
              {busy === `edit-${item.id}` ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                "ذخیره"
              )}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>
              <X className="h-3.5 w-3.5" />
            </Button>
          </>
        ) : (
          <>
            <span className="flex-1 truncate text-sm">{item.name}</span>
            {item.parent_id && (
              <span className="text-xs text-muted-foreground">
                زیرمجموعهٔ{" "}
                {categories.find((c) => c.id === item.parent_id)?.name ?? "—"}
              </span>
            )}
            {item.post_count != null && (
              <span className="text-xs text-muted-foreground">
                {toPersianDigits(item.post_count)} نوشته
              </span>
            )}
            <Button
              size="icon"
              variant="ghost"
              aria-label={`ویرایش ${item.name}`}
              onClick={() => setEditing({ kind, id: item.id, name: item.name })}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
            <Button
              size="icon"
              variant="ghost"
              aria-label={`حذف ${item.name}`}
              disabled={busy === `del-${item.id}`}
              onClick={() => void remove(kind, item.id, item.name, item.post_count ?? 0)}
            >
              {busy === `del-${item.id}` ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Trash2 className="h-3.5 w-3.5 text-destructive" />
              )}
            </Button>
          </>
        )}
      </li>
    );
  };

  const renderSection = (kind: Kind, title: string, items: typeof categories, icon: React.ReactNode) => (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {icon}
          {title}
        </CardTitle>
        <CardDescription>
          {kind === "category"
            ? "دسته‌ها برای سازمان‌دهی نوشته‌ها و آرشیو /blog/category هستند."
            : "برچسب‌ها موضوع نوشته را نشان می‌دهند و آرشیو /blog/tag می‌سازند."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Input
            className="min-w-[12rem] flex-1"
            value={newName[kind]}
            onChange={(e) => setNewName((v) => ({ ...v, [kind]: e.target.value }))}
            onKeyDown={(e) => {
              if (e.key === "Enter") void create(kind);
            }}
            placeholder={kind === "category" ? "نام دسته‌بندی تازه" : "نام برچسب تازه"}
          />
          {kind === "category" && tree.length > 0 && (
            <select
              value={newParent}
              onChange={(e) => setNewParent(e.target.value)}
              aria-label="دسته‌بندی والد"
              className="rounded-md border border-input bg-background px-3 py-2 text-sm"
            >
              <option value="">بدون والد (سطح اول)</option>
              {flattenTree(tree).map((o) => (
                <option key={o.id} value={o.id}>
                  {o.label}
                </option>
              ))}
            </select>
          )}
          <Button
            onClick={() => void create(kind)}
            disabled={!newName[kind]?.trim() || busy === `create-${kind}`}
          >
            {busy === `create-${kind}` ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            افزودن
          </Button>
        </div>
        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">موردی ثبت نشده است.</p>
        ) : (
          <ul className="list-none">{items.map((i) => renderRow(kind, i))}</ul>
        )}
      </CardContent>
    </Card>
  );

  if (loading) {
    return (
      <div className="flex justify-center p-10">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      {renderSection("category", "دسته‌بندی‌ها", categories, <FolderTree className="h-4 w-4" />)}
      {renderSection("tag", "برچسب‌ها", tags, <Tag className="h-4 w-4" />)}
    </div>
  );
}
