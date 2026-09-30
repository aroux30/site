"use client";

/**
 * RichBodyEditor — editor switchable between visual (WYSIWYG), HTML source,
 * and Markdown, with a sanitized live preview (DOMPurify).
 *
 * The value contract is always HTML: visual edits are read back from the
 * contentEditable surface, and Markdown is rendered to HTML on save/switch.
 */

import React, { useMemo, useRef, useState } from "react";
import { sanitizeHtml, sanitizeRichHtml, renderMarkdown } from "@/lib/editor/markdown";
import { Bold, Italic, List, ListOrdered, Link2, Heading2, Eye, Code2, FileText, MonitorPlay } from "lucide-react";
import { Button } from "@/components/ui/button";

type Mode = "visual" | "html" | "markdown";

interface Props {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
}

export default function RichBodyEditor({ value, onChange, placeholder }: Props) {
  const [mode, setMode] = useState<Mode>("visual");
  const [markdown, setMarkdown] = useState("");
  const [showPreview, setShowPreview] = useState(false);
  const visualRef = useRef<HTMLDivElement>(null);

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
    if (visualRef.current) onChange(sanitizeHtml(visualRef.current.innerHTML));
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
        onChange(sanitizeHtml(visualRef.current.innerHTML));
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
    <div className="rounded-md border border-input">
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
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("bold")} title="پررنگ">
              <Bold className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("italic")} title="کج">
              <Italic className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("formatBlock", "h2")} title="تیتر">
              <Heading2 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("insertUnorderedList")} title="لیست">
              <List className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => exec("insertOrderedList")} title="لیست شماره‌دار">
              <ListOrdered className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={insertLink} title="پیوند">
              <Link2 className="h-3.5 w-3.5" />
            </Button>
            <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => void insertEmbed()} disabled={embedBusy} title="درج محتوا (oEmbed)">
              <MonitorPlay className="h-3.5 w-3.5" />
            </Button>
          </>
        )}
        {mode === "html" && (
          <Button type="button" size="sm" variant="ghost" className="h-7 px-2" onClick={() => void insertEmbed()} disabled={embedBusy} title="درج محتوا (oEmbed)">
            <MonitorPlay className="h-3.5 w-3.5" />
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant={showPreview ? "secondary" : "ghost"}
          className="h-7 px-2 text-xs ms-auto"
          onClick={() => setShowPreview((v) => !v)}
        >
          <Eye className="h-3.5 w-3.5 ms-1" />
          پیش‌نمایش زنده
        </Button>
      </div>

      <div className={showPreview ? "grid grid-cols-1 md:grid-cols-2" : ""}>
        {/* Editing surface */}
        <div>
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
              className="min-h-40 w-full px-3 py-2 text-sm outline-none prose prose-sm max-w-none"
              data-placeholder={placeholder ?? "متن صفحه…"}
              onInput={() => {
                if (visualRef.current) onChange(sanitizeHtml(visualRef.current.innerHTML));
              }}
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
          <div className="border-t md:border-t-0 md:border-s border-border">
            <div
              dir="rtl"
              className="min-h-40 px-3 py-2 text-sm prose prose-sm max-w-none bg-muted/30"
              dangerouslySetInnerHTML={{ __html: previewHtml }}
            />
          </div>
        )}
      </div>
    </div>
  );
}
