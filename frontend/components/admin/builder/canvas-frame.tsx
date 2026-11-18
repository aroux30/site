"use client";

import React, { useEffect, useRef, useState } from "react";
import { createRoot, type Root } from "react-dom/client";
import { cn } from "@/lib/utils";
import { useBuilderStore, type Breakpoint } from "@/stores/builder-store";
import { themesAdminApi } from "@/lib/api/themes";
import { extractCssVariablesFromTokens, hexToHslChannels } from "@/lib/builder/theme-schema";

/**
 * The editor canvas, rendered inside an isolated iframe.
 *
 * The iframe is what makes the responsive preview truthful: `md:`/`lg:` media
 * queries evaluate against the frame's own width (375/768/full), not the
 * editor's browser window.
 *
 * Implements two-layer design token inheritance:
 * Layer 1 (Base): Active SiteTheme variables loaded automatically from backend.
 * Layer 2 (Override): Page-level globalStyles applied on top.
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
  const [activeThemeVars, setActiveThemeVars] = useState<Record<string, string>>({});
  const globalStyles = useBuilderStore((s) => s.ast.globalStyles);

  // Fetch active site theme as Layer 1 base tokens
  useEffect(() => {
    let isMounted = true;
    themesAdminApi
      .getActive()
      .then((theme) => {
        if (isMounted && theme?.tokens) {
          const vars = extractCssVariablesFromTokens(theme.tokens);
          setActiveThemeVars(vars);
        }
      })
      .catch((err) => {
        console.warn("Failed to load active site theme for CanvasFrame:", err);
      });
    return () => {
      isMounted = false;
    };
  }, []);

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
          '<style>body{margin:0;padding:36px 24px 24px 24px;min-height:100vh;box-sizing:border-box;}' +
          'a{pointer-events:none!important;}' +
          '@keyframes builderFadeIn{from{opacity:0;}to{opacity:1;}}' +
          '@keyframes builderSlideUp{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}' +
          '@keyframes builderZoomIn{from{opacity:0;transform:scale(0.95);}to{opacity:1;transform:scale(1);}}' +
          '.builder-animate-fade-in{animation:builderFadeIn 0.6s cubic-bezier(0.16,1,0.3,1) both;}' +
          '.builder-animate-slide-up{animation:builderSlideUp 0.6s cubic-bezier(0.16,1,0.3,1) both;}' +
          '.builder-animate-zoom-in{animation:builderZoomIn 0.6s cubic-bezier(0.16,1,0.3,1) both;}' +
          '</style></head>' +
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

      // Two-Layer Design Tokens:
      // Layer 1 (Base): Active SiteTheme variables
      const hslKeys = new Set(["--primary", "--secondary", "--background", "--foreground", "--border", "--muted", "--ring", "--input", "--card", "--popover"]);
      for (const [key, val] of Object.entries(activeThemeVars)) {
        if (hslKeys.has(key) && String(val).startsWith("#")) {
          doc.documentElement.style.setProperty(key, hexToHslChannels(String(val)));
          doc.documentElement.style.setProperty(`--theme-${key.slice(2)}`, String(val));
        } else {
          doc.documentElement.style.setProperty(key, val);
        }
      }

      // Layer 2 (Override): Page-level globalStyles
      const gs = useBuilderStore.getState().ast.globalStyles;
      if (gs?.primaryColor) {
        const pVal = String(gs.primaryColor);
        doc.documentElement.style.setProperty("--primary", pVal.startsWith("#") ? hexToHslChannels(pVal) : pVal);
        doc.documentElement.style.setProperty("--theme-primary", pVal);
      }
      if (gs?.secondaryColor) {
        const sVal = String(gs.secondaryColor);
        doc.documentElement.style.setProperty("--secondary", sVal.startsWith("#") ? hexToHslChannels(sVal) : sVal);
        doc.documentElement.style.setProperty("--theme-secondary", sVal);
      }
      if (gs?.borderRadius) {
        doc.documentElement.style.setProperty("--radius", String(gs.borderRadius));
      }
      if (gs?.fontFamily === "system-ui") {
        doc.documentElement.style.setProperty("--font-vazirmatn", "system-ui, sans-serif");
      } else if (gs?.fontFamily) {
        doc.documentElement.style.setProperty("--font-vazirmatn", String(gs.fontFamily));
      }
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

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer) {
        const isMove = e.dataTransfer.effectAllowed === "move";
        e.dataTransfer.dropEffect = isMove ? "move" : "copy";
      }
    };
    doc.addEventListener("dragover", handleDragOver);

    return () => {
      doc.removeEventListener("dragover", handleDragOver);
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

  // Two-Layer Design Tokens Injection:
  // Layer 1 (Base): Active SiteTheme variables
  // Layer 2 (Override): Page-level globalStyles
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !ready) return;
    const doc = iframe.contentDocument;
    if (!doc?.documentElement) return;

    // Apply Layer 1
    for (const [key, val] of Object.entries(activeThemeVars)) {
      doc.documentElement.style.setProperty(key, val);
    }

    // Apply Layer 2 (Override)
    if (globalStyles?.primaryColor) {
      doc.documentElement.style.setProperty("--primary", String(globalStyles.primaryColor));
    }
    if (globalStyles?.secondaryColor) {
      doc.documentElement.style.setProperty("--secondary", String(globalStyles.secondaryColor));
    }
    if (globalStyles?.borderRadius) {
      doc.documentElement.style.setProperty("--radius", String(globalStyles.borderRadius));
    }
    if (globalStyles?.fontFamily === "system-ui") {
      doc.documentElement.style.setProperty("--font-vazirmatn", "system-ui, sans-serif");
    } else if (globalStyles?.fontFamily) {
      doc.documentElement.style.setProperty("--font-vazirmatn", String(globalStyles.fontFamily));
    }
  }, [activeThemeVars, globalStyles, ready]);

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
