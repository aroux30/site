"use client";

/**
 * PostTermsPicker — attach custom-taxonomy terms to a post.
 *
 * The attach route and the typed client both existed with no caller, so a
 * custom taxonomy could be created, populated with terms, and then never used:
 * a term could not be attached to anything from the editor. (WordPress calls
 * this the "taxonomy" box on the post editor; here the built-in categories and
 * tags already have their own fields, so this covers the custom ones.)
 *
 * The endpoint *replaces* the post's whole term set rather than adding to it,
 * so this sends the full selection on every save. It therefore only mounts once
 * the post exists — there is no id to attach to before the first save.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { Loader2 } from "lucide-react";
import {
  taxonomiesApi,
  OBJECT_TYPES,
  type CustomTaxonomyTerm,
  type ObjectType,
} from "@/lib/api/wp-parity";
import { useToast } from "@/components/ui/use-toast";
import { toPersianDigits } from "@/lib/utils";

interface PostTermsPickerProps {
  /** Null while the content is being created; nothing can be attached yet. */
  postId: string | null;
  /**
   * Which content type is being edited. The server refuses a term whose
   * taxonomy does not include it, so the picker filters on the same field
   * rather than letting the operator hit that error and guess.
   */
  objectType: ObjectType;
  /** Terms already on the content, so the first paint is not empty. */
  initialTermIds?: string[];
  onChange?: (termIds: string[]) => void;
}

export function PostTermsPicker({
  postId,
  objectType,
  initialTermIds = [],
  onChange,
}: PostTermsPickerProps) {
  const { toast } = useToast();
  const [groups, setGroups] = useState<
    { id: string; name: string; objectTypes: ObjectType[]; terms: CustomTaxonomyTerm[] }[]
  >([]);
  const [selected, setSelected] = useState<string[]>(initialTermIds);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  // Server-side per taxonomy, debounced. Filtering the fetched slice
  // would report "no match" for a term beyond the first page.
  const [searches, setSearches] = useState<Record<string, string>>({});

  const load = useCallback(async (perTaxonomy?: Record<string, string>) => {
    setLoading(true);
    try {
      const taxonomies = await taxonomiesApi.list();
      const loaded = await Promise.all(
        taxonomies.map(async (t) => ({
          id: t.id,
          name: t.name,
          objectTypes: t.object_types ?? ["blog_post", "cms_page"],
          terms: await taxonomiesApi.listTerms(t.id, perTaxonomy?.[t.id]),
        })),
      );
      setGroups(
        loaded.filter(
          (g) =>
            g.terms.length > 0 && g.objectTypes.includes(objectType),
        ),
      );
    } catch {
      // A picker that cannot load must not block the rest of the editor, and
      // must not read as "this post has no terms".
      toast({
        variant: "destructive",
        title: "خواندن تاکسونومی‌های سفارشی ناموفق بود.",
      });
      setGroups([]);
    } finally {
      setLoading(false);
    }
  }, [toast]);

  useEffect(() => {
    void load();
    // Re-runs when the content type changes: the same component edits a post in
    // one place and a page in another, and the applicable taxonomies differ.
  }, [objectType, load]);

  useEffect(() => {
    const anyText = Object.values(searches).some((v) => v.trim());
    if (!anyText) return;
    const t = setTimeout(() => void load(searches), 250);
    return () => clearTimeout(t);
  }, [searches, load]);

  useEffect(() => {
    setSelected(initialTermIds);
  }, [initialTermIds]);

  const toggle = (termId: string) => {
    setSelected((prev) =>
      prev.includes(termId) ? prev.filter((x) => x !== termId) : [...prev, termId],
    );
    onChange?.(
      selected.includes(termId) ? selected.filter((x) => x !== termId) : [...selected, termId],
    );
  };

  const save = async () => {
    if (!postId) return;
    setSaving(true);
    try {
      // Two routes, one contract: both replace the whole set. Sent by content
      // type so a page does not get posted to the blog table and silently
      // lose its terms on the next read.
      if (objectType === "cms_page") {
        await taxonomiesApi.attachToPage(postId, selected);
      } else {
        await taxonomiesApi.attachToPost(postId, selected);
      }
      toast({ title: "ترم‌ها ذخیره شد" });
      await load();
    } catch {
      toast({ variant: "destructive", title: "ذخیره ترم‌ها ناموفق بود." });
    } finally {
      setSaving(false);
    }
  };

  const totalTerms = useMemo(
    () => groups.reduce((n, g) => n + g.terms.length, 0),
    [groups],
  );

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" />
        در حال خواندن تاکسونومی‌ها...
      </div>
    );
  }

  // No custom taxonomy has terms yet: say so rather than rendering an empty
  // box that looks like a control that failed to load.
  if (totalTerms === 0) {
    return (
      <p className="rounded-md border border-dashed border-border p-3 text-xs text-muted-foreground">
        هیچ تاکسونومی سفارشیِ فعال برای این نوع محتوا وجود ندارد. از تب «تاکسونومی‌ها» یک تاکسونومی بسازید و تیک این نوع محتوا را بزنید.
      </p>
    );
  }

  return (
    <div className="space-y-3 rounded-2xl border border-border p-3">
      {groups.map((g) => (
        <div key={g.id} className="space-y-1.5">
          <div className="flex items-center gap-2">
            <p className="text-xs font-bold text-muted-foreground">{g.name}</p>
            <input
              value={searches[g.id] ?? ""}
              aria-label={`جست‌وجو در ${g.name}`}
              placeholder="جست‌وجو…"
              onChange={(e) =>
                setSearches((prev) => ({ ...prev, [g.id]: e.target.value }))
              }
              className="h-7 flex-1 rounded-md border border-input bg-background px-2 text-[11px]"
            />
          </div>
          <div className="flex flex-wrap gap-1.5">
            {g.terms.map((t) => {
              const on = selected.includes(t.id);
              return (
                <button
                  key={t.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggle(t.id)}
                  className={
                    "rounded-full border px-2.5 py-0.5 text-[11px] transition " +
                    (on
                      ? "border-primary bg-primary/10 font-medium text-primary"
                      : "border-border text-muted-foreground hover:border-primary/40")
                  }
                >
                  {t.name}
                </button>
              );
            })}
            {g.terms.length === 0 && searches[g.id]?.trim() && (
              <span className="text-[11px] text-muted-foreground">
                ترمی با این نام پیدا نشد.
              </span>
            )}
          </div>
        </div>
      ))}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => void save()}
          disabled={!postId || saving}
          className="rounded-md border border-input px-3 py-1 text-xs font-medium disabled:opacity-60"
          title={
            postId
              ? "کل ترم‌های این نوشته با این انتخاب جایگزین می‌شوند"
              : "پس از اولین ذخیره می‌توانید ترم وصل کنید"
          }
        >
          {saving ? "در حال ذخیره..." : "ذخیره ترم‌ها"}
        </button>
        <span className="text-[11px] text-muted-foreground">
          {toPersianDigits(String(selected.length))} ترم انتخاب شده
          {postId
            ? " — ذخیره، انتخاب‌های قبلی را جایگزین می‌کند."
            : " — برای اتصال، اول نوشته را ذخیره کنید."}
        </span>
      </div>
    </div>
  );
}
