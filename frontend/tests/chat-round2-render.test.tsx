import { render } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { ChatMessageContent } from "@/components/chat/chat-message-content";

/**
 * Chat regression pins.
 *
 * The visitor widget is now the WordPress plugin's VERBATIM frontend
 * (`public/chat-plugin.js`, copied from `assets/js/script.js`) loaded by
 * `plugin-widget-loader.tsx` — so the old React-widget source pins are gone and
 * replaced by loader + plugin-file pins. The admin console stays React, so its
 * pins remain.
 *
 * `ChatMessageContent` (N1) is behavioural: proved by rendering, not grepping.
 */

describe("ChatMessageContent (N1 — admin thread rendering)", () => {
  it("renders a [Voice Message] marker as an <audio> player, not raw text", () => {
    const { container } = render(
      <ChatMessageContent text="[Voice Message](https://x/v.webm)" previewImages />,
    );
    expect(container.querySelector("audio")).not.toBeNull();
    expect(container.querySelector("audio")?.getAttribute("src")).toBe("https://x/v.webm");
    expect(container.textContent).not.toContain("[Voice Message]");
  });

  it("renders an image attachment as an inline <img> when previewImages is set (admin)", () => {
    const { container } = render(
      <ChatMessageContent text="[Attachment: photo.png](https://x/photo.png)" previewImages />,
    );
    const img = container.querySelector("img");
    expect(img).not.toBeNull();
    expect(img?.getAttribute("src")).toBe("https://x/photo.png");
  });

  it("renders a NON-image attachment as a 📎 chip (both consumers)", () => {
    const { container } = render(
      <ChatMessageContent text="[Attachment: doc.pdf](https://x/doc.pdf)" previewImages />,
    );
    expect(container.querySelector("img")).toBeNull();
    expect(container.textContent).toContain("📎");
    expect(container.textContent).toContain("doc.pdf");
  });

  it("linkifies a bare URL", () => {
    const { container } = render(<ChatMessageContent text="ببین https://shop.test/help ادامه" />);
    expect(container.querySelector('a[href="https://shop.test/help"]')).not.toBeNull();
  });
});

const ADMIN_SRC = readFileSync(
  join(__dirname, "..", "app", "admin", "chat", "page.tsx"),
  "utf-8",
);
const LOADER_SRC = readFileSync(
  join(__dirname, "..", "components", "chat", "plugin-widget-loader.tsx"),
  "utf-8",
);
const PLUGIN_SRC = readFileSync(
  join(__dirname, "..", "public", "chat-plugin.js"),
  "utf-8",
);
const GLOBALS_CSS = readFileSync(
  join(__dirname, "..", "app", "globals.css"),
  "utf-8",
);

describe("widget motion survives prefers-reduced-motion (owner: hover/halo/ring)", () => {
  // Owner (live-site parity): the FAB hover scale + icon wiggle, the halo rings
  // and the ring breath must run even for reduced-motion users — the live WP
  // site has no global kill-switch. Our globals.css `*` reduced-motion rule
  // would zero them, so the widget is exempted (same higher-specificity
  // `!important` pattern as `.wheel-rotor`).
  it("exempts the widget's toggle transition (FAB hover scale) from the kill-switch", () => {
    expect(GLOBALS_CSS).toContain("#n8n-w #n8n-toggle");
    expect(GLOBALS_CSS).toContain("transition-duration: 0.3s !important");
  });

  it("exempts the halo rings + ring breath + wiggle + badge pulse", () => {
    expect(GLOBALS_CSS).toContain("#n8n-w .n8n-halo-1");
    expect(GLOBALS_CSS).toContain("#n8n-w .n8n-halo-2");
    expect(GLOBALS_CSS).toContain("#n8n-w #n8n-pro-ring");
    expect(GLOBALS_CSS).toContain("#n8n-w #n8n-toggle:hover svg");
    expect(GLOBALS_CSS).toContain("#n8n-w #n8n-badge");
    // Durations are the plugin's own (script.js:178-190, 203).
    expect(GLOBALS_CSS).toContain("animation-duration: 2s !important"); // halo
    expect(GLOBALS_CSS).toContain("animation-duration: 2.5s !important"); // breath
    expect(GLOBALS_CSS).toContain("animation-duration: 0.4s !important"); // wiggle
  });

  it("keeps the FAB hover scale(1.1) in the verbatim plugin (script.js:480)", () => {
    expect(PLUGIN_SRC).toContain("$(this).css('transform', 'scale(1.1)')");
  });

  it("ring + halo take their color from C.button (config), not a hardcode", () => {
    // .n8n-halo background and #n8n-pro-ring border both use ${C.button}.
    expect(PLUGIN_SRC).toContain(".n8n-halo { position:absolute; inset:0; border-radius:50%; background:${C.button};");
    expect(PLUGIN_SRC).toContain("border:2px solid ${C.button};opacity:0.35;");
  });
});

describe("admin console wiring (N1/N2/N4/N9 — source pins)", () => {
  it("AdminBubble renders through the shared ChatMessageContent (N1), not raw text", () => {
    expect(ADMIN_SRC).toContain("<ChatMessageContent text={message.message} previewImages />");
  });

  it("the admin thread polls and beeps on a new USER message (N2)", () => {
    expect(ADMIN_SRC).toContain('if (res.messages.some((m) => m.role === "user")) playAdminBeep();');
  });

  it("the admin console beeps when another session's unread rises (N2)", () => {
    expect(ADMIN_SRC).toContain("total > prevUnreadOtherRef.current");
  });

  it("uses Lucide icons instead of UI emoji (owner: «ایموجی‌ها را پاک کن»)", () => {
    // The tab/button/label emoji are replaced with Lucide icons. The remaining
    // emoji are INTENTIONAL and out of scope: role avatars (👤/🤖/👨‍💼) and the
    // plugin-parity empty-state 😴 (admin-online.js:38). Assert a few icons are
    // wired and that the old UI emoji strings are gone.
    for (const icon of ["MessageCircle", "Users", "Settings", "Trash2", "RefreshCw"]) {
      // Icons are either rendered directly (<Trash2 className=) or via the tab
      // descriptor (<Icon className=, Icon: Users). Assert the import is present.
      expect(ADMIN_SRC).toContain(icon);
    }
    expect(ADMIN_SRC).toContain("<Icon className=");
    expect(ADMIN_SRC).toContain("Icon: Users");
    expect(ADMIN_SRC).toContain("Icon: Settings");
    // Old tab/button emoji gone.
    expect(ADMIN_SRC).not.toContain("💬 لایو چت");
    expect(ADMIN_SRC).not.toContain("🟢 کاربران آنلاین");
    expect(ADMIN_SRC).not.toContain("⚙️ تنظیمات");
    expect(ADMIN_SRC).not.toContain("🗑️ حذف");
    expect(ADMIN_SRC).not.toContain("🔄 بروزرسانی");
  });

  it("online cards parse the UA but show NO WP / source badge (owner removed it)", () => {
    // parseUA (N4) stays — the UA string is rendered as «دستگاه — مرورگر / OS».
    expect(ADMIN_SRC).toContain("function parseUA(");
    // Owner: «پروفایل WP را کلاً پاک کن» + «هرجا متن WP هست پاک کن» — the WP
    // badge and the source badges (پروفایل WP / فرم چت) must be GONE from the UI.
    // `is_wp_user` stays in the backend data (harmless); only the UI is removed.
    expect(ADMIN_SRC).not.toContain("پروفایل WP");
    expect(ADMIN_SRC).not.toContain("فرم چت");
    expect(ADMIN_SRC).not.toContain("{u.is_wp_user && (");
    expect(ADMIN_SRC).not.toContain(">WP<");
  });

  it("AdminBubble renders a per-role avatar (N9)", () => {
    expect(ADMIN_SRC).toContain("avatars?.admin");
  });

  it("E1: handoff toggle shows a pending state + guards double-click", () => {
    expect(ADMIN_SRC).toContain("if (!active || handoffBusy) return;");
    expect(ADMIN_SRC).toContain("disabled={handoffBusy}");
    expect(ADMIN_SRC).toContain("در حال انجام...");
  });

  it("E3: admin upload/voice show optimistic placeholder bubbles", () => {
    expect(ADMIN_SRC).toContain('tempUpload("🎤 در حال ارسال ویس...")');
    expect(ADMIN_SRC).toContain('tempUpload("📎 در حال آپلود...")');
    expect(ADMIN_SRC).toContain("dropTemp(tmp)");
  });

  it("A1/A2/A3: online card hover + dot glow", () => {
    expect(ADMIN_SRC).toContain("shadow-sm transition-shadow hover:shadow-md");
    expect(ADMIN_SRC).toContain("bg-green-500 shadow-[0_0_8px_#22c55e]");
  });

  it("AD3: conversation rows carry the plugin's active + unread state markers", () => {
    // plugin admin-chat.js:101 — active row 4px indicator bar; :103 — unread row
    // red tint + 4px red border. Structural (not palette), so both must exist.
    // Position-aware: both classes must live inside the conversation-row button.
    const rowIdx = ADMIN_SRC.indexOf("block w-full border-b p-3 text-right transition-colors");
    expect(rowIdx).toBeGreaterThan(-1);
    const rowBlock = ADMIN_SRC.slice(rowIdx, rowIdx + 500);
    expect(rowBlock).toContain("border-s-4 border-primary bg-primary/5");
    expect(rowBlock).toContain("border-e-4 border-red-500 bg-red-50");
  });

  it("AD3: the unread badge sits in the top row next to the time chip (plugin:110-114)", () => {
    // The badge moved from the last-message row to the header row, matching the
    // plugin's `badge` + `time_ago` group.
    const headerIdx = ADMIN_SRC.indexOf("shrink-0 items-center gap-1.5");
    const badgeIdx = ADMIN_SRC.indexOf("rounded-full bg-red-500 px-1.5");
    expect(headerIdx).toBeGreaterThan(-1);
    expect(badgeIdx).toBeGreaterThan(headerIdx);
  });

  it("AD3: the online card's send button is solid, not outline (plugin admin-online.js:113)", () => {
    // Plugin uses `bg-indigo-600 text-white`; the port keeps the project palette
    // but must not be `variant=\"outline\"`.
    const onlineBtnIdx = ADMIN_SRC.indexOf("window.location.href = `/admin/chat?session=");
    const block = ADMIN_SRC.slice(onlineBtnIdx - 300, onlineBtnIdx);
    expect(block).not.toContain('variant="outline"');
  });

  it("AD6: a dedicated voice bar replaces the composer while recording (plugin php:1037-1047)", () => {
    // The plugin HIDES the composer and shows `#n8n-voice-ui` (timer + لغو +
    // ارسال). The port must: hide the composer while recording, expose a CANCEL
    // path (admin-chat.js:415 cancelVoice → stopRecording(false)) and a SEND path.
    expect(ADMIN_SRC).toContain('recording ? "hidden" : "flex"');
    expect(ADMIN_SRC).toContain("stopRecording(false)");
    expect(ADMIN_SRC).toContain("stopRecording(true)");
    expect(ADMIN_SRC).toContain("لغو");
  });

  it("AD7: bubble tail is NOT mirrored (plugin admin-chat.js:293-296)", () => {
    // Border-radius shorthand "TL TR BR BL". Plugin: user flat bottom-LEFT
    // (`rounded-bl-none`) → BL=0 → "12px 12px 12px 0"; admin/ai flat bottom-RIGHT
    // (`rounded-br-none`) → BR=0 → "12px 12px 0 12px". The earlier port had these
    // swapped (mirrored tail).
    expect(ADMIN_SRC).toContain('isUser ? "12px 12px 12px 0" : "12px 12px 0 12px"');
  });

  it("AD8: online empty state matches the plugin's sizing (admin-online.js:38)", () => {
    // Plugin: emoji 56px, title text-lg, hint text-xs, py-16.
    const idx = ADMIN_SRC.indexOf("هیچ کاربری آنلاین نیست");
    expect(idx).toBeGreaterThan(-1);
    const block = ADMIN_SRC.slice(idx - 250, idx + 100);
    expect(block).toContain("text-[56px]");
    expect(block).toContain("py-16");
    expect(block).toContain("text-lg font-bold");
  });

  it("AD9: the online tab's refresh button reloads ONLINE users, not conversations", () => {
    // Plugin admin-online.js:137 fires `n8n-refresh-online` which reloads the
    // online list. The port's online-tab refresh must call reloadOnline (the
    // online query), not reloadList (conversations).
    const idx = ADMIN_SRC.indexOf("مانیتورینگ کاربران آنلاین");
    expect(idx).toBeGreaterThan(-1);
    const block = ADMIN_SRC.slice(idx, idx + 600);
    expect(block).toContain("void reloadOnline()");
    expect(block).not.toContain("void reloadList()");
  });

  it("AD10: the admin composer textarea auto-resizes (plugin admin-chat.js:363-367)", () => {
    // Plugin: on input, height = clamp(scrollHeight, 34, 80). The port must
    // recompute height from scrollHeight, not stay a fixed 34px.
    expect(ADMIN_SRC).toContain("Math.min(Math.max(el.scrollHeight, 34), 80)");
  });
});

describe("plugin widget loader (switch + bridge + globals)", () => {
  it("short-circuits on the chat switch — no plugin load when off", () => {
    // The exact early-return the shop-feature gate + its negative test anchor
    // on. The isStorefront guard widens the same return: the widget is a
    // front-end feature and never loads on /admin (wp-admin parity).
    expect(LOADER_SRC).toContain(
      "if (!features.chat || !isStorefront) return;",
    );
  });

  it("points the plugin at the bridge endpoint", () => {
    expect(LOADER_SRC).toContain('ajax_url: "/api/v1/chat/plugin-bridge"');
  });

  it("coerces proactive_enabled to the plugin's string contract ('1'/'0')", () => {
    // The plugin compares `S.proactive_enabled === '1'` (script.js:491) — a
    // boolean never fires the popup/ring.
    expect(LOADER_SRC).toContain('cfg.proactive_enabled ? "1" : "0"');
  });

  it("clears the proactive cooldown so the popup shows every refresh", () => {
    expect(LOADER_SRC).toContain('localStorage.removeItem("n8n_proactive_seen")');
  });

  it("injects an always-visible ring + halos override (owner, round 76)", () => {
    // Owner: the ring and halos must show PERMANENTLY from page load (no waiting
    // for the proactive popup). The plugin keeps both `display:none` until the
    // popup fires, so we force them visible with the plugin's OWN animations.
    expect(LOADER_SRC).toContain("#n8n-pro-ring");
    expect(LOADER_SRC).toContain("display: block !important");
    expect(LOADER_SRC).toContain("animation: n8nBreath 2.5s ease-in-out infinite !important");
    expect(LOADER_SRC).toContain("#n8n-halos");
    // No custom pulse keyframe — the plugin's n8nBreath / n8nHalo are used.
    expect(LOADER_SRC).not.toContain("n8nRingPulse");
  });

  it("hides the always-on ring + halos only while the chat window is open", () => {
    // The plugin fades them out on open (script.js:463); since our override pins
    // `display:block`, mirror that with the open-window selector.
    expect(LOADER_SRC).toContain('#n8n-w:has(#n8n-win[style*="display: flex"]) #n8n-pro-ring');
    expect(LOADER_SRC).toContain('#n8n-w:has(#n8n-win[style*="display: flex"]) #n8n-halos');
  });

  it("loads jQuery then the verbatim plugin script", () => {
    expect(LOADER_SRC).toContain('loadScript("/jquery.min.js")');
    expect(LOADER_SRC).toContain('loadScript("/chat-plugin.js")');
  });
});

describe("verbatim plugin script (public/chat-plugin.js)", () => {
  it("is the plugin's own file (its distinctive markers are present)", () => {
    expect(PLUGIN_SRC).toContain("jQuery(document).ready");
    expect(PLUGIN_SRC).toContain("n8nChat.settings");
    expect(PLUGIN_SRC).toContain("n8nWiggle");
    expect(PLUGIN_SRC).toContain("n8nBreath");
  });

  it("keeps the plugin's ring + halo + breath keyframes", () => {
    expect(PLUGIN_SRC).toContain("@keyframes n8nHalo");
    expect(PLUGIN_SRC).toContain("@keyframes n8nBreath");
    expect(PLUGIN_SRC).toContain("#n8n-pro-ring");
  });
});
