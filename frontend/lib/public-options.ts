/** Server-side reader for the public discussion/visibility options.
 *
 * Fails open (the permissive value) so a backend outage cannot silently
 * deindex the whole blog — the reverse mistake would hide every page from
 * crawlers the moment the API blipped.
 */
import { apiInternalUrl } from "@/lib/api/server-base";

export interface PublicDiscussionOptions {
  commentRegistration: boolean;
  searchVisible: boolean;
}

const DEFAULTS: PublicDiscussionOptions = {
  commentRegistration: false,
  searchVisible: true,
};

export async function fetchPublicDiscussionOptions(): Promise<PublicDiscussionOptions> {
  try {
    const res = await fetch(`${apiInternalUrl()}/settings/public/discussion`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return DEFAULTS;
    const data = (await res.json()) as {
      comment_registration?: boolean;
      search_visible?: boolean;
    };
    return {
      commentRegistration: data.comment_registration === true,
      searchVisible: data.search_visible !== false,
    };
  } catch {
    return DEFAULTS;
  }
}

export interface PublicBreadcrumbOptions {
  homeLabel: string;
  separator: string;
  /** Whether post trails include the "وبلاگ" crumb. */
  showBlog: boolean;
}

const BREADCRUMB_DEFAULTS: PublicBreadcrumbOptions = {
  homeLabel: "خانه",
  separator: "/",
  showBlog: true,
};

/** The breadcrumb display settings; same fail-open shape as discussion. */
export async function fetchPublicBreadcrumbOptions(): Promise<PublicBreadcrumbOptions> {
  try {
    const res = await fetch(`${apiInternalUrl()}/settings/public/breadcrumbs`, {
      next: { revalidate: 300 },
    });
    if (!res.ok) return BREADCRUMB_DEFAULTS;
    const data = (await res.json()) as {
      home_label?: string;
      separator?: string;
      show_blog?: boolean;
    };
    return {
      homeLabel: data.home_label || BREADCRUMB_DEFAULTS.homeLabel,
      separator: data.separator || BREADCRUMB_DEFAULTS.separator,
      showBlog: data.show_blog !== false,
    };
  } catch {
    return BREADCRUMB_DEFAULTS;
  }
}
