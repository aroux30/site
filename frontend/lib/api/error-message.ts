/**
 * One way to turn a failed request into the sentence an operator reads.
 *
 * The backend answers with `error.message` on most modules and FastAPI's
 * `detail` on the older ones; the API client (`lib/api/client.ts`) additionally
 * pre-extracts the same text onto `err.message`. Pages that read only one of
 * those shapes threw the server's actual reason away and showed a generic
 * sentence instead — so an operator could not tell "this document does not
 * exist" from "you may not read this document" from "the service is down".
 * Several `catch {}` blocks did not bind the error at all, which lost the
 * message outright.
 *
 * Call this from any catch block that ends in user-visible text, and always
 * pass a fallback: an unexpected error type must still say something.
 */
export function apiErrorMessage(err: unknown, fallback: string): string {
  const e = err as
    | {
        message?: unknown;
        response?: {
          data?: {
            detail?: unknown;
            message?: unknown;
            error?: { message?: unknown };
          };
        };
      }
    | null
    | undefined;

  const candidates = [
    e?.response?.data?.error?.message,
    e?.response?.data?.message,
    e?.response?.data?.detail,
    e?.message,
  ];
  for (const c of candidates) {
    // FastAPI validation errors arrive as a list under `detail`; surface the
    // first entry's message rather than "[object Object]".
    if (typeof c === "string" && c.trim()) return c;
    if (Array.isArray(c) && c.length > 0) {
      const first = c[0] as { msg?: unknown } | undefined;
      if (first && typeof first.msg === "string" && first.msg.trim()) {
        return first.msg;
      }
    }
  }
  return fallback;
}
