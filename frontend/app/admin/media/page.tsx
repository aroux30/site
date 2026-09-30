"use client";

import { useEffect, useRef, useState } from "react";
import {
  FolderOpen,
  Folder,
  ImageIcon,
  RefreshCw,
  UploadCloud,
  Trash2,
  FolderInput,
  Crosshair,
  Info,
  Copy,
  Check,
  FileText,
  RotateCw,
  RotateCcw,
  Images,
  Zap,
  Scaling,
  Search,
  Crop,
  AlertTriangle,
  FlipHorizontal2,
  FlipVertical2,
} from "lucide-react";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { mediaApi, type MediaAsset } from "@/lib/api/media";
import { mediaEditingApi } from "@/lib/api/wp-parity";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  MEDIA_ACCEPT_ATTRIBUTE,
  MEDIA_MAX_BATCH_FILES,
  MEDIA_MIME_PREFIXES,
} from "@/lib/media-types";
import { toPersianDigits } from "@/lib/utils";
import { ImageSizeSettingsCard } from "@/components/admin/image-size-settings-card";

const MEDIA_QUERY_KEY = "admin-media" as const;

/** One grid page. A 2000-image library is unusable at any smaller page. */
const PAGE_SIZE = 60;

function fmtSize(bytes: number): string {
  if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1024)) + " KB";
}

/** اگر فایل فیزیکی روی دیسک نیست (آپلود قدیمی/محیط دیگر)، نمایش بصری ندهیم. */
function ImageWithFallback({ asset, className }: { asset: MediaAsset; className: string }) {
  const [broken, setBroken] = useState(false);
  if (broken || !asset.mime_type.startsWith("image/")) {
    return (
      <div className="flex h-32 items-center justify-center bg-muted">
        <div className="text-center">
          <ImageIcon className="mx-auto h-8 w-8 text-muted-foreground" />
          {broken && <p className="mt-1 text-[10px] text-muted-foreground">فایل در دسترس نیست</p>}
        </div>
      </div>
    );
  }
  return (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={mediaApi.variantUrl(asset.id, { width: 300 })}
      alt={asset.alt_text ?? asset.file_name}
      className={className}
      loading="lazy"
      onError={() => setBroken(true)}
    />
  );
}

export default function AdminMediaPage() {
  const { toast } = useToast();
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  // The list was pinned to page 1 with no pager, so a store with more than 60
  // assets could not reach the rest of its own library.
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [mimeFilter, setMimeFilter] = useState("");

  // focal point dialog
  const [focalAsset, setFocalAsset] = useState<MediaAsset | null>(null);
  const [savingFocal, setSavingFocal] = useState(false);

  // detail & metadata dialog (WordPress parity: caption, description, alt_text)
  const [detailAsset, setDetailAsset] = useState<MediaAsset | null>(null);
  const [detailAlt, setDetailAlt] = useState("");
  const [detailCaption, setDetailCaption] = useState("");
  const [detailDescription, setDetailDescription] = useState("");
  const [detailFolder, setDetailFolder] = useState("");
  const [savingDetail, setSavingDetail] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  // image editing (crop/resize/rotate/EXIF/thumbnails/optimize)
  const [imageBusy, setImageBusy] = useState<
    "rotate" | "resize" | "thumbs" | "optimize" | "exif" | "crop" | "flip" | null
  >(null);
  const [resizeWidth, setResizeWidth] = useState("");
  const [resizeHeight, setResizeHeight] = useState("");
  const [exifData, setExifData] = useState<Record<string, unknown> | null>(null);
  const [cropOpen, setCropOpen] = useState(false);
  const [crop, setCrop] = useState({ x: 0, y: 0, width: 0, height: 0 });

  const fileRef = useRef<HTMLInputElement>(null);

  // The old load used Promise.allSettled and never surfaced an error, so a
  // failing list must not turn into a toast. `fallbackError` is only ever
  // consulted when something throws; this queryFn keeps settling both calls
  // and returns out-of-band flags instead, exactly like the old behaviour.
  const {
    data,
    loading,
    reload: load,
  } = useAdminQuery<{
    assets: MediaAsset[];
    totalPages: number;
    total: number;
    folders: Array<{ path: string; asset_count: number }>;
    // Same wall of silence the old page had: the failure is not rendered.
    listFailed: boolean;
    foldersFailed: boolean;
  }>({
    // Every filter that scopes the result set is part of the key, so paging or
    // typing in the search box cannot serve a page from the previous query.
    queryKey: [MEDIA_QUERY_KEY, currentFolder ?? "", page, search, mimeFilter],
    queryFn: async () => {
      const [list, flds] = await Promise.allSettled([
        mediaApi.list({
          page,
          page_size: PAGE_SIZE,
          folder: currentFolder === null ? undefined : currentFolder,
          search: search.trim() || undefined,
          mime_type: mimeFilter || undefined,
        }),
        mediaApi.listFolders(),
      ]);
      return {
        assets: list.status === "fulfilled" ? list.value.items : [],
        totalPages: list.status === "fulfilled" ? list.value.total_pages : 1,
        total: list.status === "fulfilled" ? list.value.total : 0,
        folders: flds.status === "fulfilled" ? flds.value : [],
        listFailed: list.status === "rejected",
        foldersFailed: flds.status === "rejected",
      };
    },
    fallbackError: "دریافت رسانه ناموفق بود",
    // Typing should not fire a request per keystroke.
    options: { placeholderData: (prev) => prev },
  });
  const assets: MediaAsset[] = data?.assets ?? [];
  const folders: Array<{ path: string; asset_count: number }> = data?.folders ?? [];
  const totalPages: number = data?.totalPages ?? 1;
  const totalAssets: number = data?.total ?? 0;
  const runMutation = useAdminMutation();

  // Any change of scope invalidates the current offset: staying on page 4 of a
  // now-one-page result set would render an empty grid with no way back.
  useEffect(() => {
    setPage(1);
  }, [currentFolder, search, mimeFilter]);

  // Reset the selection on every load — a fresh fetch replaces the grid, so
  // the old code cleared stale picks right after the payload landed.
  useEffect(() => {
    setSelected(new Set());
  }, [currentFolder, data]);

  const upload = async (files: File[]) => {
    // Bound to a local so the single-file branch and the toast below can read
    // the same value without re-indexing an array this guard already proved
    // non-empty.
    const [first] = files;
    if (!first) return;
    setUploading(true);
    const result = await runMutation(
      async () => {
        if (files.length === 1) {
          const fd = new FormData();
          fd.append("file", first);
          if (currentFolder) fd.append("folder", currentFolder);
          return { uploaded: [await mediaApi.upload(fd)], errors: [] };
        }
        return await mediaApi.uploadBatch(files, currentFolder ?? undefined);
      },
      {
        fallbackError: "آپلود ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: (res) => {
          // A batch accepts what it can and reports the rest, so a partial
          // failure must not be reported as an outright failure — and the
          // rejected names are the part the operator has to act on.
          const failed = res.errors.length;
          toast({
            title: `${toPersianDigits(String(res.uploaded.length))} فایل آپلود شد`,
            description: failed
              ? `${toPersianDigits(String(failed))} فایل رد شد: ${res.errors
                  .map((e) => e.filename)
                  .join("، ")}`
              : files.length === 1
                ? first.name
                : undefined,
            variant: failed ? "destructive" : "default",
          });
        },
      },
    );
    if (!result.ok) {
      toast({ title: "آپلود ناموفق", description: result.error, variant: "destructive" });
    }
    setUploading(false);
    if (fileRef.current) fileRef.current.value = "";
  };

  const remove = async (id: string) => {
    if (!confirm("این فایل حذف شود؟")) return;
    const result = await runMutation(
      () => mediaApi.delete(id),
      {
        fallbackError: "حذف ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
  };

  const moveSelected = async () => {
    if (selected.size === 0) return;
    const target = prompt("پوشه مقصد (خالی = ریشه):", currentFolder ?? "");
    if (target === null) return;
    const result = await runMutation(
      () => mediaApi.move([...selected], target.trim() || null),
      {
        fallbackError: "انتقال ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: (res) =>
          toast({ title: `${toPersianDigits(String(res.moved))} فایل منتقل شد` }),
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const saveFocal = async (x: number, y: number) => {
    if (!focalAsset) return;
    setSavingFocal(true);
    const result = await runMutation(
      () => mediaApi.setFocalPoint(focalAsset.id, x, y),
      {
        fallbackError: "ذخیره ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "نقطه کانونی ذخیره شد" });
          setFocalAsset(null);
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setSavingFocal(false);
  };

  const openDetail = (asset: MediaAsset) => {
    setDetailAsset(asset);
    setDetailAlt(asset.alt_text || "");
    setDetailCaption(asset.caption || "");
    setDetailDescription(asset.description || "");
    setDetailFolder(asset.folder || "");
    setCopiedUrl(false);
  };

  const saveDetail = async () => {
    if (!detailAsset) return;
    setSavingDetail(true);
    const result = await runMutation(
      () =>
        mediaApi.update(detailAsset.id, {
          alt_text: detailAlt,
          caption: detailCaption,
          description: detailDescription,
          folder: detailFolder || null,
        }),
      {
        fallbackError: "ذخیره مشخصات ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "مشخصات رسانه ذخیره شد" });
          setDetailAsset(null);
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setSavingDetail(false);
  };

  // ── Image editing handlers (WordPress parity) ──────────────────────────

  const rotateImage = async (degrees: number) => {
    if (!detailAsset) return;
    setImageBusy("rotate");
    const result = await runMutation(() => mediaEditingApi.rotate(detailAsset.id, degrees), {
      fallbackError: "چرخش تصویر ناموفق بود",
      invalidateKeys: [[MEDIA_QUERY_KEY]],
      onSuccess: () => {
        toast({ title: `چرخش ${degrees}° انجام شد — نسخه جدید ساخته شد` });
        setDetailAsset(null);
      },
    });
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

  const flipImage = async (horizontal: boolean) => {
    if (!detailAsset) return;
    setImageBusy("flip");
    const result = await runMutation(() => mediaEditingApi.flip(detailAsset.id, horizontal), {
      fallbackError: "قرینه‌سازی تصویر ناموفق بود",
      invalidateKeys: [[MEDIA_QUERY_KEY]],
      onSuccess: () => {
        toast({
          title: horizontal
            ? "قرینه افقی انجام شد — نسخه جدید ساخته شد"
            : "قرینه عمودی انجام شد — نسخه جدید ساخته شد",
        });
        setDetailAsset(null);
      },
    });
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

  const resizeImage = async () => {
    if (!detailAsset || !resizeWidth.trim()) return;
    setImageBusy("resize");
    const height = resizeHeight.trim() ? Number(resizeHeight) : undefined;
    const result = await runMutation(
      () => mediaEditingApi.resize(detailAsset.id, { width: Number(resizeWidth), height }),
      {
        fallbackError: "تغییر اندازه ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "تغییر اندازه انجام شد — نسخه جدید ساخته شد" });
          setDetailAsset(null);
          setResizeWidth("");
          setResizeHeight("");
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

  // The crop endpoint has always existed and always created a new asset, so the
  // original is safe to crop against. The rectangle is in source pixels: the
  // preview is a scaled variant, and scaling back is what makes a drag on a
  // small thumbnail land on the pixels the operator pointed at.
  const openCrop = (asset: MediaAsset) => {
    setDetailAsset(asset);
    setCropOpen(true);
    // Default to a centred 80% box so the action is one click, not a drag the
    // operator has to discover.
    const w = Math.round((asset.width ?? 0) * 0.8);
    const h = Math.round((asset.height ?? 0) * 0.8);
    setCrop({
      x: Math.round(((asset.width ?? 0) - w) / 2),
      y: Math.round(((asset.height ?? 0) - h) / 2),
      width: w,
      height: h,
    });
  };

  const applyCrop = async () => {
    if (!detailAsset) return;
    if (crop.width < 1 || crop.height < 1) {
      toast({ title: "ابعد برش باید بزرگ‌تر از صفر باشد", variant: "destructive" });
      return;
    }
    setImageBusy("crop");
    const result = await runMutation(
      () => mediaEditingApi.crop(detailAsset.id, crop),
      {
        fallbackError: "برش تصویر ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "برش انجام شد — نسخه جدید ساخته شد" });
          setCropOpen(false);
          setDetailAsset(null);
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

  const loadExif = async () => {
    if (!detailAsset) return;
    setImageBusy("exif");
    try {
      const data = await mediaEditingApi.exif(detailAsset.id);
      setExifData(data);
      if (Object.keys(data).length === 0) {
        toast({ title: "این تصویر متادیتای EXIF ندارد" });
      }
    } catch {
      toast({ title: "خواندن EXIF ناموفق بود", variant: "destructive" });
    } finally {
      setImageBusy(null);
    }
  };

  const regenerateThumbs = async () => {
    if (!detailAsset) return;
    setImageBusy("thumbs");
    try {
      const res = await mediaEditingApi.regenerateThumbnails(detailAsset.id);
      toast({ title: `بندانگشتی‌ها بازسازی شد (${res.generated.length} سایز)` });
    } catch {
      toast({ title: "بازسازی بندانگشتی‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setImageBusy(null);
    }
  };

  const regenerateAllThumbs = async () => {
    setImageBusy("thumbs");
    try {
      const res = await mediaEditingApi.regenerateAll();
      // Report the skips: a file deleted off-disk is the operator's cue that
      // the count does not add up, and a silent summary would hide it.
      toast({
        title: `بازسازی کامل شد: ${toPersianDigits(res.success)} موفق، ${toPersianDigits(res.skipped ?? 0)} رد شده، ${toPersianDigits(res.failed)} ناموفق`,
        variant: res.failed > 0 ? "destructive" : "default",
      });
    } catch {
      toast({ title: "بازسازی بندانگشتی‌ها ناموفق بود", variant: "destructive" });
    } finally {
      setImageBusy(null);
    }
  };

  const optimizeImage = async () => {
    if (!detailAsset) return;
    setImageBusy("optimize");
    try {
      const res = await mediaEditingApi.optimize(detailAsset.id);
      toast({
        title: `حجم تصویر بهینه شد (${res.savings_pct}٪ کاهش)`,
      });
      void load();
    } catch {
      toast({ title: "بهینه‌سازی ناموفق بود", variant: "destructive" });
    } finally {
      setImageBusy(null);
    }
  };

  const copyUrl = (url: string) => {
    navigator.clipboard.writeText(url);
    setCopiedUrl(true);
    setTimeout(() => setCopiedUrl(false), 2000);
    toast({ title: "آدرس فایل کپی شد" });
  };

  return (
    <div className="space-y-6" dir="rtl">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold flex items-center gap-2">
            <ImageIcon className="h-5 w-5 text-primary" />
            کتابخانه رسانه
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            پوشه‌بندی، انتقال گروهی، نقطه کانونی و واریانت‌های رندرشده
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="h-4 w-4 ms-2" />
            بروزرسانی
          </Button>
          <input
            ref={fileRef}
            type="file"
            multiple
            accept={MEDIA_ACCEPT_ATTRIBUTE}
            className="hidden"
            onChange={(e) => {
              const picked = Array.from(e.target.files ?? []);
              if (picked.length > 0) {
                void upload(
                  picked.slice(0, MEDIA_MAX_BATCH_FILES),
                );
              }
            }}
          />
          <Button size="sm" onClick={() => fileRef.current?.click()} disabled={uploading}>
            <UploadCloud className="h-4 w-4 ms-1" />
            {uploading ? "در حال آپلود..." : "آپلود"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            onClick={() => void regenerateAllThumbs()}
            disabled={imageBusy === "thumbs"}
          >
            <RefreshCw className="h-4 w-4 ms-1" />
            {imageBusy === "thumbs" ? "در حال بازسازی..." : "بازتولید همهٔ تصاویر"}
          </Button>
        </div>
      </div>

      <div className="mb-4">
        <ImageSizeSettingsCard />
      </div>

      <div className="flex gap-4">
        {/* Folder tree */}
        <Card className="w-56 shrink-0 p-4 space-y-1">
          <button
            onClick={() => setCurrentFolder(null)}
            className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm ${
              currentFolder === null ? "bg-primary/10 text-primary" : "hover:bg-muted"
            }`}
          >
            <FolderOpen className="h-4 w-4" />
            همه فایل‌ها
          </button>
          {folders.map((f) => (
            <button
              key={f.path}
              onClick={() => setCurrentFolder(f.path)}
              className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm ${
                currentFolder === f.path ? "bg-primary/10 text-primary" : "hover:bg-muted"
              }`}
            >
              <Folder className="h-4 w-4" />
              <span className="truncate">{f.path}</span>
              <span className="ms-auto text-xs text-muted-foreground">
                {toPersianDigits(String(f.asset_count))}
              </span>
            </button>
          ))}
        </Card>

        {/* Asset grid */}
        <div className="flex-1 space-y-3">
          <Card className="flex flex-col gap-3 p-3 sm:flex-row sm:items-end">
            <div className="relative min-w-[200px] flex-1 space-y-1.5">
              <Label htmlFor="media-search" className="text-[11px]">
                جستجو در کتابخانه
              </Label>
              <div className="relative">
                <Search className="absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  id="media-search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="نام فایل یا متن جایگزین..."
                  className="ps-9"
                />
              </div>
            </div>
            <FilterSelect
              id="media-mime-filter"
              label="نوع فایل"
              value={mimeFilter}
              onChange={setMimeFilter}
              options={MEDIA_MIME_PREFIXES.map((p) => ({ value: p.value, label: p.label }))}
              className="sm:w-40"
            />
            <span className="pb-2 text-xs text-muted-foreground sm:ms-auto">
              {toPersianDigits(String(totalAssets))} فایل
            </span>
          </Card>

          {selected.size > 0 && (
            <Card className="p-3 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {toPersianDigits(String(selected.size))} فایل انتخاب شده
              </span>
              <Button size="sm" variant="outline" onClick={moveSelected}>
                <FolderInput className="h-4 w-4 ms-1" />
                انتقال به پوشه
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setSelected(new Set())}>
                لغو انتخاب
              </Button>
            </Card>
          )}
          {loading ? (
            <div className="flex justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : assets.length === 0 ? (
            <Card className="p-8 text-center text-sm text-muted-foreground">
              {currentFolder ? "این پوشه خالی است" : "هنوز فایلی آپلود نشده است"}
            </Card>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {assets.map((a) => (
                <Card key={a.id} className="overflow-hidden">
                  <button onClick={() => toggleSelect(a.id)} className="block w-full">
                    <ImageWithFallback asset={a} className="h-32 w-full object-cover" />
                  </button>
                  <div className="p-2 space-y-1">
                    <p className="truncate text-xs font-medium" title={a.file_name}>
                      {a.file_name}
                    </p>
                    <div className="flex items-center justify-between">
                      <span className="text-[10px] text-muted-foreground">
                        {fmtSize(a.file_size)}
                        {a.folder ? ` · ${a.folder}` : ""}
                      </span>
                      {selected.has(a.id) && <Badge className="text-[10px]">انتخاب</Badge>}
                    </div>
                    <div className="flex gap-1">
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-1.5"
                        title="مشخصات و جزئیات"
                        onClick={() => openDetail(a)}
                      >
                        <Info className="h-3.5 w-3.5" />
                      </Button>
                      {a.mime_type.startsWith("image/") && (
                        <Button
                          size="sm"
                          variant="ghost"
                          className="h-7 px-1.5"
                          title="نقطه کانونی"
                          onClick={() => setFocalAsset(a)}
                        >
                          <Crosshair className="h-3.5 w-3.5" />
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-1.5 text-destructive"
                        title="حذف"
                        onClick={() => remove(a.id)}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between text-xs">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1 || loading}
              >
                قبلی
              </Button>
              <span className="text-muted-foreground">
                صفحه {toPersianDigits(String(page))} از {toPersianDigits(String(totalPages))}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                disabled={page >= totalPages || loading}
              >
                بعدی
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Focal point dialog */}
      <Dialog open={!!focalAsset} onOpenChange={() => setFocalAsset(null)}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>نقطه کانونی برش</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            روی نقطه‌ای از تصویر کلیک کنید که در برش‌های بعدی حفظ شود.
          </p>
          {focalAsset && (
            <div className="relative mx-auto">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={mediaApi.variantUrl(focalAsset.id, { width: 400 })}
                alt={focalAsset.file_name}
                className="w-full rounded border"
                onClick={(e) => {
                  const rect = (e.target as HTMLImageElement).getBoundingClientRect();
                  const x = (e.clientX - rect.left) / rect.width;
                  const y = (e.clientY - rect.top) / rect.height;
                  void saveFocal(Number(x.toFixed(3)), Number(y.toFixed(3)));
                }}
                style={{ cursor: "crosshair" }}
              />
              {focalAsset.focal_x != null && focalAsset.focal_y != null && (
                <div
                  className="absolute h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-primary bg-primary/30"
                  style={{
                    left: `${focalAsset.focal_x * 100}%`,
                    top: `${focalAsset.focal_y * 100}%`,
                  }}
                />
              )}
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setFocalAsset(null)} disabled={savingFocal}>
              بستن
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Media Detail & Metadata Dialog (WordPress parity) */}
      <Dialog open={!!detailAsset} onOpenChange={() => setDetailAsset(null)}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto" dir="rtl">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-emerald-600" />
              <DialogTitle>مشخصات و جزئیات رسانه</DialogTitle>
            </div>
          </DialogHeader>

          {detailAsset && (
            <div className="space-y-4 py-2">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* Preview */}
                <div className="rounded-xl border border-border overflow-hidden bg-muted flex items-center justify-center p-2 min-h-[180px]">
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={detailAsset.file_url}
                    alt={detailAsset.file_name}
                    className="max-h-56 max-w-full object-contain rounded"
                  />
                </div>

                {/* Metadata details */}
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">نام فایل:</span>
                    <span className="font-bold truncate max-w-[180px]" title={detailAsset.file_name}>
                      {detailAsset.file_name}
                    </span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">نوع فایل (MIME):</span>
                    <span className="font-mono">{detailAsset.mime_type}</span>
                  </div>
                  <div className="flex justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">حجم فایل:</span>
                    <span>{fmtSize(detailAsset.file_size)}</span>
                  </div>
                  {detailAsset.width && detailAsset.height && (
                    <div className="flex justify-between py-1 border-b border-border">
                      <span className="text-muted-foreground">ابعاد تصویر:</span>
                      <span>
                        {toPersianDigits(String(detailAsset.width))} ×{" "}
                        {toPersianDigits(String(detailAsset.height))} پیکسل
                      </span>
                    </div>
                  )}
                  <div className="flex justify-between py-1 border-b border-border">
                    <span className="text-muted-foreground">تاریخ بارگذاری:</span>
                    <span>
                      {toPersianDigits(new Date(detailAsset.created_at).toLocaleDateString("fa-IR"))}
                    </span>
                  </div>

                  {/* Copy URL */}
                  <div className="pt-2">
                    <Label className="text-[11px] text-muted-foreground">نشانی اینترنتی فایل (URL):</Label>
                    <div className="flex items-center gap-1.5 mt-1">
                      <Input
                        readOnly
                        value={detailAsset.file_url}
                        className="h-8 text-xs font-mono dir-ltr truncate"
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => copyUrl(detailAsset.file_url)}
                        className="h-8 px-2 shrink-0 text-xs gap-1"
                      >
                        {copiedUrl ? <Check className="h-3.5 w-3.5 text-emerald-600" /> : <Copy className="h-3.5 w-3.5" />}
                        {copiedUrl ? "کپی شد" : "کپی"}
                      </Button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Editable Fields (WordPress Parity) */}
              <div className="space-y-3 pt-2 border-t border-border">
                <div className="grid gap-1.5">
                  <Label htmlFor="med-alt">متن جایگزین (Alt Text — برای سئو و دسترس‌پذیری)</Label>
                  <Input
                    id="med-alt"
                    value={detailAlt}
                    onChange={(e) => setDetailAlt(e.target.value)}
                    placeholder="توضیح مختصر تصویر برای موتورهای جستجو..."
                    aria-invalid={detailAsset && !detailAlt.trim() ? true : undefined}
                    className={
                      detailAsset && !detailAlt.trim() ? "border-amber-500" : undefined
                    }
                  />
                  {/* Non-blocking, like WordPress: an image with no alt is
                      usable, it is just invisible to screen readers and to
                      image search. Blocking the save would stop operators
                      publishing a product photo over a missing caption. */}
                  {detailAsset && !detailAlt.trim() && (
                    <p className="flex items-center gap-1 text-xs text-amber-600">
                      <AlertTriangle className="h-3 w-3" />
                      این تصویر متن جایگزین ندارد — در جست‌وجوی تصویر و برای صفحه‌خوان‌ها نامرئی می‌ماند
                    </p>
                  )}
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="med-caption">زیرنویس تصویر (Caption)</Label>
                  <Input
                    id="med-caption"
                    value={detailCaption}
                    onChange={(e) => setDetailCaption(e.target.value)}
                    placeholder="زیرنویس نمایش داده شده زیر تصویر در مقالات..."
                  />
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="med-desc">توضیحات کامل (Description)</Label>
                  <Textarea
                    id="med-desc"
                    value={detailDescription}
                    onChange={(e) => setDetailDescription(e.target.value)}
                    placeholder="توضیحات و متادیتای اختصاصی فایل..."
                    rows={3}
                  />
                </div>

                <div className="grid gap-1.5 max-w-xs">
                  <Label htmlFor="med-folder">پوشه دسته‌بندی</Label>
                  <Input
                    id="med-folder"
                    value={detailFolder}
                    onChange={(e) => setDetailFolder(e.target.value)}
                    placeholder="e.g. banners or blog"
                    dir="ltr"
                    className="text-left text-xs font-mono"
                  />
                </div>
              </div>

              {/* Image editing & processing (WordPress parity) */}
              {detailAsset.mime_type?.startsWith("image/") && (
                <div className="space-y-3 border-t border-border pt-3">
                  <div className="text-xs font-semibold">ویرایش و پردازش تصویر</div>

                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void rotateImage(90)}
                    >
                      <RotateCw className="h-4 w-4" /> چرخش ۹۰°
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void rotateImage(270)}
                    >
                      <RotateCcw className="h-4 w-4" /> چرخش ۲۷۰°
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void flipImage(true)}
                      title="قرینه افقی — برای عکس‌هایی که از پشت شیشه یا اسکنر آینه‌ای گرفته شده‌اند"
                    >
                      <FlipHorizontal2 className="h-4 w-4" /> قرینه افقی
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void flipImage(false)}
                      title="قرینه عمودی"
                    >
                      <FlipVertical2 className="h-4 w-4" /> قرینه عمودی
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => {
                        if (detailAsset) openCrop(detailAsset);
                      }}
                    >
                      <Crop className="h-4 w-4" />
                      {imageBusy === "crop" ? "…" : "برش تصویر"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void loadExif()}
                    >
                      <Info className="h-4 w-4" /> EXIF
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void regenerateThumbs()}
                    >
                      <Images className="h-4 w-4" />
                      {imageBusy === "thumbs" ? "…" : "بازسازی بندانگشتی‌ها"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => void optimizeImage()}
                    >
                      <Zap className="h-4 w-4" />
                      {imageBusy === "optimize" ? "…" : "بهینه‌سازی حجم"}
                    </Button>
                  </div>

                  <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                    <div className="grid gap-1">
                      <Label htmlFor="rs-w" className="text-[11px]">
                        عرض
                      </Label>
                      <Input
                        id="rs-w"
                        type="number"
                        value={resizeWidth}
                        onChange={(e) => setResizeWidth(e.target.value)}
                        className="text-xs"
                      />
                    </div>
                    <div className="grid gap-1">
                      <Label htmlFor="rs-h" className="text-[11px]">
                        ارتفاع (خالی = خودکار)
                      </Label>
                      <Input
                        id="rs-h"
                        type="number"
                        value={resizeHeight}
                        onChange={(e) => setResizeHeight(e.target.value)}
                        className="text-xs"
                      />
                    </div>
                    <Button
                      size="sm"
                      className="self-end"
                      disabled={imageBusy !== null || !resizeWidth.trim()}
                      onClick={() => void resizeImage()}
                    >
                      <Scaling className="h-4 w-4" />
                      {imageBusy === "resize" ? "…" : "تغییر اندازه"}
                    </Button>
                  </div>

                  {exifData && (
                    <div className="max-h-40 overflow-auto rounded-md bg-muted/50 p-2 text-[11px]" dir="ltr">
                      {Object.entries(exifData).map(([k, v]) => (
                        <div key={k} className="flex justify-between gap-3">
                          <span className="font-mono text-muted-foreground">{k}</span>
                          <span className="truncate">{String(v)}</span>
                        </div>
                      ))}
                    </div>
                  )}

                  <p className="text-[11px] text-muted-foreground">
                    ویرایش‌ها یک نسخه جدید می‌سازند و فایل اصلی دست‌نخورده می‌ماند.
                  </p>
                </div>
              )}
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setDetailAsset(null)}>
              انصراف
            </Button>
            <Button onClick={saveDetail} disabled={savingDetail} className="bg-emerald-600 hover:bg-emerald-700">
              {savingDetail ? "در حال ذخیره..." : "ذخیره مشخصات"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Crop dialog — the endpoint created a new asset but nothing could reach it */}
      <Dialog open={cropOpen} onOpenChange={(open) => !open && setCropOpen(false)}>
        <DialogContent className="max-w-2xl" dir="rtl">
          <DialogHeader>
            <div className="flex items-center gap-2">
              <Crop className="h-5 w-5 text-emerald-600" />
              <DialogTitle>برش تصویر</DialogTitle>
            </div>
          </DialogHeader>

          {detailAsset && (
            <div className="space-y-3">
              <div className="relative mx-auto w-fit">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={mediaApi.variantUrl(detailAsset.id, { width: 500 })}
                  alt={detailAsset.file_name}
                  className="max-h-72 rounded border"
                />
                {/* Overlaid on the preview in the same proportion the rectangle
                    occupies of the original, so the numbers below and the
                    highlighted area are the same box. */}
                {detailAsset.width && detailAsset.height && crop.width > 0 && (
                  <div
                    className="pointer-events-none absolute border-2 border-primary bg-primary/20"
                    style={{
                      left: `${(crop.x / detailAsset.width) * 100}%`,
                      top: `${(crop.y / detailAsset.height) * 100}%`,
                      width: `${(crop.width / detailAsset.width) * 100}%`,
                      height: `${(crop.height / detailAsset.height) * 100}%`,
                    }}
                  />
                )}
              </div>

              <p className="text-xs text-muted-foreground">
                مختصات بر حسب پیکسل فایل اصلی (
                {toPersianDigits(String(detailAsset.width ?? 0))} ×{" "}
                {toPersianDigits(String(detailAsset.height ?? 0))}) وارد می‌شود.
              </p>

              <div className="grid gap-2 sm:grid-cols-4">
                {(
                  [
                    ["x", "محور افقی", 0, detailAsset.width ?? 0],
                    ["y", "محور عمودی", 0, detailAsset.height ?? 0],
                    ["width", "عرض", 1, detailAsset.width ?? 0],
                    ["height", "ارتفاع", 1, detailAsset.height ?? 0],
                  ] as const
                ).map(([key, label, min, max]) => (
                  <div key={key} className="grid gap-1">
                    <Label htmlFor={`crop-${key}`} className="text-[11px]">
                      {label}
                    </Label>
                    <Input
                      id={`crop-${key}`}
                      type="number"
                      min={min}
                      max={max}
                      value={crop[key]}
                      onChange={(e) =>
                        setCrop((prev) => ({ ...prev, [key]: Number(e.target.value) || 0 }))
                      }
                      className="text-xs"
                    />
                  </div>
                ))}
              </div>

              <div className="flex flex-wrap gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    const w = Math.round((detailAsset.width ?? 0) / 2);
                    const h = Math.round((detailAsset.height ?? 0) / 2);
                    setCrop({
                      x: Math.round(((detailAsset.width ?? 0) - w) / 2),
                      y: Math.round(((detailAsset.height ?? 0) - h) / 2),
                      width: w,
                      height: h,
                    });
                  }}
                >
                  نیمهٔ مرکزی
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() =>
                    setCrop({
                      x: 0,
                      y: 0,
                      width: detailAsset.width ?? 0,
                      height: detailAsset.height ?? 0,
                    })
                  }
                >
                  کل تصویر
                </Button>
              </div>
            </div>
          )}

          <DialogFooter>
            <Button variant="outline" onClick={() => setCropOpen(false)} disabled={imageBusy !== null}>
              انصراف
            </Button>
            <Button
              onClick={() => void applyCrop()}
              disabled={imageBusy !== null}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {imageBusy === "crop" ? "در حال برش..." : "برش و ساخت نسخهٔ جدید"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
