import type { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import {
  contentTypesPublicApi,
  type ContentTypeField,
  type PublicContentEntry,
} from "@/lib/api/cms-admin";

/** Archive page for a custom post type.
 *
 *  WordPress archives whatever the operator registered as a post type: a
 *  portfolio, a testimonial, an event list. Here `GET
 *  /content-types/{slug}/entries` existed and nothing called it, so a type the
 *  operator had carefully filled was unreachable on the storefront — the entry
 *  existed and nothing showed it.
 *
 *  The field schema drives the rendering rather than dumping `data` as JSON,
 *  because a page of key/value pairs is not a page. Declared order is kept:
 *  the operator arranged the fields when they defined the type.
 */

/** Seconds. Long enough to absorb an upload round-trip per request, short
 *  enough that publishing an entry is visible without a redeploy. */
export const revalidate = 60;

interface PageProps {
  params: Promise<{ slug: string }>;
}

function fieldLabel(fields: ContentTypeField[], key: string): string {
  return fields.find((f) => f.key === key)?.label ?? key;
}

function fieldValue(value: unknown): string | null {
  if (value === null || value === undefined || value === "") return null;
  if (Array.isArray(value)) return value.join("، ");
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function renderEntry(entry: PublicContentEntry, fields: ContentTypeField[]) {
  const declared = fields.filter((f) => entry.data?.[f.key] !== undefined);
  // A field the operator typed after the entries were written has nothing to
  // show. Render whatever the entry does carry, in declared order, then
  // anything left over — so an entry is never a blank card because a field was
  // added later.
  const seen = new Set(declared.map((f) => f.key));
  const rest = Object.keys(entry.data ?? {}).filter((k) => !seen.has(k));

  return (
    <article
      key={entry.id}
      className="rounded-lg border border-border bg-card p-5 shadow-sm"
    >
      {declared.length === 0 && rest.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          این مورد هنوز محتوایی ندارد.
        </p>
      ) : (
        <dl className="space-y-2">
          {[...declared.map((f) => f.key), ...rest].map((key) => {
            const shown = fieldValue(entry.data?.[key]);
            if (shown === null) return null;
            const label = fieldLabel(fields, key);
            return (
              <div key={key} className="grid gap-1 sm:grid-cols-[9rem_1fr]">
                <dt className="text-xs font-medium text-muted-foreground">
                  {label}
                </dt>
                <dd className="text-sm leading-7 break-words">{shown}</dd>
              </div>
            );
          })}
        </dl>
      )}
    </article>
  );
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const types = await contentTypesPublicApi.list().catch(() => []);
  const found = types.find((t) => t.slug === slug);
  if (!found) return { title: "یافت نشد" };
  return {
    title: found.name,
    description: found.description ?? undefined,
    // A type archive is a listing, not a thing that should be indexed as a
    // single page of text.
    openGraph: { title: found.name },
  };
}

export default async function ContentTypeArchivePage({ params }: PageProps) {
  const { slug } = await params;

  const [types, entries] = await Promise.all([
    contentTypesPublicApi.list(),
    contentTypesPublicApi.entries(slug).catch(() => [] as PublicContentEntry[]),
  ]);
  const type = types.find((t) => t.slug === slug);
  if (!type) notFound();

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-8" dir="rtl">
      <nav className="mb-4 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          خانه
        </Link>
        <span className="mx-1">/</span>
        <span>{type.name}</span>
      </nav>

      <header className="mb-6">
        <h1 className="text-2xl font-bold">{type.name}</h1>
        {type.description && (
          <p className="mt-2 text-sm text-muted-foreground">
            {type.description}
          </p>
        )}
      </header>

      {entries.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          در حال حاضر موردی در این بخش منتشر نشده است.
        </p>
      ) : (
        <div className="space-y-3">
          {entries.map((entry) => renderEntry(entry, type.field_schema))}
        </div>
      )}
    </div>
  );
}