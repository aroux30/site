"use client";

import React, { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import type { Breakpoint } from "@/stores/builder-store";

interface CanvasFrameProps {
  viewport: Breakpoint;
  children: React.ReactNode;
  className?: string;
}

export function CanvasFrame({
  viewport,
  children,
  className,
}: CanvasFrameProps) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const [mountNode, setMountNode] = useState<HTMLElement | null>(null);
  const [iframeDoc, setIframeDoc] = useState<Document | null>(null);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    const doc = iframe.contentDocument;
    if (!doc) return;

    if (!doc.getElementById("builder-canvas-mount")) {
      doc.open();
      doc.write(
        '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>body { min-height: 100vh; padding: 24px; box-sizing: border-box; } a { pointer-events: none !important; }</style></head><body class="bg-background text-foreground font-sans antialiased p-0 m-0 min-h-screen"><div id="builder-canvas-mount"></div></body></html>'
      );
      doc.close();
    }

    const mount = doc.getElementById("builder-canvas-mount");
    setMountNode(mount);
    setIframeDoc(doc);

    // Synchronize parent document styles (Tailwind CSS, fonts, dark theme)
    const syncHeadAndStyles = () => {
      if (!doc.head || !doc.documentElement) return;

      doc.documentElement.className = document.documentElement.className;
      doc.documentElement.dir = document.documentElement.dir || "rtl";
      doc.documentElement.lang = "fa";

      const parentStyle = document.documentElement.getAttribute("style");
      if (parentStyle) {
        doc.documentElement.setAttribute("style", parentStyle);
      }

      // Clone parent stylesheets
      const existingHrefs = new Set(
        Array.from(doc.head.querySelectorAll("link[rel='stylesheet']")).map(
          (l) => (l as HTMLLinkElement).href
        )
      );

      document.querySelectorAll("link[rel='stylesheet']").forEach((link) => {
        const href = (link as HTMLLinkElement).href;
        if (href && !existingHrefs.has(href)) {
          const clone = link.cloneNode(true) as HTMLLinkElement;
          doc.head.appendChild(clone);
        }
      });

      // Clone inline style tags
      const existingStyleTexts = new Set(
        Array.from(doc.head.querySelectorAll("style")).map((s) => s.textContent)
      );
      document.querySelectorAll("style").forEach((style) => {
        if (style.textContent && !existingStyleTexts.has(style.textContent)) {
          const clone = style.cloneNode(true);
          doc.head.appendChild(clone);
        }
      });
    };

    syncHeadAndStyles();

    const themeObserver = new MutationObserver(() => syncHeadAndStyles());
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "dir", "style"],
    });

    const headObserver = new MutationObserver(() => syncHeadAndStyles());
    headObserver.observe(document.head, { childList: true, subtree: true });

    return () => {
      themeObserver.disconnect();
      headObserver.disconnect();
    };
  }, []);

  // Dynamically adjust iframe height to match content
  useEffect(() => {
    if (!iframeRef.current || !iframeDoc) return;
    const iframe = iframeRef.current;
    const doc = iframeDoc;

    const updateHeight = () => {
      if (!iframe || !doc.body) return;
      const h = Math.max(
        doc.body.scrollHeight,
        doc.documentElement.scrollHeight,
        700
      );
      iframe.style.height = `${h + 40}px`;
    };

    updateHeight();
    const ro = new ResizeObserver(() => updateHeight());
    if (doc.body) ro.observe(doc.body);
    if (doc.documentElement) ro.observe(doc.documentElement);

    return () => {
      ro.disconnect();
    };
  }, [iframeDoc, children, viewport]);

  return (
    <div className={cn("relative w-full flex justify-center py-6 px-4", className)}>
      <div
        className={cn(
          "transition-all duration-300 w-full overflow-hidden rounded-xl shadow-lg border border-border bg-background",
          viewport === "desktop" && "max-w-full",
          viewport === "tablet" && "max-w-[768px]",
          viewport === "mobile" && "max-w-[375px]"
        )}
      >
        <iframe
          ref={iframeRef}
          title="Visual Builder Canvas"
          className="w-full border-0 block bg-background"
          style={{ minHeight: "750px" }}
        />
        {mountNode && createPortal(children, mountNode)}
      </div>
    </div>
  );
}
