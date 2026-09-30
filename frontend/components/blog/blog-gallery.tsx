"use client";

import React, { useState } from "react";
import Image from "next/image";
import { Images, X, ChevronLeft, ChevronRight } from "lucide-react";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { toPersianDigits } from "@/lib/utils";

interface BlogGalleryProps {
  imageUrls: string[];
  title?: string;
}

export function BlogGallery({ imageUrls, title }: BlogGalleryProps) {
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);

  if (!imageUrls || imageUrls.length === 0) return null;

  const openModal = (idx: number) => setSelectedIdx(idx);
  const closeModal = () => setSelectedIdx(null);
  const next = () => {
    if (selectedIdx !== null) {
      setSelectedIdx((selectedIdx + 1) % imageUrls.length);
    }
  };
  const prev = () => {
    if (selectedIdx !== null) {
      setSelectedIdx((selectedIdx - 1 + imageUrls.length) % imageUrls.length);
    }
  };

  return (
    <section className="my-10 rounded-3xl border border-border bg-card p-6 shadow-sm">
      <div className="mb-6 flex items-center justify-between border-b border-border pb-4">
        <div className="flex items-center gap-2">
          <Images className="h-5 w-5 text-emerald-600" />
          <h3 className="font-bold text-lg">
            گالری تصاویر{" "}
            <span className="text-sm font-normal text-muted-foreground">
              ({toPersianDigits(String(imageUrls.length))} تصویر)
            </span>
          </h3>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
        {imageUrls.map((url, idx) => (
          <div
            key={idx}
            onClick={() => openModal(idx)}
            className="group relative aspect-square cursor-pointer overflow-hidden rounded-2xl border border-border bg-muted transition-transform hover:scale-[1.02] hover:shadow-md"
          >
            <Image
              src={url}
              alt={`${title || "تصویر"} - ${idx + 1}`}
              fill
              className="object-cover transition-transform duration-300 group-hover:scale-110"
              sizes="(max-width: 768px) 50vw, 25vw"
            />
            <div className="absolute inset-0 bg-black/0 transition-colors group-hover:bg-black/20" />
          </div>
        ))}
      </div>

      {/* Lightbox Modal */}
      <Dialog open={selectedIdx !== null} onOpenChange={(open) => !open && closeModal()}>
        <DialogContent className="max-w-4xl border-0 bg-black/90 p-2 text-white">
          {selectedIdx !== null && imageUrls[selectedIdx] && (
            <div className="relative flex h-[75vh] w-full items-center justify-center">
              <div className="relative h-full w-full">
                <Image
                  src={imageUrls[selectedIdx]}
                  alt="نمای بزرگ تصویر"
                  fill
                  className="object-contain"
                />
              </div>

              {/* Prev / Next buttons */}
              {imageUrls.length > 1 && (
                <>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      prev();
                    }}
                    className="absolute right-4 top-1/2 -translate-y-1/2 rounded-full bg-white/20 p-2 text-white backdrop-blur-md transition-colors hover:bg-white/40"
                    aria-label="قبلی"
                  >
                    <ChevronRight className="h-6 w-6" />
                  </button>
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation();
                      next();
                    }}
                    className="absolute left-4 top-1/2 -translate-y-1/2 rounded-full bg-white/20 p-2 text-white backdrop-blur-md transition-colors hover:bg-white/40"
                    aria-label="بعدی"
                  >
                    <ChevronLeft className="h-6 w-6" />
                  </button>
                </>
              )}

              {/* Index counter */}
              <div className="absolute bottom-4 left-1/2 -translate-x-1/2 rounded-full bg-black/60 px-4 py-1 text-xs text-white backdrop-blur-sm">
                {toPersianDigits(String(selectedIdx + 1))} از {toPersianDigits(String(imageUrls.length))}
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
