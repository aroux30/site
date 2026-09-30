"use client";

import { useCallback, useEffect, useState } from "react";
import { ImageIcon, RefreshCw, UploadCloud } from "lucide-react";
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

interface MediaPickerProps {
  /** آدرس انتخاب‌شده فعلی */
  value: string;
  /** با انتخاب یا پاک کردن صدا زده می‌شود */
  onChange: (url: string) => void;
  label?: string;
}

/**
 * کتابخانه مدیا به سبک Strapi: انتخاب از فایل‌های موجود یا آپلود جدید.
 * خروجی فقط URL فایل است تا در هر فیلد متنی (کاور بلاگ، بنر، ...) بنشیند.
 */
export function MediaPicker({ value, onChange, label = "تصویر" }: MediaPickerProps) {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  // The library was pinned to page 1 / 60 items, so anything past the 60th
  // was unreachable from any picker. Real stores are past that in a week.
  // Page and search are the server's, not a client-side filter over a slice.
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [hasMore, setHasMore] = useState(false);

  const PAGE_SIZE = 60;

  const fetchAssets = useCallback(async () => {
    setLoading(true);
    try {
      const res = await mediaApi.list({
        page,
        page_size: PAGE_SIZE,
        // The API matches file name and alt text, so an operator can find an
        // image by what they named it rather than by the uuid on disk.
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

  // A new search term must return to page 1, or the operator lands on page 4
  // of a query that has one page and sees nothing.
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
      onChange(asset.file_url);
      setOpen(false);
      toast({ title: "موفق", description: "تصویر آپلود و انتخاب شد" });
    } catch {
      toast({ title: "خطا", description: "آپلود تصویر با خطا مواجه شد", variant: "destructive" });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {value ? (
          // eslint-disable-next-line @next/next/no-img-element -- editor preview of admin-managed media
          <img
            src={value}
            alt=""
            className="h-12 w-12 rounded-md border object-cover"
          />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded-md border border-dashed text-muted-foreground">
            <ImageIcon className="h-5 w-5" />
          </div>
        )}
        <div className="flex flex-1 items-center gap-2">
          <input
            className="flex h-9 w-full rounded-md border border-input bg-background px-3 text-xs text-muted-foreground"
            dir="ltr"
            readOnly
            value={value}
            placeholder="تصویری انتخاب نشده"
          />
          <Button type="button" variant="outline" size="sm" onClick={() => setOpen(true)}>
            انتخاب
          </Button>
          {value && (
            <Button type="button" variant="ghost" size="sm" onClick={() => onChange("")}>
              حذف
            </Button>
          )}
        </div>
      </div>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <DialogTitle>کتابخانه مدیا — {label}</DialogTitle>
          </DialogHeader>
          <div className="flex items-center justify-between gap-2 py-2">
            <Button variant="outline" size="sm" onClick={fetchAssets} disabled={loading}>
              <RefreshCw className={`h-4 w-4 ms-1 ${loading ? "animate-spin" : ""}`} />
              بروزرسانی
            </Button>
            <input
              className="h-9 flex-1 rounded-md border border-input bg-background px-3 text-xs"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="جست‌وجو بر اساس نام یا متن جایگزین"
              aria-label="جست‌وجو در کتابخانه مدیا"
            />
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
              <div className="grid max-h-96 grid-cols-3 gap-3 overflow-y-auto py-2 sm:grid-cols-4">
                {assets.map((asset) => (
                  <button
                    key={asset.id}
                    type="button"
                    className="group relative aspect-square overflow-hidden rounded-lg border transition hover:ring-2 hover:ring-primary"
                    onClick={() => {
                      onChange(asset.file_url);
                      setOpen(false);
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
                      // Same warning WordPress shows: the image is usable but
                      // invisible to a screen reader and to image search.
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
    </div>
  );
}
