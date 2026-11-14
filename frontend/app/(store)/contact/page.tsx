import type { Metadata } from "next";
import { fetchCmsPage, cmsMetadata } from "@/components/cms/cms-page-shell";
import cleanHtml from "@/lib/sanitize-html";
import ContactFormSection from "./contact-form";

/**
 * Contact page — WordPress page + shortcode parity.
 *
 * The page's copy (title, intro, hours, anything the editor writes) lives in
 * the CMS page `contact` and is editable from /admin/pages like every other
 * storefront page. The message form and contact-info cards stay as a fixed
 * app feature rendered below the CMS body — the equivalent of a WordPress
 * shortcode block, so no editor change can remove the one channel customers
 * can actually message the store through. With no published CMS page the
 * original static header renders, so a fresh install never 404s.
 */

const FALLBACK_TITLE = "تماس با ما";
const FALLBACK_DESCRIPTION =
  "سوال، پیشنهاد یا انتقادی دارید؟ از طریق فرم تماس یا اطلاعات تماس با ما در ارتباط باشید.";

export async function generateMetadata(): Promise<Metadata> {
  const page = await fetchCmsPage("contact");
  if (!page) {
    return {
      title: FALLBACK_TITLE,
      description: FALLBACK_DESCRIPTION,
      alternates: { canonical: "/contact" },
    };
  }
  return {
    ...cmsMetadata(page, FALLBACK_TITLE, FALLBACK_DESCRIPTION),
    // Fixed path wins over the CMS slug.
    alternates: { canonical: "/contact" },
  };
}

export default async function ContactPage() {
  const page = await fetchCmsPage("contact");

  return (
    <div className="container-page">
      {page ? (
        <>
          {/* Editor-owned copy: whatever the operator publishes for `contact`
              renders here, above the fixed form, with the same typography
              classes CmsPageShell uses. */}
          <div className="mx-auto mb-10 max-w-3xl text-center">
            <h1 className="mb-3 text-3xl font-bold text-foreground">
              {page.title}
            </h1>
            <div
              className="cms-content max-w-none leading-8 text-foreground [&_h2]:mt-8 [&_h2]:text-xl [&_h2]:font-bold [&_h3]:mt-6 [&_h3]:text-lg [&_h3]:font-semibold [&_p]:my-4 [&_ul]:my-4 [&_ul]:list-disc [&_ul]:ps-6 [&_ol]:my-4 [&_ol]:list-decimal [&_ol]:ps-6 [&_a]:text-primary [&_a]:underline [&_blockquote]:border-s-4 [&_blockquote]:border-primary/30 [&_blockquote]:ps-4 [&_blockquote]:text-muted-foreground"
              // body_html is editor-authored, but an admin account is not an
              // XSS license — sanitize before dangerouslySetInnerHTML.
              dangerouslySetInnerHTML={{ __html: cleanHtml(page.body_html) }}
            />
          </div>
        </>
      ) : (
        /* Fresh install: no CMS page yet — the original static header. */
        <div className="mb-10 text-center">
          <h1 className="mb-3 text-3xl font-bold text-foreground">
            {FALLBACK_TITLE}
          </h1>
          <p className="mx-auto max-w-lg text-muted-foreground">
            سوال، پیشنهاد یا انتقادی دارید؟ از طریق فرم زیر یا اطلاعات تماس با
            ما در ارتباط باشید.
          </p>
        </div>
      )}

      <ContactFormSection />
    </div>
  );
}
