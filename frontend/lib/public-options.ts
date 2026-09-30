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
