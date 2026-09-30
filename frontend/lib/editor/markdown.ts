/**
 * Pure Markdown → sanitized HTML renderer plus the shared DOMPurify policy
 * for CMS bodies. Kept free of React imports so it is unit-testable and
 * reusable outside components.
 */

import createDOMPurify from "dompurify";

import {
  ALLOWED_ATTR,
  ALLOWED_TAGS,
  ALLOWED_URI_REGEXP,
  EMBED_HOST_RE,
} from "./allowlist";

type Sanitizer = { sanitize: (dirty: string, opts?: object) => string };

// DOMPurify v3's default export is a factory that also carries a self-bound
// instance in browser builds. In Node (vitest) only the factory exists and it
// needs a window-like global; jsdom/happy-dom provide one in test envs, and
// Next.js renders this module client-side only.
const DOMPurify: Sanitizer = (() => {
  const factory = createDOMPurify as unknown as {
    (win?: unknown): Sanitizer;
    sanitize?: Sanitizer["sanitize"];
  };
  if (typeof factory.sanitize === "function") {
    return factory as unknown as Sanitizer;
  }
  const win = (globalThis as { window?: unknown }).window;
  return win ? factory(win) : { sanitize: (dirty: string) => dirty };
})();

// Tags and attributes come from the shared allowlist. This list used to be
// local and narrower than the server's by 45 tags, which meant the editor
// unwrapped the app's own block patterns (`section`, `div`, `details`) on the
// first keystroke after insertion.
const SANITIZE_OPTS = {
  ALLOWED_TAGS,
  ALLOWED_ATTR,
  ALLOWED_URI_REGEXP,
};

export { EMBED_HOST_RE };

export function sanitizeRichHtml(html: string): string {
  const clean = sanitizeHtml(html);
  // Second pass: drop iframes not on the allowlist (DOMPurify's URI regex
  // is global for all attributes, so host filtering happens here). Both the
  // opening and any leftover closing tag go.
  return clean
    .replace(/<iframe([^>]*?)src="([^"]*)"([^>]*)>/gi, (match, before, src, after) =>
      EMBED_HOST_RE.test(src) ? match : "",
    )
    .replace(/<\/iframe>/gi, "");
}

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html, SANITIZE_OPTS);
}

/** Minimal Markdown → HTML (headings, bold/italic, links, lists, code, quotes). */
export function renderMarkdown(md: string): string {
  const esc = (s: string) =>
    s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  const inline = (s: string) =>
    esc(s)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+|\/[^)\s]*)\)/g, '<a href="$2">$1</a>');

  const lines = md.split(/\r?\n/);
  const out: string[] = [];
  let listType: "ul" | "ol" | null = null;
  let inCode = false;
  const codeBuf: string[] = [];

  const closeList = () => {
    if (listType) {
      out.push(`</${listType}>`);
      listType = null;
    }
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`);
        codeBuf.length = 0;
        inCode = false;
      } else {
        closeList();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuf.push(line);
      continue;
    }
    const t = line.trim();
    if (!t) {
      closeList();
      continue;
    }
    const heading = /^(#{1,4})\s+(.*)$/.exec(t);
    if (heading) {
      closeList();
      const level = heading[1]?.length ?? 2;
      out.push(`<h${level}>${inline(heading[2] ?? "")}</h${level}>`);
      continue;
    }
    if (/^>\s?/.test(t)) {
      closeList();
      out.push(`<blockquote>${inline(t.replace(/^>\s?/, ""))}</blockquote>`);
      continue;
    }
    const ul = /^[-*]\s+(.*)$/.exec(t);
    const ol = /^\d+[.)]\s+(.*)$/.exec(t);
    if (ul || ol) {
      const want = ul ? "ul" : "ol";
      if (listType !== want) {
        closeList();
        out.push(`<${want}>`);
        listType = want;
      }
      out.push(`<li>${inline((ul ?? ol)?.[1] ?? "")}</li>`);
      continue;
    }
    closeList();
    out.push(`<p>${inline(t)}</p>`);
  }
  closeList();
  if (inCode) out.push(`<pre><code>${esc(codeBuf.join("\n"))}</code></pre>`);
  return sanitizeHtml(out.join("\n"));
}
