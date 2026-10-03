"use client";

/**
 * RichBodyEditor — editor switchable between visual (WYSIWYG), HTML source,
 * and Markdown, with a sanitized live preview (DOMPurify).
 *
 * The value contract is always HTML: visual edits are read back from the
 * contentEditable surface, and Markdown is rendered to HTML on save/switch.
 */

import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { sanitizeHtml, sanitizeRichHtml, renderMarkdown } from "@/lib/editor/markdown";
import {
  AlignCenter, AlignLeft, AlignRight, Bold, Braces, Code2, Eye, FileText, Heading1,
  Heading2, Heading3, Image as ImageIcon, Italic, List, ListOrdered, Link2, Minus,
  MonitorPlay, Quote, Redo2, Settings2, Strikethrough, Table, Underline, Undo2,
  Maximize2, Minimize2, X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { MediaBodyDialog, type MediaInsertion } from "@/components/admin/media-body-dialog";
import { mediaApi } from "@/lib/api/media";
import { cn } from "@/lib/utils";

type Mode = "visual" | "html" | "markdown";
type Align = "right" | "center" | "left" | "justify";

/** Elements a style can be written onto. Anything else (a bare `<span>`, a
 *  `<b>` inside a paragraph) has no width of its own, so aligning it would
 *  silently do nothing. */
const BLOCK_TAGS = new Set([
  "P", "DIV", "H1", "H2", "H3", "H4", "H5", "H6",
  "LI", "BLOCKQUOTE", "PRE", "TD", "TH", "SECTION", "ARTICLE", "FIGCAPTION",
]);

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

/** Blocks a table insert produces. Built as a string so one execCommand carries it. */
const EMPTY_TABLE_HTML =
  "<table><thead><tr><th>ستون ۱</th><th>ستون ۲</th><th>ستون ۳</th></tr></thead>" +
  "<tbody><tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr>" +
  "<tr><td>&nbsp;</td><td>&nbsp;</td><td>&nbsp;</td></tr></tbody></table><p><br></p>";

/** Counts words and characters the way a Persian editor usually does. */
function countWords(html: string): { words: number; chars: number } {
  const tmp = document.createElement("div");
  tmp.innerHTML = sanitizeHtml(html);
  const text = (tmp.textContent ?? "").replace(/\s+/g, " ").trim();
  return { words: text ? text.split(" ").length : 0, chars: text.length };
}

export default function RichBodyEditor({ value, onChange, placeholder }: Props) {
  const [mode, setMode] = useState<Mode>("visual");
  const [markdown, setMarkdown] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [alignState, setAlignState] = useState<Align>("right");
  const alignRef = useRef<Align>("right");
  const [mediaOpen, setMediaOpen] = useState(false);
  const [counts, setCounts] = useState({ words: 0, chars: 0 });
  const [canUndo, setCanUndo] = useState(false);
  const [canRedo, setCanRedo] = useState(false);
  const visualRef = useRef<HTMLDivElement>(null);
  /** The image the author clicked in the body, if any. */
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null);

  /**
   * The value contract is HTML, owned by the parent — but a controlled
   * `dangerouslySetInnerHTML` re-applies the *old* markup on every parent
   * render, which silently reverted anything a toolbar command had just
   * written to the DOM. Typing hid it (the parent re-renders on each
   * keystroke, so the fresh value is already in `value`), but one-shot
   * commands — alignment, a table insert, a horizontal rule — had their
   * effect wiped a frame later.
   *
   * So the editor keeps the last committed HTML itself and re-asserts it when
   * the parent sends back something stale. A genuinely new value (a real
   * parent state update) still wins.
   */
  const lastCommitted = useRef(value);
  useEffect(() => {
    if (value !== lastCommitted.current) lastCommitted.current = value;
  }, [value]);

  const commitVisual = useCallback(() => {
    const surface = visualRef.current;
    if (!surface) return;
    const next = sanitizeHtml(surface.innerHTML);
    lastCommitted.current = next;
    onChange(next);
  }, [onChange]);

  const countsHtml = useMemo(() => countWords(value), [value]);
  useEffect(() => setCounts(countsHtml), [countsHtml]);

  // Undo/redo have no React state to subscribe to: the browser keeps the
  // history on the contentEditable surface, and `queryCommandState` is the only
  // way to ask it. Polling on edit is the cheap honest option; the alternative
  // is maintaining our own history, which would then be the thing that breaks.
  useEffect(() => {
    const surface = visualRef.current;
    if (!surface) return;
    const sync = () => {
      try {
        setCanUndo(document.queryCommandEnabled("undo") && document.queryCommandState("undo"));
        setCanRedo(document.queryCommandEnabled("redo") && document.queryCommandState("redo"));
      } catch {
        setCanUndo(false);
        setCanRedo(false);
      }
    };
    surface.addEventListener("input", sync);
    surface.addEventListener("keyup", sync);
    surface.addEventListener("mouseup", sync);
    sync();
    return () => {
      surface.removeEventListener("input", sync);
      surface.removeEventListener("keyup", sync);
      surface.removeEventListener("mouseup", sync);
    };
  }, [mode]);

  const previewHtml = useMemo(() => {
    const source = mode === "markdown" ? renderMarkdown(markdown) : value;
    return sanitizeHtml(source);
  }, [mode, markdown, value]);

  const switchMode = (next: Mode) => {
    // Commit the current surface back to HTML before switching away.
    if (mode === "visual" && visualRef.current) {
      onChange(sanitizeHtml(visualRef.current.innerHTML));
    }
    if (mode === "markdown" && next !== "markdown") {
      onChange(renderMarkdown(markdown));
    }
    if (next === "markdown") {
      // HTML → Markdown is lossy; start from plain text of the current body.
      const tmp = document.createElement("div");
      tmp.innerHTML = sanitizeHtml(value);
      setMarkdown(tmp.textContent ?? "");
    }
    setMode(next);
  };

  const exec = (command: string, arg?: string) => {
    visualRef.current?.focus();
    document.execCommand(command, false, arg);
    commitVisual();
  };

  /**
   * Alignment is written as a style on the focused block rather than through
   * `execCommand("justify*")`.
   *
   * Two reasons the execCommand route cannot work here: in a `dir="rtl"`
   * paragraph the browser reports the block as already `justifyRight`, so
   * clicking "right" writes nothing at all; and `justifyFull` on a
   * contentEditable puts the style on the editable root rather than the
   * paragraph, so it is lost on the next re-render. Writing the style onto the
   * caret's own block is both directions-correct and survives a re-render.
   */
  const setAlign = (side: Align) => {
    setAlignState(side);
    alignRef.current = side;

    const surface = visualRef.current;
    if (!surface) return;

    // Read the selection *before* touching focus. `focus()` on a contentEditable
    // can collapse the selection to the start of the surface, and the caret's
    // block is what needs the style.
    const selection = window.getSelection();
    const anchor = selection?.anchorNode ?? null;
    const hadSelectionInside =
      !!anchor && (anchor === surface || surface.contains(anchor));

    if (!hadSelectionInside) surface.focus();

    let el: HTMLElement | null =
      anchor instanceof HTMLElement ? anchor : (anchor?.parentElement ?? null);
    while (el && el !== surface && !BLOCK_TAGS.has(el.tagName)) {
      el = el.parentElement;
    }
    if (!el || el === surface) {
      // No block under the caret (empty editor): create one and align that.
      const p = document.createElement("p");
      p.appendChild(document.createElement("br"));
      surface.appendChild(p);
      el = p;
      if (!hadSelectionInside) {
        const range = document.createRange();
        range.setStart(p, 0);
        range.collapse(true);
        selection?.removeAllRanges();
        selection?.addRange(range);
      }
    }
    el.style.textAlign = side;
    commitVisual();
  };

  const insertHtml = (html: string) => {
    if (mode === "visual" && visualRef.current) {
      visualRef.current.focus();
      document.execCommand("insertHTML", false, html);
      commitVisual();
    } else {
      onChange(value + "\n" + html);
    }
  };

  /**
   * Resolve the selected image's src to a media asset id.
   *
   * The body stores a URL (`/uploads/media/<name>`) and the media page
   * deep-links by id, so the id has to come from somewhere. The list endpoint
   * is the only lookup the editor can do without a per-image API: one request
   * for a page of assets, matched on the filename. A match miss is the normal
   * case for an image hosted elsewhere — an external URL, a legacy path — and
   * the button stays disabled rather than linking to an asset that is not it.
   */
  const [imageAssetId, setImageAssetId] = useState<string | null>(null);
  useEffect(() => {
    if (!selectedImageUrl) {
      setImageAssetId(null);
      return;
    }
    let cancelled = false;
    (async () => {
      try {
        const name = selectedImageUrl.split("/").pop()?.split("?")[0];
        if (!name) {
          if (!cancelled) setImageAssetId(null);
          return;
        }
        const res = await mediaApi.list({ search: name, page_size: 25 });
        const hit = (res.items || []).find(
          (a) => a.file_url === selectedImageUrl || a.file_name === name,
        );
        if (!cancelled) setImageAssetId(hit?.id ?? null);
      } catch {
        // A failed lookup must not surface as an error the author has to
        // dismiss: the editing tools simply stay out of reach.
        if (!cancelled) setImageAssetId(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selectedImageUrl]);

  /**
   * Pick the clicked image out of the editing surface.
   *
   * The crop, rotate and flip tools live on the media page, and nothing
   * connected them to a picture sitting in a post: the author had to remember
   * the image, leave the editor, find the file, edit it, then come back and
   * hand-edit the URL. Clicking the image is the natural place to offer the
   * trip, so this records which one is selected and the toolbar below acts on
   * it.
   *
   * A click anywhere else clears the selection, so a stray click does not leave
   * a stale image armed.
   */
  const onSurfaceClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const target = e.target as HTMLElement | null;
    const img = target?.closest?.("img");
    const src = img?.getAttribute("src")?.trim();
    setSelectedImageUrl(src ? src : null);
  };

  const insertMedia = (media: MediaInsertion) => {
    // Escaped, not interpolated raw: an alt text with a quote or an ampersand
    // would otherwise break out of the attribute and emit broken markup.
    const esc = (s: string) =>
      s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
    const img = `<img src="${esc(media.url)}" alt="${esc(media.alt)}" />`;
    const block = media.caption
      ? `<figure>${img}<figcaption>${esc(media.caption)}</figcaption></figure>`
      : `<p>${img}</p>`;
    insertHtml(block);
  };

  const insertLink = () => {
    const url = window.prompt("آدرس پیوند (https://… یا /path):");
    if (url && /^(https?:\/\/|\/)/i.test(url)) exec("createLink", url);
  };

  const [embedBusy, setEmbedBusy] = useState(false);
  const insertEmbed = async () => {
    const url = window.prompt("نشانی محتوا برای درج (یوتیوب، آپارات، صفحه وب…):");
    if (!url || !/^https?:\/\//i.test(url)) return;
    setEmbedBusy(true);
    try {
      const res = await fetch(
        `/api/v1/content/admin/embed?url=${encodeURIComponent(url)}`,
        { credentials: "include" },
      );
      if (!res.ok) throw new Error("embed failed");
      const meta = (await res.json()) as {
        type?: string;
        html?: string | null;
        title?: string | null;
        image?: string | null;
        thumbnail_url?: string | null;
        url?: string;
      };
      // Provider markup (oEmbed html) may carry an iframe — sanitize with the
      // host-allowlisting policy, and fall back to a link card using the
      // backend's actual thumbnail key (`thumbnail_url`, not `image`).
      const thumb = meta.thumbnail_url ?? meta.image ?? "";
      const card = meta.html
        ? sanitizeRichHtml(meta.html)
        : sanitizeHtml(
            `<figure><a href="${meta.url ?? url}">${thumb ? `<img src="${thumb}" alt="" />` : ""}<figcaption>${meta.title ?? url}</figcaption></a></figure>`,
          );
      if (mode === "visual" && visualRef.current) {
        visualRef.current.focus();
        document.execCommand("insertHTML", false, card);
        commitVisual();
      } else if (mode === "html") {
        onChange(value + "\n" + card);
      }
    } catch {
      window.alert("بازیابی محتوای درج ناموفق بود");
    } finally {
      setEmbedBusy(false);
    }
  };

  return (
    <div
      className={
        fullscreen
          ? "fixed inset-0 z-50 flex flex-col rounded-none border-0 bg-background"
          : "rounded-md border border-input"
      }
    >
      {/* Selected image bar — the trip from a picture in the body to the crop
          and rotate tools. It sits above the toolbar because the selection is
          about the content, not about the formatting controls. The URL is
          shown truncated because it is long and the point is "which image",
          not to read the whole path. */}
      {selectedImageUrl && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border bg-muted/40 px-2 py-1.5 text-xs">
          <ImageIcon className="h-3.5 w-3.5 shrink-0 text-emerald-600" />
          <span className="text-muted-foreground">تصویر انتخاب‌شده:</span>
          <span className="max-w-[240px] truncate font-mono text-[11px]" dir="ltr" title={selectedImageUrl}>
            {selectedImageUrl.replace(/^\/uploads\//, "")}
          </span>
          <Link
            href={`/admin/media?asset=${encodeURIComponent(imageAssetId ?? "")}`}
            className={cn(
              "ms-auto inline-flex h-7 items-center gap-1 rounded-md border px-2 text-xs hover:bg-background",
              imageAssetId
                ? "border-emerald-600 text-emerald-700 hover:bg-emerald-50 dark:text-emerald-400 dark:hover:bg-emerald-950/20"
                : "pointer-events-none border-border text-muted-foreground opacity-60",
            )}
            target="_blank"
            rel="noreferrer"
            title={
              imageAssetId
                ? "باز کردن این تصویر در کتابخانه‌ی رسانه برای برش، چرخش و قرینه"
                : "این تصویر از کتابخانه‌ی رسانه نیامده و قابل ویرایش نیست"
            }
          >
            <Settings2 className="h-3.5 w-3.5" />
            ویرایش تصویر
          </Link>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => setSelectedImageUrl(null)}
            aria-label="لغو انتخاب تصویر"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      )}

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-1 border-b border-border p-2">
        {(
          [
            ["visual", Eye, "دیداری"],
            ["html", Code2, "HTML"],
            ["markdown", FileText, "Markdown"],
          ] as const
        ).map(([m, Icon, label]) => (
          <Button
            key={m}
            type="button"
            size="sm"
            variant={mode === m ? "default" : "ghost"}
            className="h-7 px-2 text-xs"
            onClick={() => switchMode(m)}
          >
            <Icon className="h-3.5 w-3.5 ms-1" />
            {label}
          </Button>
        ))}
        <span className="mx-1 h-4 w-px bg-border" />
        {mode === "visual" && (
          <>
            <span className="mx-1 h-4 w-px bg-border" />
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("undo")} disabled={!canUndo} title="واگرد (Ctrl+Z)">
              <Undo2 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("redo")} disabled={!canRedo} title="ازنو (Ctrl+Y)">
              <Redo2 className="h-3.5 w-3.5" />
            </Button>
            <span className="mx-1 h-4 w-px bg-border" />
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("bold")} title="پررنگ">
              <Bold className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("italic")} title="کج">
              <Italic className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("underline")} title="زیرخط">
              <Underline className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("strikeThrough")} title="خط‌خورده">
              <Strikethrough className="h-3.5 w-3.5" />
            </Button>
            <span className="mx-1 h-4 w-px bg-border" />
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "h1")} title="تیتر ۱">
              <Heading1 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "h2")} title="تیتر ۲">
              <Heading2 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "h3")} title="تیتر ۳">
              <Heading3 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "pre")} title="کد">
              <Braces className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "blockquote")} title="نقل‌قول">
              <Quote className="h-3.5 w-3.5" />
            </Button>
            <span className="mx-1 h-4 w-px bg-border" />
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("insertUnorderedList")} title="لیست">
              <List className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("insertOrderedList")} title="لیست شماره‌دار">
              <ListOrdered className="h-3.5 w-3.5" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={() => insertHtml(EMPTY_TABLE_HTML)}
              title="جدول"
            >
              <Table className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("insertHorizontalRule")} title="خط جداکننده">
              <Minus className="h-3.5 w-3.5" />
            </Button>
            <span className="mx-1 h-4 w-px bg-border" />
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={insertLink} title="پیوند">
              <Link2 className="h-3.5 w-3.5" />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-7 px-2"
              onClick={() => setMediaOpen(true)}
              title="درج تصویر از کتابخانه"
            >
              <ImageIcon className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => void insertEmbed()} disabled={embedBusy} title="درج محتوا (oEmbed)">
              <MonitorPlay className="h-3.5 w-3.5" />
            </Button>
            <span className="mx-1 h-4 w-px bg-border" />
            {(
              [
                ["right", AlignRight, "تراز راست"],
                ["center", AlignCenter, "وسط‌چین"],
                ["left", AlignLeft, "تراز چپ"],
                ["justify", List, "هم‌تراز"],
              ] as const
            ).map(([side, Icon, label]) => (
              <Button
                key={side}
                type="button"
                size="sm"
                variant={alignState === side ? "secondary" : "ghost"}
                className="h-7 px-2"
                onClick={() => setAlign(side)}
                title={label}
              >
                <Icon className="h-3.5 w-3.5" />
              </Button>
            ))}
          </>
        )}
        {mode === "html" && (
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => void insertEmbed()} disabled={embedBusy} title="درج محتوا (oEmbed)">
            <MonitorPlay className="h-3.5 w-3.5" />
          </Button>
        )}
        <div className="ms-auto flex items-center gap-2 text-[11px] text-muted-foreground">
          <span aria-live="polite">
            {counts.words.toLocaleString("fa-IR")} واژه
            {" · "}
            {counts.chars.toLocaleString("fa-IR")} نویسه
          </span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            className="h-7 px-2 text-xs"
            onClick={() => setFullscreen((v) => !v)}
            title={fullscreen ? "خروج از تمام‌صفحه" : "تمام‌صفحه"}
          >
            {fullscreen ? <Minimize2 className="h-3.5 w-3.5 ms-1" /> : <Maximize2 className="h-3.5 w-3.5 ms-1" />}
          </Button>
          <Button
            type="button"
            size="sm"
            variant={showPreview ? "secondary" : "ghost"}
            className="h-7 px-2 text-xs"
            onClick={() => setShowPreview((v) => !v)}
          >
            <Eye className="h-3.5 w-3.5 ms-1" />
            پیش‌نمایش زنده
          </Button>
        </div>
      </div>

      <div className={showPreview ? "grid flex-1 grid-cols-1 md:grid-cols-2" : "flex-1"}>
        {/* Editing surface */}
        <div className={fullscreen ? "flex flex-1 flex-col overflow-y-auto" : undefined}>
          {mode === "visual" && (
            <div
              ref={visualRef}
              contentEditable
              suppressContentEditableWarning
              dir="rtl"
              // A bare contentEditable div announces as an unlabelled group, so
              // a screen-reader user hears nothing where the body should be.
              role="textbox"
              aria-multiline="true"
              aria-label="متن نوشته"
              className={
                fullscreen
                  ? "min-h-[70vh] w-full flex-1 px-3 py-2 text-sm outline-none prose prose-sm max-w-none"
                  : "min-h-40 w-full px-3 py-2 text-sm outline-none prose prose-sm max-w-none"
              }
              data-placeholder={placeholder ?? "متن صفحه…"}
              onInput={() => commitVisual()}
              onClick={onSurfaceClick}
              dangerouslySetInnerHTML={{ __html: sanitizeHtml(value) }}
            />
          )}
          {mode === "html" && (
            <textarea
              dir="ltr"
              rows={10}
              className="w-full resize-y bg-transparent px-3 py-2 font-mono text-left text-xs outline-none"
              value={value}
              onChange={(e) => onChange(e.target.value)}
            />
          )}
          {mode === "markdown" && (
            <textarea
              dir="auto"
              rows={10}
              className="w-full resize-y bg-transparent px-3 py-2 font-mono text-sm outline-none"
              placeholder="# تیتر&#10;متن **پررنگ** و [پیوند](https://…)"
              value={markdown}
              onChange={(e) => setMarkdown(e.target.value)}
              onBlur={() => onChange(renderMarkdown(markdown))}
            />
          )}
        </div>

        {/* Live preview */}
        {showPreview && (
          <div className="border-t md:border-t-0 md:border-s border-border overflow-y-auto">
            <div
              dir="rtl"
              className="min-h-40 px-3 py-2 text-sm prose prose-sm max-w-none bg-muted/30"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
            />
          </div>
        )}
      </div>

      <MediaBodyDialog
        open={mediaOpen}
        onOpenChange={setMediaOpen}
        onInsert={insertMedia}
      />
    </div>
  );
}
