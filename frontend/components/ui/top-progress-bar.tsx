"use client";

import { useEffect, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";

/**
 * Lightweight, zero-dependency top navigation progress bar.
 * Provides instant visual feedback on link clicks to prevent perceived freeze.
 */
export function TopProgressBar() {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [progress, setProgress] = useState(0);
  const [visible, setVisible] = useState(false);

  // Complete progress on route change completion
  useEffect(() => {
    if (visible) {
      setProgress(100);
      const timer = setTimeout(() => {
        setVisible(false);
        setProgress(0);
      }, 250);
      return () => clearTimeout(timer);
    }
  }, [pathname, searchParams]);

  // Intercept internal link clicks to start progress bar immediately
  useEffect(() => {
    const handleLinkClick = (e: MouseEvent) => {
      const target = (e.target as HTMLElement)?.closest("a");
      if (!target) return;

      const href = target.getAttribute("href");
      if (!href) return;

      // Only handle internal relative links (not new tabs, downloads, hashes, or external)
      const isInternal =
        href.startsWith("/") &&
        !href.startsWith("//") &&
        target.target !== "_blank" &&
        !href.startsWith("/#") &&
        !e.ctrlKey &&
        !e.metaKey &&
        !e.shiftKey;

      if (isInternal) {
        const currentUrl = window.location.pathname + window.location.search;
        if (href !== currentUrl) {
          setVisible(true);
          setProgress(25);

          // Simulate progress stages while waiting for route/data
          const stage1 = setTimeout(() => setProgress(65), 150);
          const stage2 = setTimeout(() => setProgress(85), 600);

          const cleanup = () => {
            clearTimeout(stage1);
            clearTimeout(stage2);
          };
          window.addEventListener("popstate", cleanup, { once: true });
        }
      }
    };

    document.addEventListener("click", handleLinkClick, { passive: true });
    return () => {
      document.removeEventListener("click", handleLinkClick);
    };
  }, []);

  if (!visible && progress === 0) return null;

  return (
    <div
      aria-hidden="true"
      className="fixed top-0 left-0 right-0 z-[9999] h-[3px] bg-transparent pointer-events-none"
    >
      <div
        className="h-full bg-gradient-to-r from-primary via-primary/90 to-amber-500 shadow-[0_0_10px_rgba(var(--primary),0.7)] transition-all ease-out duration-200"
        style={{
          width: `${progress}%`,
          opacity: visible ? 1 : 0,
        }}
      />
    </div>
  );
}

export default TopProgressBar;
