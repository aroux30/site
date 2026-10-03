"use client";

/**
 * MediaBodyDialog — pick an already-uploaded asset and insert it at the caret
 * inside the content editor.
 *
 * The existing `MediaPicker` sets a URL for a *field* (a cover image). An
 * operator writing a post had no way to put an image in the body: the toolbar
 * had no insert button and the only route to a picture was hand-written HTML,
 * which is both tedious and a place to paste a wrong URL. This dialog is the
 * missing second half — it hands the chosen asset's real `file_url` and `alt`
 * back to the editor, which inserts the markup there.
 *
 * Uploading is intentionally not here: the library dialog stays a browser of
 * what already exists, and a new file is uploaded from the media page. That
 * keeps one place responsible for upload validation and storage.
 */

import { useCallback, useEffect, useState } from "react";
import { RefreshCw, Search, UploadCloud } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { mediaApi, type MediaAsset } from "@/lib/api/media";
import { MEDIA_ACCEPT_ATTRIBUTE } from "@/lib/media-types";

/** What the editor needs in order to insert one asset. */
export interface MediaInsertion {
  url: string;
  alt: string;
  caption?: string;
}

interface MediaBodyDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called with the chosen asset; the editor does the insertion at the caret. */
  onInsert: (media: MediaInsertion) => void;
}

const PAGE_SIZE = 60;

export function MediaBodyDialog({ open, onOpenChange, onInsert }: MediaBodyDialogProps) {
  const { toast } = useToast();
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [hasMore, setHasMore] = useState(false);

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mediaApi.list({
        page,
        page_size: PAGE_SIZE,
        search: search.trim() || undefined,
      });
      const images = res.items.filter((a) => a.mime_type.startsWith("image/"));
      setAssets(images);
      setHasMore(res.page < res.total_pages);
    } catch {
      toast({
        title: "خطا",
        description: "بارگذاری کتابخانه مدیا با خطا مواجه شد",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
    }
  }, [page, search, toast]);

  useEffect(() => {
    setPage(1);
  }, [search]);

  useEffect(() => {
    if (open) fetchAssets();
  }, [open, fetchAssets]);

  const upload = async (file: File) => {
    setUploading(true);
    try {
      const data = new FormData();
      data.append("file", file);
      const asset = await mediaApi.upload(data);
      onInsert({ url: asset.file_url, alt: asset.alt_text ?? "" });
      onOpenChange(false);
      toast({ title: "موفق", description: "تصویر آپلود و در متن درج شد" });
    } catch {
      toast({ title: "خطا", description: "آپلود تصویر با خطا مواجه شد", variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl" dir="rtl">
        <DialogHeader>
          <DialogTitle>درج تصویر در متن</DialogTitle>
        </DialogHeader>
        <div className="flex flex-wrap items-center gap-2 py-2">
          <Button variant="outline" size="sm" onClick={fetchAssets} disabled={loading}>
            <RefreshCw className={`h-4 w-4 ms-1 ${loading ? "animate-spin" : ""}`} />
            بروزرسانی
          </Button>
          <div className="flex min-w-48 flex-1 items-center gap-1 rounded-md border border-input px-2">
            <Search className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <input
              className="h-8 flex-1 bg-transparent text-xs outline-none"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جست‌وجو بر اساس نام یا متن جایگزین"
              aria-label="جست‌وجو در کتابخانه مدیا"
            />
          </div>
          <Button size="sm" asChild disabled={uploading}>
            <label className="cursor-pointer">
              <UploadCloud className="h-4 w-4 ms-1" />
              {uploading ? "در حال آپلود..." : "آپلود تصویر جدید"}
              <input
                type="file"
                accept={MEDIA_ACCEPT_ATTRIBUTE}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) upload(file);
                  e.target.value = "";
                }}
              />
            </label>
          </Button>
        </div>
        {assets.length === 0 && !loading ? (
          <p className="py-10 text-center text-sm text-muted-foreground">
            {search.trim()
              ? `تصویری با «${search.trim()}» پیدا نشد`
              : "هنوز تصویری در کتابخانه نیست — اولین تصویر را آپلود کنید"}
          </p>
        ) : (
          <>
            <div className="grid max-h-96 grid-cols-3 gap-3 overflow-y-auto py-2 sm:grid-cols-5">
              {assets.map((asset) => (
                <button
                  key={asset.id}
                  type="button"
                  className="group relative aspect-square overflow-hidden rounded-lg border transition hover:ring-2 hover:ring-primary"
                  title={asset.alt_text?.trim() || asset.file_name}
                  onClick={() => {
                    onInsert({
                      url: asset.file_url,
                      alt: asset.alt_text ?? "",
                      caption: asset.caption ?? undefined,
                    });
                    onOpenChange(false);
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element -- admin library thumbnails */}
                  <img
                    src={asset.file_url}
                    alt={asset.alt_text ?? asset.file_name}
                    className="h-full w-full object-cover"
                  />
                  {asset.alt_text?.trim() ? (
                    <span className="absolute inset-x-0 bottom-0 truncate bg-black/60 px-1 py-0.5 text-[10px] text-white opacity-0 transition group-hover:opacity-100">
                      {asset.alt_text}
                    </span>
                  ) : (
                    <span className="absolute end-1 top-1 rounded bg-amber-500/90 px-1 text-[10px] font-medium text-white">
                      بدون alt
                    </span>
                  )}
                </button>
              ))}
            </div>
            {hasMore && (
              <Button
                variant="outline"
                size="sm"
                className="w-full"
                onClick={() => setPage((p) => p + 1)}
                disabled={loading}
              >
                {loading ? "در حال بارگذاری..." : "نمایش تصاویر بیشتر"}
              </Button>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}
