import type { Metadata } from "next";
import { EditorProbeClient } from "./editor-probe-client";

/**
 * A bare page that mounts the content editor on its own, for the toolbar
 * browser test in frontend/scripts/verify-editor-toolbar.mjs.
 *
 * It lives under /admin so the staff guard in middleware.ts applies. An
 * earlier version sat at /editor-probe, which the middleware explicitly
 * passes through — only `/admin` and `/account` are gated — so the route was
 * reachable by typing the URL, and a comment claiming it was "admin-only" was
 * simply wrong. `noindex` is the second line of defence: a page that must not
 * be in a search index should say so rather than rely on the path.
 */
export const metadata: Metadata = {
  title: "پروب ادیتور",
  robots: { index: false, follow: false },
};

export default function EditorProbePage() {
  return <EditorProbeClient />;
}
