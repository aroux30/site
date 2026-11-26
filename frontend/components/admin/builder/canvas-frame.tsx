"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";
import { useBuilderStore, type Breakpoint } from "@/stores/builder-store";
import { themesAdminApi } from "@/lib/api/themes";
import { extractCssVariablesFromTokens, hexToHslChannels } from "@/lib/builder/theme-schema";
import { CanvasOverlayLayer } from "./canvas-overlay-layer";

const INITIAL_CANVAS_HTML = `<!DOCTYPE html><html lang="fa" dir="rtl"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>body{margin:0;padding:36px 24px 24px 24px;min-height:100vh;box-sizing:border-box;position:relative;}a{pointer-events:none!important;}@keyframes builderFadeIn{from{opacity:0;}to{opacity:1;}}@keyframes builderSlideUp{from{opacity:0;transform:translateY(20px);}to{opacity:1;transform:translateY(0);}}@keyframes builderZoomIn{from{opacity:0;transform:scale(0.95);}to{opacity:1;transform:scale(1);}}.builder-animate-fade-in{animation:builderFadeIn 0.6s cubic-bezier(0.16,1,0.3,1) both;}.builder-animate-slide-up{animation:builderSlideUp 0.6s cubic-bezier(0.16,1,0.3,1) both;}.builder-animate-zoom-in{animation:builderZoomIn 0.6s cubic-bezier(0.16,1,0.3,1) both;}</style></head><body class="bg-background text-foreground font-sans antialiased relative"><div id="builder-canvas-mount"></div><div id="builder-overlay-mount" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99990;"></div></body></html>`;

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
  const [mountNode, setMountNode] = useState<HTMLElement | null>(null);
  const [overlayNode, setOverlayNode] = useState<HTMLElement | null>(null);
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

  const syncStyles = useCallback((doc: Document) => {
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
        doc.documentElement.style.setProperty(`${key}-hex`, String(val));
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
      doc.documentElement.style.setProperty("--primary-hex", pVal);
    } else {
      doc.documentElement.style.removeProperty("--theme-primary");
      doc.documentElement.style.removeProperty("--primary-hex");
    }
    if (gs?.secondaryColor) {
      const sVal = String(gs.secondaryColor);
      doc.documentElement.style.setProperty("--secondary", sVal.startsWith("#") ? hexToHslChannels(sVal) : sVal);
      doc.documentElement.style.setProperty("--theme-secondary", sVal);
      doc.documentElement.style.setProperty("--secondary-hex", sVal);
    } else {
      doc.documentElement.style.removeProperty("--theme-secondary");
      doc.documentElement.style.removeProperty("--secondary-hex");
    }
    if (gs?.borderRadius) {
      doc.documentElement.style.setProperty("--radius", String(gs.borderRadius));
    } else {
      doc.documentElement.style.removeProperty("--radius");
    }
    if (gs?.fontFamily === "system-ui") {
      doc.documentElement.style.setProperty("--font-vazirmatn", "system-ui, sans-serif");
    } else if (gs?.fontFamily) {
      doc.documentElement.style.setProperty("--font-vazirmatn", String(gs.fontFamily));
    } else {
      doc.documentElement.style.removeProperty("--font-vazirmatn");
    }
    if (gs?.textColor) {
      const tVal = String(gs.textColor);
      doc.documentElement.style.setProperty("--foreground", tVal.startsWith("#") ? hexToHslChannels(tVal) : tVal);
      doc.documentElement.style.setProperty("--theme-foreground", tVal);
      doc.documentElement.style.setProperty("--foreground-hex", tVal);
    } else {
      doc.documentElement.style.removeProperty("--theme-foreground");
      doc.documentElement.style.removeProperty("--foreground-hex");
    }
    if (gs?.backgroundColor) {
      const bVal = String(gs.backgroundColor);
      doc.documentElement.style.setProperty("--background", bVal.startsWith("#") ? hexToHslChannels(bVal) : bVal);
      doc.documentElement.style.setProperty("--theme-background", bVal);
      doc.documentElement.style.setProperty("--background-hex", bVal);
    } else {
      doc.documentElement.style.removeProperty("--theme-background");
      doc.documentElement.style.removeProperty("--background-hex");
    }
    if (gs?.contentMaxWidth) {
      doc.documentElement.style.setProperty("--content-max-width", String(gs.contentMaxWidth));
    }
  }, [activeThemeVars]);

  const initIframe = useCallback(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc) return;

    let mount = doc.getElementById("builder-canvas-mount");
    let overlay = doc.getElementById("builder-overlay-mount");

    if (!mount && doc.body) {
      mount = doc.createElement("div");
      mount.id = "builder-canvas-mount";
      doc.body.appendChild(mount);
    }
    if (!overlay && doc.body) {
      overlay = doc.createElement("div");
      overlay.id = "builder-overlay-mount";
      overlay.style.cssText = "position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:99990;";
      doc.body.appendChild(overlay);
    }

    if (!mount) return;

    syncStyles(doc);
    setMountNode(mount);
    setOverlayNode(overlay);
    setReady(true);

    const handleDragOver = (e: DragEvent) => {
      e.preventDefault();
      if (e.dataTransfer) {
        const isMove = e.dataTransfer.effectAllowed === "move";
        e.dataTransfer.dropEffect = isMove ? "move" : "copy";
      }
    };
    doc.addEventListener("dragover", handleDragOver);

    // Forward keyboard events (Ctrl+Z, Ctrl+Y, Ctrl+C, Ctrl+V, Delete) to parent window
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      const isInput =
        targetTag === "input" ||
        targetTag === "textarea" ||
        (e.target as HTMLElement)?.isContentEditable;
      if (isInput) return;

      window.dispatchEvent(
        new KeyboardEvent(e.type, {
          key: e.key,
          code: e.code,
          ctrlKey: e.ctrlKey,
          metaKey: e.metaKey,
          shiftKey: e.shiftKey,
          altKey: e.altKey,
          bubbles: true,
          cancelable: true,
        })
      );
    };
    doc.addEventListener("keydown", handleKeyDown);

    const handleContextMenu = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      const elemContainer = target?.closest("[data-element-id]");
      if (elemContainer) {
        e.preventDefault();
        const targetId = elemContainer.getAttribute("data-element-id");
        const iframeRect = iframe.getBoundingClientRect();
        window.postMessage(
          {
            type: "builder:contextmenu",
            targetId,
            clientX: iframeRect.left + e.clientX,
            clientY: iframeRect.top + e.clientY,
          },
          "*"
        );
      }
    };
    doc.addEventListener("contextmenu", handleContextMenu);

    return () => {
      doc.removeEventListener("dragover", handleDragOver);
      doc.removeEventListener("keydown", handleKeyDown);
      doc.removeEventListener("contextmenu", handleContextMenu);
    };
  }, [syncStyles]);

  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe) return;

    let cleanup: (() => void) | undefined = initIframe();

    const onLoad = () => {
      if (cleanup) cleanup();
      cleanup = initIframe();
    };

    iframe.addEventListener("load", onLoad);
    return () => {
      iframe.removeEventListener("load", onLoad);
      if (cleanup) cleanup();
    };
  }, [initIframe]);

  // Two-Layer Design Tokens Injection updates
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !ready) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc?.documentElement) return;
    syncStyles(doc);
  }, [activeThemeVars, globalStyles, ready, syncStyles]);

  // Live dark mode and style synchronization from parent document to canvas iframe
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !ready) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
    if (!doc?.documentElement) return;

    const observer = new MutationObserver(() => {
      doc.documentElement.className = document.documentElement.className;
      const parentStyle = document.documentElement.getAttribute("style");
      if (parentStyle) doc.documentElement.setAttribute("style", parentStyle);
    });

    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class", "style"],
    });

    return () => observer.disconnect();
  }, [ready]);

  // Keep the frame tall enough for its content (no nested scrollbars).
  useEffect(() => {
    const iframe = iframeRef.current;
    if (!iframe || !ready) return;
    const doc = iframe.contentDocument || iframe.contentWindow?.document;
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
          srcDoc={INITIAL_CANVAS_HTML}
          data-testid="canvas-iframe"
          title="Visual Builder Canvas"
          className="w-full border-0 block bg-background"
          style={{ minHeight: "750px" }}
        />
        {mountNode && createPortal(children, mountNode)}
        {overlayNode && createPortal(<CanvasOverlayLayer doc={iframeRef.current?.contentDocument || null} />, overlayNode)}
      </div>
    </div>
  );
}
