"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useShopFeatures } from "@/hooks/use-shop-features";
import { fetchChatConfig } from "@/lib/api/chat";

/**
 * Loads the WordPress plugin's VERBATIM frontend (`/chat-plugin.js`) — the
 * owner's directive: «همه چیز عین وردپرس» / copy the plugin UI, don't rebuild it
 * in React. The plugin JS builds the whole widget (FAB, halos, ring, window,
 * views, composer, emoji, voice, quick-flow) from inline styles and talks to the
 * backend only through `window.n8nChat.ajax_url` — pointed here at our bridge
 * (`/api/v1/chat/plugin-bridge`).
 *
 * Gating: nothing loads unless the `chat` shop-feature switch is on AND the
 * widget config is enabled — so a disabled install never renders a dead FAB.
 */

declare global {
  interface Window {
    n8nChat?: {
      ajax_url: string;
      nonce: string;
      user: { id?: number; name?: string; email?: string };
      settings: Record<string, unknown>;
    };
    jQuery?: unknown;
    $?: unknown;
  }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-chat-plugin="${src}"]`)) {
      resolve();
      return;
    }
    const s = document.createElement("script");
    s.src = src;
    s.async = false;
    s.dataset.chatPlugin = src;
    s.onload = () => resolve();
    s.onerror = () => reject(new Error(`failed to load ${src}`));
    document.body.appendChild(s);
  });
}

export function PluginWidgetLoader() {
  const pathname = usePathname();
  const features = useShopFeatures();
  const [ready, setReady] = useState(false);
  const [isBuilder, setIsBuilder] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const sp = new URLSearchParams(window.location.search);
      const isB =
        sp.get("visual_editor") === "true" ||
        sp.get("visual_editor") === "1" ||
        sp.get("edit") === "true" ||
        sp.get("edit") === "1" ||
        sp.get("builder") === "1" ||
        sp.get("builder") === "true";
      setIsBuilder(isB);
    }
  }, [pathname]);

  // WordPress parity: the chat widget is a front-end feature — wp-admin and
  // the visual page builder studio never show it. The plugin appends its #n8n-w
  // root straight to <body>, OUTSIDE the React tree, so walking into the builder
  // or admin would otherwise leave the FAB floating over the studio controls.
  const isStorefront = !pathname.startsWith("/admin") && !isBuilder;

  // Mounted in the ROOT layout: the loader keeps watching the route and
  // toggles the plugin's body-level widget on every admin ⇄ storefront move.
  useEffect(() => {
    const widgetRoot = document.getElementById("n8n-w");
    if (widgetRoot) widgetRoot.style.display = isStorefront ? "" : "none";
  }, [isStorefront, ready]);

  useEffect(() => {
    if (!features.chat || !isStorefront) return;
    let cancelled = false;

    (async () => {
      try {
        const cfg = await fetchChatConfig();
        if (cancelled || !cfg.enabled) return;

        // The plugin reads `S = n8nChat.settings` (its own defaults, e.g.
        // color_primary || '#007ACC'). Our config mirrors the key names, but the
        // plugin compares `S.proactive_enabled === '1'` as a STRING (script.js
        // L491) — our config sends a boolean, so coerce it. sound_url is the one
        // key the plugin reads that we don't store (built-in beep instead).
        const settings: Record<string, unknown> = {
          ...cfg,
          proactive_enabled: cfg.proactive_enabled ? "1" : "0",
          sound_url: "",
          // The plugin defaults the mobile FAB to 70px from the bottom, which
          // lands ON TOP of the storefront's fixed mobile bottom nav (h-16 +
          // safe area) and collides with the floating compare/cart bars. The
          // plugin exposes this exact override — raise the FAB above the nav.
          btn_bottom_mobile: 100,
          btn_bottom_desktop: 20,
        };
        window.n8nChat = {
          ajax_url: "/api/v1/chat/plugin-bridge",
          nonce: "",
          user: {},
          settings,
        };

        // Owner: the proactive popup must appear on EVERY refresh. The plugin
        // gates it on a localStorage cooldown key; clearing it here (without
        // touching the plugin code) makes each page load eligible again.
        try {
          localStorage.removeItem("n8n_proactive_seen");
        } catch {
          /* storage unavailable */
        }

        await loadScript("/jquery.min.js");
        if (cancelled) return;
        await loadScript("/chat-plugin.js");
        if (cancelled) return;

        // Owner (round 76 correction): the ring + halos must be visible
        // PERMANENTLY (from page load, no waiting for the proactive popup) — «همه
        // چیز میاد ... هیچ موج یا حلقه نیست». The plugin keeps both `display:none`
        // until the proactive popup fires (script.js:194/199). Force them visible
        // here, WITHOUT editing the plugin file, keeping the plugin's OWN
        // animations:
        //   - ring: the plugin's `n8nBreath` (scale 1→1.06, 2.5s, script.js:190)
        //   - halos: the plugin's `n8nHalo` on `.n8n-halo-1/2` (script.js:186-187)
        // Only hide them when the chat window is OPEN (plugin fades them out on
        // open, script.js:463 — the plugin sets #n8n-win to display:flex).
        const style = document.createElement("style");
        style.textContent = `
          #n8n-pro-ring {
            display: block !important;
            animation: n8nBreath 2.5s ease-in-out infinite !important;
            transform-origin: center !important;
          }
          #n8n-halos {
            display: block !important;
          }
          #n8n-w:has(#n8n-win[style*="display: flex"]) #n8n-pro-ring,
          #n8n-w:has(#n8n-win[style*="display: flex"]) #n8n-halos {
            display: none !important;
          }
        `;
        document.head.appendChild(style);

        setReady(true);
      } catch {
        /* best-effort — the storefront simply has no widget */
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [features.chat, isStorefront]);

  void ready;
  return null;
}
