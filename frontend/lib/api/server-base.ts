/**
 * Base URL for server-side (Node/SSR) calls to the backend API.
 *
 * A relative URL is invalid outside the browser, so server components must
 * call the backend on an absolute origin. The correct origin differs by
 * environment — localhost for `npm run dev`, the compose service name inside
 * Docker — and this previously lived as three different env var names
 * (`INTERNAL_API_URL`, `API_INTERNAL_URL`, `NEXT_PUBLIC_API_BASE_URL`)
 * scattered across five files, two of which disagreed about whether the value
 * already ended in `/api/v1`. An unset var therefore silently fell through to
 * the Docker-only hostname `backend` and every CMS-backed page rendered empty
 * on a local dev machine while the API itself was healthy.
 *
 * One resolver, one canonical value: `API_INTERNAL_URL`, including the
 * `/api/v1` suffix so every caller builds paths the same way.
 */

/** Backend origin including the API prefix, e.g. `http://localhost:8000/api/v1`. */
export function apiInternalUrl(): string {
  const raw =
    process.env.API_INTERNAL_URL ||
    // Legacy names kept working so an existing deployment env is not broken by
    // the consolidation; both are expected to include the /api/v1 suffix too.
    process.env.INTERNAL_API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000/api/v1";
  // Tolerate a bare origin (`http://backend:8000`) by appending the prefix,
  // never by dropping it — callers below assume the suffix is present.
  const trimmed = raw.replace(/\/+$/, "");
  return /\/api\/v\d+$/.test(trimmed) ? trimmed : `${trimmed}/api/v1`;
}
