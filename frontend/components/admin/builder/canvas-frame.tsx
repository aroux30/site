"use client";

import React, { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { cn } from "@/lib/utils";
import type { Breakpoint } from "@/stores/builder-store";

/**
 * The editor canvas, rendered inside an isolated iframe.
 *
 * The iframe is what makes the responsive preview truthful: `md:`/`lg:` media
 * queries evaluate against the frame's own width (375/768/full), not the
 * editor's browser window.
 *
 * The canvas gets its OWN React root inside the iframe document. That is not
 * an optimisation — it is required. React 18/19 attach their synthetic event
 * listeners to the root container, so a portal from the parent document into
 * an iframe leaves every handler dead: native `pointerdown` fires in the
 * iframe but React's `onPointerDown` never runs, which is exactly why
 * dnd-kit drags could not start. Mounting a root in the iframe document puts
 * the listener target and the DOM in the same document. The Zustand store is
 * module-level, so both roots read and write the same AST.
 */
export function CanvasFrame({
  viewport,
  children,
  className,
}: {
  viewport: Breakpoint;
  children: React.ReactNode;
  className?: string;
}) {
  const iframeRef = useRef<HTMLIFrameElement | null>(null);
  const rootRef = useRef<Root | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const doc = iframe.contentDocument;
    if (!doc) return;

    if (!doc.getElementById("builder-canvas-mount")) {
      doc.open();
      doc.write(
        '<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"/>' +
          '<meta name="viewport" content="width=device-width, initial-scale=1"/>' +
          '<style>body{margin:0;padding:24px;min-height:100vh;box-sizing:border-box;}' +
          'a{pointer-events:none!important;}</style></head>' +
          '<body class="bg-background text-foreground font-sans antialiased">' +
          '<div id="builder-canvas-mount"></div></body></html>'
      );
      doc.close();
    }

    const mount = doc.getElementById("builder-canvas-mount");
    if (!mount) return;

    if (!rootRef.current) {
      rootRef.current = createRoot(mount);
    }

    const sync = () => {
      if (!doc.head || !doc.documentElement) return;
      doc.documentElement.className = document.documentElement.className;
      doc.documentElement.dir = "rtl";
      doc.documentElement.lang = "fa";
      const parentStyle = document.documentElement.getAttribute("style");
      if (parentStyle) doc.documentElement.setAttribute("style", parentStyle);

      const hrefs = new Set(
        Array.from(doc.head.querySelectorAll("link[rel='stylesheet']")).map(
          (l) => (l as HTMLLinkElement).href
        )
      );
      document.querySelectorAll("link[rel='stylesheet']").forEach((link) => {
        const href = (link as HTMLLinkElement).href;
        if (href && !hrefs.has(href)) {
          doc.head.appendChild(link.cloneNode(true));
        }
      });

      const styles = new Set(
        Array.from(doc.head.querySelectorAll("style")).map((s) => s.textContent)
      );
      document.querySelectorAll("style").forEach((style) => {
        if (style.textContent && !styles.has(style.textContent)) {
          doc.head.appendChild(style.cloneNode(true));
        }
      });
    };

    sync();
    setReady(true);

    const themeObserver = new MutationObserver(sync);
    themeObserver.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "dir", "style"],
    });
    const headObserver = new MutationObserver(sync);
    headObserver.observe(document.head, { childList: true, subtree: true });

    return () => {
      themeObserver.disconnect();
      headObserver.disconnect();
    };
  }, []);

  // Render children into the iframe's own root on every change. This root is
  // separate from the parent's, so the parent's React tree never owns those
  // nodes — which is the point.
  useEffect(() => {
    if (!rootRef.current || !ready) return;
    rootRef.current.render(<>{children}</>);
  }, [children, ready]);

  useEffect(() => {
    return () => {
      const root = rootRef.current;
      rootRef.current = null;
      // Unmount after the current commit; unmounting synchronously during a
      // parent unmount trips React's "cannot unmount while rendering" guard.
      setTimeout(() => root?.unmount(), 0);
    };
  }, []);

  // Keep the frame tall enough for its content (no nested scrollbars).
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !ready) return;
    const doc = iframe.contentDocument;
    if (!doc?.body) return;
    const update = () => {
      const h = Math.max(doc.body.scrollHeight, doc.documentElement.scrollHeight, 700);
      iframe.style.height = `${h + 40}px`;
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(doc.body);
    ro.observe(doc.documentElement);
    return () => ro.disconnect();
  }, [children, ready, viewport]);

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
      </div>
    </div>
  );
}
