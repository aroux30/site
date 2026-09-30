import Image from "next/image";
import { ImageIcon } from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * A `next/image` wrapper that cannot take a page down.
 *
 * `next/image` **throws** when `src` points at a host that is not listed in
 * `images.remotePatterns` of next.config.ts. In a server component that throw
 * aborts the whole render — and because it happens while rendering, the reader
 * sees the 404 page rather than an error. A hard-coded Unsplash placeholder in
 * the blog detail page did exactly that: any article with related posts but no
 * cover image became unreadable, with no obvious cause.
 *
 * This project deliberately keeps `remotePatterns` narrow (see the comment in
 * next.config.ts: only same-origin media plus anything the operator opts into
 * via NEXT_PUBLIC_IMAGE_HOSTS). So instead of widening it to allow a stock
 * photo site, content with no image of its own renders a neutral panel.
 *
 * Use this for any image whose URL comes from data (which is every image a
 * CMS or catalog can leave empty).
 */
export function RemoteImage({
  src,
  alt,
  className,
  fallbackClassName,
  sizes,
  priority,
  fill = true,
}: {
  /** Image URL, or null/undefined/"" to render the placeholder. */
  src?: string | null;
  alt: string;
  className?: string;
  fallbackClassName?: string;
  sizes?: string;
  priority?: boolean;
  fill?: boolean;
}) {
  const url = typeof src === "string" && src.trim() ? src.trim() : null;

  if (!url) {
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-gradient-to-br from-emerald-500/10 via-muted to-muted/80 rounded-2xl relative overflow-hidden group-hover:from-emerald-500/20 transition-colors",
          fill && "absolute inset-0 h-full w-full",
          fallbackClassName,
        )}
        role="img"
        aria-label={alt}
      >
        <div className="flex flex-col items-center gap-2 text-center p-3">
          <div className="p-3 rounded-2xl bg-background/80 shadow-sm border border-border/50 text-emerald-600 dark:text-emerald-400">
            <ImageIcon className="h-6 w-6" />
          </div>
          <span className="text-[11px] font-medium text-muted-foreground line-clamp-1 max-w-[120px]">
            {alt}
          </span>
        </div>
      </div>
    );
  }

  return (
    <Image
      src={url}
      alt={alt}
      fill={fill}
      sizes={sizes}
      priority={priority}
      className={className}
    />
  );
}
