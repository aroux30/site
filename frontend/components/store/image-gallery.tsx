"use client";

import { useState, useCallback, useEffect } from "react";
import useEmblaCarousel from "embla-carousel-react";
import { RemoteImage } from "@/components/shared/remote-image";
import { cn, toPersianDigits } from "@/lib/utils";
import { ChevronLeft, ChevronRight, X, ZoomIn, ZoomOut } from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import {
  Dialog,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
} from "@/components/ui/dialog";

/* ─────────────────────────────────────────────────────────────────────
 * ImageGallery — advanced product image viewer with Embla Carousel + Lightbox
 *
 * Features:
 *   - Embla Carousel for smooth touch swipe and transitions (RTL native)
 *   - Synchronized thumbnail strip with smooth auto-scroll to active index
 *   - Main image zoom hint & click-to-open lightbox
 *   - Lightbox zoom mode (1x ⇄ 1.75x) with pan/scroll
 *   - Keyboard navigation (ArrowRight/ArrowLeft for RTL, Escape to close)
 * ────────────────────────────────────────────────────────────────── */

export interface GalleryImage {
  url: string;
  alt?: string;
}

export interface ImageGalleryProps {
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
  const [isZoomed, setIsZoomed] = useState(false);

  const safeImages =
    images.length > 0 ? images : [{ url: "", alt: productName }];
  const current = safeImages[selectedIndex] ?? safeImages[0]!;

  // ── Embla Carousel instances (Main + Thumbnails) ───────────────────────────
  const [mainRef, mainApi] = useEmblaCarousel({
    direction: "rtl",
    loop: safeImages.length > 1,
  });

  const [thumbRef, thumbApi] = useEmblaCarousel({
    direction: "rtl",
    containScroll: "keepSnaps",
    dragFree: true,
  });

  const onSelect = useCallback(() => {
    if (!mainApi) return;
    const index = mainApi.selectedScrollSnap();
    setSelectedIndex(index);
    thumbApi?.scrollTo(index);
  }, [mainApi, thumbApi]);

  useEffect(() => {
    if (!mainApi) return;
    onSelect();
    mainApi.on("select", onSelect);
    mainApi.on("reInit", onSelect);
    return () => {
      mainApi.off("select", onSelect);
      mainApi.off("reInit", onSelect);
    };
  }, [mainApi, onSelect]);

  const onThumbClick = useCallback(
    (index: number) => {
      if (!mainApi) return;
      mainApi.scrollTo(index);
    },
    [mainApi]
  );

  const scrollPrev = useCallback(() => {
    if (mainApi) mainApi.scrollPrev();
  }, [mainApi]);

  const scrollNext = useCallback(() => {
    if (mainApi) mainApi.scrollNext();
  }, [mainApi]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "ArrowRight") {
        e.preventDefault();
        scrollPrev(); // RTL: right = prev
      } else if (e.key === "ArrowLeft") {
        e.preventDefault();
        scrollNext(); // RTL: left = next
      }
    },
    [scrollPrev, scrollNext]
  );

  return (
    <div
      className={cn("space-y-3 select-none", className)}
      onKeyDown={handleKeyDown}
      tabIndex={0}
      aria-label="گالری تصاویر محصول"
    >
      {/* ── Main Embla Viewport ── */}
      <div className="relative group rounded-2xl overflow-hidden border border-border/60 bg-muted/20">
        <div ref={mainRef} className="overflow-hidden">
          <div className="flex touch-pan-y" style={{ direction: "rtl" }}>
            {safeImages.map((img, idx) => (
              <div
                key={`${img.url}-${idx}`}
                className="relative min-w-0 flex-[0_0_100%] aspect-square cursor-zoom-in"
                onClick={() => {
                  setIsZoomed(false);
                  setLightboxOpen(true);
                }}
              >
                <RemoteImage
                  src={img.url}
                  alt={img.alt || `${productName} - تصویر ${toPersianDigits(idx + 1)}`}
                  sizes="(max-width: 768px) 100vw, 50vw"
                  className="object-contain p-4 transition-transform duration-300 motion-safe:group-hover:scale-105"
                />
              </div>
            ))}
          </div>
        </div>

        {/* Zoom hint overlay */}
        <div className="absolute bottom-3 start-3 pointer-events-none flex items-center gap-1.5 rounded-lg bg-background/80 backdrop-blur-sm px-2.5 py-1.5 text-xs text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity">
          <ZoomIn className="h-3.5 w-3.5" />
          <span>بزرگ‌نمایی</span>
        </div>

        {/* Counter */}
        {safeImages.length > 1 && (
          <div className="absolute bottom-3 end-3 rounded-lg bg-background/80 backdrop-blur-sm px-2.5 py-1.5 text-xs tabular-nums text-muted-foreground">
            {toPersianDigits(selectedIndex + 1)} / {toPersianDigits(safeImages.length)}
          </div>
        )}

        {/* Nav arrows on main carousel */}
        {safeImages.length > 1 && (
          <>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                scrollPrev();
              }}
              className="absolute end-2 top-1/2 -translate-y-1/2 z-10 opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity flex h-9 w-9 items-center justify-center rounded-full bg-background/80 backdrop-blur-sm border border-border/60 text-foreground hover:bg-background shadow-sm"
              aria-label="تصویر قبلی"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                scrollNext();
              }}
              className="absolute start-2 top-1/2 -translate-y-1/2 z-10 opacity-0 group-hover:opacity-100 [@media(hover:none)]:opacity-100 transition-opacity flex h-9 w-9 items-center justify-center rounded-full bg-background/80 backdrop-blur-sm border border-border/60 text-foreground hover:bg-background shadow-sm"
              aria-label="تصویر بعدی"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </>
        )}
      </div>

      {/* ── Synchronized Thumbnail Strip ── */}
      {safeImages.length > 1 && (
        <div ref={thumbRef} className="overflow-hidden">
          <div className="flex gap-2" style={{ direction: "rtl" }}>
            {safeImages.map((img, i) => (
              <button
                key={`thumb-${img.url}-${i}`}
                type="button"
                onClick={() => onThumbClick(i)}
                className={cn(
                  "shrink-0 h-16 w-16 sm:h-20 sm:w-20 rounded-xl border-2 overflow-hidden bg-muted/20 transition-all",
                  i === selectedIndex
                    ? "border-primary ring-2 ring-primary/20 scale-102"
                    : "border-border/60 hover:border-primary/40 opacity-70 hover:opacity-100"
                )}
                aria-label={`تصویر بندانگشتی ${toPersianDigits(i + 1)}`}
                aria-current={i === selectedIndex ? "true" : undefined}
              >
                <RemoteImage
                  src={img.url}
                  alt={img.alt || `${productName} - ${toPersianDigits(i + 1)}`}
                  sizes="80px"
                  className="object-contain p-1 w-full h-full"
                />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Lightbox Modal with Zoom ── */}
      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogPortal>
          <DialogOverlay className="bg-black/90 backdrop-blur-md" />
          <DialogPrimitive.Content
            className="fixed left-[50%] top-[50%] z-50 translate-x-[-50%] translate-y-[-50%] max-w-5xl w-[95vw] h-[90vh] p-0 bg-transparent border-none flex items-center justify-center focus:outline-hidden"
            onKeyDown={(e) => {
              if (e.key === "ArrowRight") {
                e.preventDefault();
                scrollPrev();
              } else if (e.key === "ArrowLeft") {
                e.preventDefault();
                scrollNext();
              } else if (e.key === "Escape") {
                setLightboxOpen(false);
              }
            }}
          >
            <DialogTitle className="sr-only">
              نمایش بزرگ تصویر {current.alt || productName}
            </DialogTitle>

            {/* Top Toolbar */}
            <div className="absolute top-4 inset-x-4 z-50 flex items-center justify-between pointer-events-none">
              <div className="pointer-events-auto rounded-lg bg-black/60 px-3 py-1.5 text-xs text-white tabular-nums backdrop-blur-sm">
                {toPersianDigits(selectedIndex + 1)} از {toPersianDigits(safeImages.length)}
              </div>
              <div className="pointer-events-auto flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setIsZoomed(!isZoomed)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition backdrop-blur-sm"
                  aria-label={isZoomed ? "کوچک‌نمایی" : "بزرگ‌نمایی"}
                >
                  {isZoomed ? <ZoomOut className="h-5 w-5" /> : <ZoomIn className="h-5 w-5" />}
                </button>
                <button
                  type="button"
                  onClick={() => setLightboxOpen(false)}
                  className="flex h-10 w-10 items-center justify-center rounded-full bg-white/10 text-white hover:bg-white/20 transition backdrop-blur-sm"
                  aria-label="بستن"
                >
                  <X className="h-5 w-5" />
                </button>
              </div>
            </div>

            {/* Lightbox Image Container */}
            <div
              className={cn(
                "relative w-full h-full flex items-center justify-center p-6 overflow-auto transition-transform duration-300",
                isZoomed ? "cursor-zoom-out" : "cursor-zoom-in"
              )}
              onClick={() => setIsZoomed(!isZoomed)}
            >
              <div
                className={cn(
                  "relative max-w-full max-h-full transition-transform duration-300",
                  isZoomed && "scale-175"
                )}
              >
                <RemoteImage
                  src={current.url}
                  alt={current.alt || productName}
                  sizes="100vw"
                  className="object-contain max-h-[80vh] rounded-lg"
                />
              </div>
            </div>

            {/* Lightbox Nav Arrows */}
            {safeImages.length > 1 && (
              <>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    scrollPrev();
                  }}
                  className="absolute end-4 top-1/2 -translate-y-1/2 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 text-white hover:bg-white/30 transition backdrop-blur-sm shadow-md"
                  aria-label="تصویر قبلی"
                >
                  <ChevronRight className="h-6 w-6" />
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    scrollNext();
                  }}
                  className="absolute start-4 top-1/2 -translate-y-1/2 z-50 flex h-11 w-11 items-center justify-center rounded-full bg-white/15 text-white hover:bg-white/30 transition backdrop-blur-sm shadow-md"
                  aria-label="تصویر بعدی"
                >
                  <ChevronLeft className="h-6 w-6" />
                </button>

                {/* Dot Indicators */}
                <div className="absolute bottom-6 inset-x-0 flex justify-center gap-1.5 z-50">
                  {safeImages.map((_, i) => (
                    <button
                      key={i}
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onThumbClick(i);
                      }}
                      className={cn(
                        "h-2 rounded-full transition-all",
                        i === selectedIndex
                          ? "w-6 bg-primary"
                          : "w-2 bg-white/40 hover:bg-white/60"
                      )}
                      aria-label={`رفتن به تصویر ${toPersianDigits(i + 1)}`}
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
