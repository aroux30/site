import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchCustomTaxonomyTerms } from "@/lib/api/blog";

/** Archive for a custom taxonomy.
 *
 *  WordPress registers a third vocabulary — beyond categories and tags — and
 *  archives it at `/<taxonomy>/<term>`. `GET /blog/taxonomies/{slug}/terms`
 *  existed here with no caller, so a store that registered "product type" or
 *  "brand" had a taxonomy and no page: the operator built the vocabulary,
 *  assigned terms to products, and nothing an shopper could reach.
 *
 *  The page lists the taxonomy's terms rather than one term's posts. The public
 *  route returns terms and not posts, so a term archive that listed posts
 *  would have to invent the link it filters on — and an archive whose links go
 *  nowhere is the failure this item was written about.
 *
 *  Terms are rendered with their description, which is the one field an
 *  operator writes on a term and the only place on this page a shopper learns
 *  what the vocabulary means.
 */

export const revalidate = 120;

interface Props {
  params: Promise<{ taxonomy: string }>;
}

async function loadTerms(taxonomy: string) {
  try {
    return await fetchCustomTaxonomyTerms(taxonomy);
  } catch {
    // A taxonomy whose slug has been retired answers 404 or 500. Either way
    // this page has nothing to show, and a thrown error would take the whole
    // store's error reporting with it for one missing archive.
    return null;
  }
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { taxonomy } = await params;
  const terms = await loadTerms(taxonomy);
  if (!terms || terms.length === 0) return { title: "یافت نشد" };
  const title = terms[0]?.name ?? taxonomy;
  return {
    title,
    description:
      "دسته‌بندی‌های این بخش از فروشگاه.",
    alternates: { canonical: `/${taxonomy}` },
  };
}

export default async function CustomTaxonomyArchivePage({ params }: Props) {
  const { taxonomy } = await params;
  const terms = await loadTerms(taxonomy);
  if (!terms) {
    // Distinguish "this taxonomy is gone" from "this taxonomy is empty":
    // a 404 tells a shopper the address is wrong, which is a different thing
    // from a section with nothing in it yet.
    notFound();
  }

  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-8" dir="rtl">
      <nav className="mb-4 text-xs text-muted-foreground">
        <Link href="/" className="hover:text-foreground">
          خانه
        </Link>
        <span className="mx-1">/</span>
        <span>{terms[0]?.name ?? taxonomy}</span>
      </nav>

      <header className="mb-6">
        <h1 className="text-2xl font-bold">
          {terms[0]?.name ?? taxonomy}
        </h1>
        {terms[0]?.description && (
          <p className="mt-2 text-sm text-muted-foreground">
            {terms[0].description}
          </p>
        )}
      </header>

      {terms.length === 0 ? (
        <p className="rounded-lg border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          در این دسته‌بندی هنوز موردی ثبت نشده است.
        </p>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {terms.map((term) => (
            <li key={term.id}>
              <Link
                href={`/${taxonomy}/${term.slug}`}
                className="block rounded-lg border border-border bg-card p-4 shadow-sm transition-colors hover:border-primary"
              >
                <span className="block font-medium">{term.name}</span>
                {term.description && (
                  <span className="mt-1 block text-xs text-muted-foreground">
                    {term.description}
                  </span>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}