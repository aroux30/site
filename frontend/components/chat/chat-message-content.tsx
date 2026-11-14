"use client";

import React from "react";

/**
 * Renders a chat message body with the plugin's markup conventions
 * (`assets/js/admin-chat.js` `formatContent` / `script.js` `fmtC`):
 *
 *  - `[Voice Message](url)`      → an <audio controls> player
 *  - `[Attachment: name](url)`   → an inline <img> for image extensions,
 *                                  otherwise a 📎 file chip linking to the file
 *  - bare `http(s)://…` URLs     → clickable links
 *  - newlines                    → preserved via `whitespace-pre-wrap`
 *
 * The widget already inlined this logic; extracting it here lets the admin
 * console (N1) render voice notes / attachments too, instead of printing the
 * raw `[Voice Message](…)` marker text.
 */

const IMAGE_EXTS = new Set(["jpg", "jpeg", "png", "gif", "webp", "svg", "avif"]);

function isImageUrl(url: string): boolean {
  try {
    const path = url.split("?")[0]?.split("#")[0] ?? "";
    const ext = path.split(".").pop()?.toLowerCase() ?? "";
    return IMAGE_EXTS.has(ext);
  } catch {
    return false;
  }
}

const MARKER_RE = /\[(Voice Message|Attachment: [^\]]+)\]\(([^)]+)\)/g;
const URL_RE = /(https?:\/\/[^\s<>"']+)/g;

export function ChatMessageContent({
  text,
  previewImages = false,
}: {
  text: string;
  /**
   * `true` (admin console) → image attachments render as an inline `<img>`.
   * `false` (visitor widget) → every attachment renders as a 📎 link, matching
   * the widget's original `renderMessage` (script.js `fmtC`). The difference is
   * intentional and preserved via this single flag.
   */
  previewImages?: boolean;
}) {
  if (!text) return null;

  const nodes: React.ReactNode[] = [];
  let key = 0;
  let last = 0;
  let match: RegExpExecArray | null;

  MARKER_RE.lastIndex = 0;
  while ((match = MARKER_RE.exec(text)) !== null) {
    if (match.index > last) {
      nodes.push(linkify(text.slice(last, match.index), () => key++));
    }
    const label = match[1] ?? "";
    const url = match[2] ?? "";
    if (label === "Voice Message") {
      nodes.push(
        <audio key={key++} controls preload="metadata" src={url} className="mt-1 block max-w-[220px]" />,
      );
    } else {
      const name = label.replace("Attachment: ", "");
      if (previewImages && isImageUrl(url)) {
        nodes.push(
          <a key={key++} href={url} target="_blank" rel="noreferrer" className="mt-1 block">
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={name}
              className="max-h-[180px] max-w-[180px] rounded-lg border object-cover"
            />
          </a>,
        );
      } else {
        nodes.push(
          <a
            key={key++}
            href={url}
            target="_blank"
            rel="noreferrer"
            className="mt-1 inline-flex items-center gap-1 rounded-md bg-primary/5 px-2 py-1 text-xs text-primary underline"
          >
            📎 {name}
          </a>,
        );
      }
    }
    last = match.index + match[0].length;
  }
  if (last < text.length) {
    nodes.push(linkify(text.slice(last), () => key++));
  }
  return <div className="whitespace-pre-wrap break-words">{nodes}</div>;
}

/** Turn bare http(s) URLs inside a plain-text chunk into anchor elements. */
function linkify(chunk: string, nextKey: () => number): React.ReactNode {
  if (!chunk) return null;
  const parts: React.ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  URL_RE.lastIndex = 0;
  while ((m = URL_RE.exec(chunk)) !== null) {
    if (m.index > last) parts.push(chunk.slice(last, m.index));
    parts.push(
      <a
        key={nextKey()}
        href={m[0]}
        target="_blank"
        rel="noreferrer"
        className="text-primary underline"
      >
        {m[0]}
      </a>,
    );
    last = m.index + m[0].length;
  }
  if (last < chunk.length) parts.push(chunk.slice(last));
  return parts.length ? <React.Fragment key={nextKey()}>{parts}</React.Fragment> : chunk;
}
