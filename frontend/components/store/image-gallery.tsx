"use client";

import { useState, useCallback } from "react";
import { RemoteImage } from "@/components/shared/remote-image";
import { cn, toPersianDigits } from "@/lib/utils";
import { ChevronLeft, ChevronRight, X, ZoomIn } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Dialog,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/ui/dialog";

/* ─────────────────────────────────────────────────────────────────────
 * ImageGallery — product image viewer with thumbnail strip + lightbox
 *
 * Features:
 *   - Main image with zoom-on-click lightbox
 *   - Thumbnail strip with scroll on overflow
 *   - Keyboard navigation (← → Esc)
 *   - RTL-safe (start/end, not left/right)
 *   - Touch-friendly on mobile
 * ────────────────────────────────────────────────────────────────── */

interface GalleryImage {
  url: string;
  alt?: string;
}

interface ImageGalleryProps {
  images: GalleryImage[];
  productName?: string;
  className?: string;
}

export function ImageGallery({
  images,
  productName = "محصول",
  className,
}: ImageGalleryProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [lightboxOpen, setLightboxOpen] = useState(false);

  const safeImages =
    images.length > 0 ? images : [{ url: "", alt: productName }];
  const current = safeImages[selectedIndex] ?? safeImages[0]!;

  const goTo = useCallback(
    (index: number) => {
      setSelectedIndex(
        ((index % safeImages.length) + safeImages.length) % safeImages.length
      );
    },
    [safeImages.length]
  );

  const goPrev = useCallback(() => goTo(selectedIndex - 1), [goTo, selectedIndex]);
  const goNext = useCallback(() => goTo(selectedIndex + 1), [goTo, selectedIndex]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowRight") goPrev(); // RTL: right = prev
      if (e.key === "ArrowLeft") goNext(); // RTL: left = next
    },
    [goPrev, goNext]
  );

  return (
    <div className={cn("space-y-3", className)} onKeyDown={handleKeyDown}>
      {/* Main image */}
      <button
        type="button"
        onClick={() => setLightboxOpen(true)}
        className="group relative block w-full aspect-square rounded-2xl bg-muted/20 overflow-hidden border border-border/60 cursor-zoom-in focus:outline-none focus:ring-2 focus:ring-primary/40"
        aria-label="بزرگ‌نمایی تصویر"
      >
        <RemoteImage
          src={current.url}
          alt={current.alt || productName}
          sizes="(max-width: 768px) 100vw, 50vw"
          className="object-contain p-4 transition-transform duration-300 motion-safe:group-hover:scale-105"
        />
        {/* Zoom hint */}
        <div className="absolute bottom-3 start-3 flex items-center gap-1.5 rounded-lg bg-background/80 backdrop-blur-sm px-2.5 py-1.5 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          <ZoomIn className="h-3.5 w-3.5" />
          بزرگ‌نمایی
        </div>
        {/* Image counter */}
        {safeImages.length > 1 && (
          <div className="absolute bottom-3 end-3 rounded-lg bg-background/80 backdrop-blur-sm px-2.5 py-1.5 text-xs tabular-nums text-muted-foreground">
            {toPersianDigits(selectedIndex + 1)} / {toPersianDigits(safeImages.length)}
          </div>
        )}
      </button>

      {/* Thumbnail strip */}
      {safeImages.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1 scrollbar-thin">
          {safeImages.map((img, i) => (
            <button
              key={`${img.url}-${i}`}
              type="button"
              onClick={() => setSelectedIndex(i)}
              className={cn(
                "shrink-0 h-16 w-16 sm:h-20 sm:w-20 rounded-xl border-2 overflow-hidden bg-muted/20 transition-all",
                i === selectedIndex
                  ? "border-primary ring-1 ring-primary/20"
                  : "border-border/60 hover:border-primary/40"
              )}
              aria-label={`تصویر ${toPersianDigits(i + 1)}`}
              aria-current={i === selectedIndex ? "true" : undefined}
            >
              <RemoteImage
                src={img.url}
                alt={img.alt || `${productName} - ${toPersianDigits(i + 1)}`}
                sizes="80px"
                className="object-contain p-1"
              />
            </button>
          ))}
        </div>
      )}

      {/* Lightbox */}
      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogPrimitive.Content
            className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] max-w-4xl w-[95vw] h-[90vh] p-0 bg-black/95 border-none flex items-center justify-center duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 sm:rounded-lg"
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") goPrev();
              if (e.key === "ArrowLeft") goNext();
            }}
          >
            <DialogTitle className="sr-only">
              نمایش بزرگ تصویر {current.alt || productName}
            </DialogTitle>
          {/* Close */}
          <button
            type="button"
            onClick={() => setLightboxOpen(false)}
            className="absolute top-4 end-4 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
            aria-label="بستن"
          >
            <X className="h-5 w-5" />
          </button>

          {/* Image */}
          <div className="relative w-full h-full flex items-center justify-center p-8">
            <RemoteImage
              src={current.url}
              alt={current.alt || productName}
              sizes="90vw"
              className="object-contain max-h-full"
            />
          </div>

          {/* Navigation arrows */}
          {safeImages.length > 1 && (
            <>
              <button
                type="button"
                onClick={goPrev}
                className="absolute end-4 top-1/2 -translate-y-1/2 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
                aria-label="تصویر قبلی"
              >
                <ChevronRight className="h-5 w-5" />
              </button>
              <button
                type="button"
                onClick={goNext}
                className="absolute start-4 top-1/2 -translate-y-1/2 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition-colors"
                aria-label="تصویر بعدی"
              >
                <ChevronLeft className="h-5 w-5" />
              </button>
              {/* Dot indicators */}
              <div className="absolute bottom-6 inset-x-0 flex justify-center gap-1.5 z-50">
                {safeImages.map((_, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setSelectedIndex(i)}
                    className={cn(
                      "h-2 rounded-full transition-all",
                      i === selectedIndex
                        ? "w-6 bg-white"
                        : "w-2 bg-white/40 hover:bg-white/60"
                    )}
                    aria-label={`تصویر ${toPersianDigits(i + 1)}`}
                  />
                ))}
              </div>
            </>
          )}
          </DialogPrimitive.Content>
        </DialogPortal>
      </Dialog>
    </div>
  );
}
