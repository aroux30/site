"use client";

import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
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
  CopyPlus,
  Undo2,
  Redo2,
  Check,
  FileText,
  RotateCw,
  RotateCcw,
  History,
  Images,
  Zap,
  Scaling,
  Search,
  Crop,
  AlertTriangle,
  FlipHorizontal2,
  FlipVertical2,
  FolderPlus,
  LayoutGrid,
  Link2,
  List,
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
  DialogDescription,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { mediaApi, type MediaAsset } from "@/lib/api/media";
import { mediaEditingApi, type MediaEditStep } from "@/lib/api/wp-parity";
import { useAdminMutation, useAdminQuery } from "@/lib/api/admin-query";
import MediaTrashPanel from "@/components/admin/media-trash-panel";
import { MediaDropzone } from "@/components/admin/media-dropzone";
import { FilterSelect } from "@/components/admin/filter-select";
import {
  MEDIA_ACCEPT_ATTRIBUTE,
  MEDIA_MAX_BATCH_FILES,
  MEDIA_MIME_PREFIXES,
} from "@/lib/media-types";
import { toPersianDigits } from "@/lib/utils";
import { ImageSizeSettingsCard } from "@/components/admin/image-size-settings-card";
import { WatermarkSettingsCard } from "@/components/admin/watermark-settings-card";

const MEDIA_QUERY_KEY = "admin-media" as const;

/** One grid page. A 2000-image library is unusable at any smaller page. */
const PAGE_SIZE = 60;

function fmtSize(bytes: number): string {
  if (bytes > 1024 * 1024) return (bytes / 1024 / 1024).toFixed(1) + " MB";
  return Math.max(1, Math.round(bytes / 1024)) + " KB";
}

/**
 * Whether an image is missing its alt text.
 *
 * Prefers the server's `needs_alt_text`, which is the single source of the
 * rule — and falls back to recomputing it only when the field is absent, so a
 * route that predates it still shows the warning. The previous version always
 * recomputed and never read the field, so the server's answer was dead code
 * and the two copies of the rule could drift with nothing to catch it.
 */
function needsAlt(asset: MediaAsset): boolean {
  if (typeof asset.needs_alt_text === "boolean") return asset.needs_alt_text;
  return asset.mime_type.startsWith("image/") && !(asset.alt_text || "").trim();
}

/** اگر فایل فیزیکی روی دیسک نیست (آپلود قدیمی/محیط دیگر)، نمایش بصری ندهیم. */
function ImageWithFallback({ asset, className }: { asset: MediaAsset; className: string }) {
  const [broken, setBroken] = useState(false);
  if (broken || !asset.mime_type.startsWith("image/")) {
    // A PDF is a document, not a broken image: it gets its own icon so a
    // catalogue of brochures does not read as a wall of failures. Anything
    // else non-image (audio, video, zip) keeps the generic glyph.
    const isPdf = asset.mime_type === "application/pdf";
    return (
      <div className="flex h-32 items-center justify-center bg-muted">
        <div className="text-center">
          {isPdf ? (
            <FileText className="mx-auto h-8 w-8 text-rose-500" />
          ) : (
            <ImageIcon className="mx-auto h-8 w-8 text-muted-foreground" />
          )}
          {isPdf && (
            <p className="mt-1 text-[10px] font-medium text-muted-foreground">PDF</p>
          )}
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
  // useSearchParams (below) opts the whole subtree out of static prerendering, so
  // the page is exported as a Suspense boundary around itself. Without it the
  // build fails with "useSearchParams() should be wrapped in a suspense boundary".
  return (
    <Suspense fallback={<MediaPageSkeleton />}>
      <AdminMediaPageInner />
    </Suspense>
  );
}

function AdminMediaPageInner() {
  const { toast } = useToast();
  // ?asset=<id> opens one image straight away. The editor links here when the
  // author clicks "edit this image" on a picture inside a post, so the crop and
  // rotate tools are reachable from the body without hunting through the
  // library — which is the whole gap: those tools existed, but only on this page,
  // and nothing connected the two.
  const searchParams = useSearchParams();
  const router = useRouter();
  const deepLinkId = searchParams?.get("asset") ?? null;
  // Next 15's useSearchParams is read-only. Dropping the param is a router
  // navigation, and `replace` so the dismissed image does not come back when
  // the author presses Back.
  const clearDeepLink = useCallback(() => {
    router.replace("/admin/media", { scroll: false });
  }, [router]);
  const [currentFolder, setCurrentFolder] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // Busy flag for a bulk action, so the buttons cannot be double-fired while a
  // batch of up to 200 files is in flight.
  const [bulkBusy, setBulkBusy] = useState(false);

  // The list was pinned to page 1 with no pager, so a store with more than 60
  // assets could not reach the rest of its own library.
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [mimeFilter, setMimeFilter] = useState("");
  // WordPress's "Unattached" filter. Worth having because it is the only way
  // to find an upload nobody has used yet, which is exactly the file an
  // operator wants to delete when the disk fills up.
  const [unattachedOnly, setUnattachedOnly] = useState(false);
  // Grid or list. The grid answers "what do these look like", which is most of
  // the time; the list answers "what is in here and when did it arrive", which
  // is the question when the library is a thousand files and the operator is
  // looking for one of them rather than browsing.
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  // WordPress's "uploaded between". Reaching for it is almost always "what
  // arrived this week", because that is when the disk or a mistake is.
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  // focal point dialog
  const [focalAsset, setFocalAsset] = useState<MediaAsset | null>(null);
  const [savingFocal, setSavingFocal] = useState(false);

  // create-folder. A folder used to exist only once something was uploaded into
  // it, so laying out products/shoes before the first product photo was not
  // possible; this is the affordance that makes an empty folder a real thing.
  const [newFolderOpen, setNewFolderOpen] = useState(false);
  const [newFolderPath, setNewFolderPath] = useState("");
  const [creatingFolder, setCreatingFolder] = useState(false);

  // Side-load from a URL. WordPress's "Add media from URL": the operator has a
  // link (a supplier's photo, a press image) and no reason to download it to
  // their machine and upload it back. The server fetches it behind the SSRF
  // guard; this dialog is only the way the link gets there.
  const [sideloadOpen, setSideloadOpen] = useState(false);
  const [sideloadUrl, setSideloadUrl] = useState("");
  const [sideloading, setSideloading] = useState(false);

  // detail & metadata dialog (WordPress parity: title, caption, description, alt_text)
  const [detailAsset, setDetailAsset] = useState<MediaAsset | null>(null);
  const [detailAlt, setDetailAlt] = useState("");
  const [detailTitle, setDetailTitle] = useState("");
  const [detailCaption, setDetailCaption] = useState("");
  const [detailDescription, setDetailDescription] = useState("");
  const [detailFolder, setDetailFolder] = useState("");
  const [detailPostId, setDetailPostId] = useState("");
  const [savingAttach, setSavingAttach] = useState(false);
  const [savingDetail, setSavingDetail] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  // image editing (crop/resize/rotate/EXIF/thumbnails/optimize/replace/duplicate)
  const [imageBusy, setImageBusy] = useState<
    | "rotate"
    | "resize"
    | "thumbs"
    | "optimize"
    | "exif"
    | "crop"
    | "flip"
    | "restore"
    | "replace"
    | "duplicate"
    | null
  >(null);
  // The edit chain, fetched on demand rather than with the asset: most assets
  // were never edited and have no chain to show.
  const [editHistory, setEditHistory] = useState<MediaEditStep[]>([]);
  const [resizeWidth, setResizeWidth] = useState("");
  const [resizeHeight, setResizeHeight] = useState("");
  const [exifData, setExifData] = useState<Record<string, unknown> | null>(null);
  const [cropOpen, setCropOpen] = useState(false);
  const [crop, setCrop] = useState({ x: 0, y: 0, width: 0, height: 0 });

  const fileRef = useRef<HTMLInputElement>(null);
  // The replace picker. A dedicated input because the file dialog has to open
  // from the detail dialog, and reusing the upload input would also trigger
  // the page-level upload handler.
  const replaceRef = useRef<HTMLInputElement>(null);

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
    queryKey: [MEDIA_QUERY_KEY, currentFolder ?? "", page, search, mimeFilter,
      unattachedOnly, dateFrom, dateTo],
    queryFn: async () => {
      const [list, flds] = await Promise.allSettled([
        mediaApi.list({
          page,
          page_size: PAGE_SIZE,
          folder: currentFolder === null ? undefined : currentFolder,
          search: search.trim() || undefined,
          mime_type: mimeFilter || undefined,
          unattached: unattachedOnly || undefined,
          // Sent as instants, not date strings. A bare "2026-10-01" would be
          // parsed by the server in its own zone and could land a day early,
          // which quietly drops the first morning of the range.
          created_from: dateFrom
            ? new Date(`${dateFrom}T00:00:00`).toISOString()
            : undefined,
          created_to: dateTo
            ? new Date(`${dateTo}T23:59:59`).toISOString()
            : undefined,
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
  }, [currentFolder, search, mimeFilter, unattachedOnly, dateFrom, dateTo]);

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

  const sideload = async () => {
    const url = sideloadUrl.trim();
    if (!url) return;
    setSideloading(true);
    const result = await runMutation(
      () => mediaApi.sideload({ url, folder: currentFolder ?? undefined }),
      {
        fallbackError: "دریافت تصویر از URL ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({ title: "تصویر از URL اضافه شد" });
          setSideloadOpen(false);
          setSideloadUrl("");
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setSideloading(false);
  };

  const remove = async (id: string) => {
    // Ask what uses this file first. Deleting an image that is a published
    // post's cover takes the cover with it, and the only warning used to be
    // "are you sure" — so the loss was discovered on the storefront.
    let used = 0;
    let where = "";
    try {
      const usage = await mediaApi.usage(id);
      used = usage.total;
      where = usage.summary;
    } catch {
      // A usage lookup that fails must not block the delete: the server
      // refuses a referenced delete anyway, so the worst case is that the
      // admin is not warned before the server declines.
    }

    if (used > 0) {
      const ok = confirm(
        `این فایل هنوز استفاده می‌شود (${where}).\n` +
          `با حذف آن، ${used} مورد ارجاع از کار می‌افتد.\n\n` +
          "اگر مطمئنید، حذف را ادامه دهید؛ در غیر این صورت انصراف دهید.",
      );
      if (!ok) return;
      const result = await runMutation(
        () => mediaApi.delete(id, { force: true }),
        { fallbackError: "حذف ناموفق بود", invalidateKeys: [[MEDIA_QUERY_KEY]] },
      );
      if (!result.ok) toast({ title: result.error, variant: "destructive" });
      return;
    }

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

  // Bulk delete. The library offered only "move selected", so clearing 40
  // images meant 40 confirmations. The confirmation names the count and says
  // the files go to the trash rather than vanishing, because "delete" on a
  // product library reads as permanent to an operator.
  const deleteSelected = async () => {
    if (selected.size === 0) return;
    const count = selected.size;
    if (
      !confirm(
        `${count} فایل به سطل زباله منتقل شود؟

` +
          "این فایل‌ها از کتابخانه پاک می‌شوند ولی روی سرور می‌مانند و از بخش سطل زباله قابل بازگردانی هستند.",
      )
    ) {
      return;
    }
    setBulkBusy(true);
    try {
      const res = await mediaApi.bulkTrash([...selected]);
      // Report the refusals by name. A silent partial delete is the failure
      // mode here: the admin sees the grid refresh and assumes all of it worked.
      if (res.failed > 0) {
        const reasons = res.results
          .filter((r) => r.ok === false)
          .map((r) => String(r.error ?? "نامشخص"))
          .filter((e, i, arr) => arr.indexOf(e) === i)
          .slice(0, 3);
        toast({
          title: `${res.ok} فایل منتقل شد، ${res.failed} فایل منتقل نشد`,
          description: reasons.join(" — "),
          variant: "destructive",
        });
      } else {
        toast({ title: `${toPersianDigits(String(res.ok))} فایل به سطل زباله منتقل شد` });
      }
      // Only the files that actually moved are dropped from the selection; the
      // refused ones stay selected so the operator can deal with them.
      const moved = new Set(
        res.results.filter((r) => r.ok === true).map((r) => String(r.id)),
      );
      setSelected(new Set([...selected].filter((id) => !moved.has(id))));
      await load();
    } catch {
      toast({ title: "حذف گروهی ناموفق بود", variant: "destructive" });
    } finally {
      setBulkBusy(false);
    }
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
    setDetailTitle(asset.title || "");
    setDetailCaption(asset.caption || "");
    setDetailDescription(asset.description || "");
    setDetailFolder(asset.folder || "");
    setDetailPostId(asset.post_id || "");
    setCopiedUrl(false);
    // The chain belongs to the asset being opened. Carrying the previous one's
    // steps over would put one image's history under another image.
    setEditHistory([]);
  };

  /**
   * Open the image named by ?asset=<id>, once.
   *
   * A deep link to a deleted or moved asset has to say so rather than sitting
   * on a spinner: the author clicked "edit this image" inside a post and
   * nothing happening looks like a broken button. Clearing the param stops the
   * effect from re-running on every render, which would re-fetch forever.
   */
  const [deepLinkAttempted, setDeepLinkAttempted] = useState(false);
  useEffect(() => {
    if (!deepLinkId || deepLinkAttempted) return;
    setDeepLinkAttempted(true);
    let cancelled = false;
    (async () => {
      try {
        const asset = await mediaApi.get(deepLinkId);
        if (!cancelled) openDetail(asset);
      } catch {
        if (!cancelled) {
          toast({
            title: "تصویر مورد نظر پیدا نشد",
            description: "ممکن است حذف یا جابه‌جا شده باشد.",
            variant: "destructive",
          });
          clearDeepLink();
        }
      }
    })();
    return () => {
      cancelled = true;
    };
    // openDetail and setSearchParams are stable enough for this one-shot fetch;
    // the guard flag, not the dependency list, is what prevents the loop.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [deepLinkId, deepLinkAttempted]);

  const closeDetail = () => {
    setDetailAsset(null);
    setEditHistory([]);
    // Drop the deep link on close so reopening the page does not resurrect the
    // same dialog the author just dismissed.
    if (deepLinkId) clearDeepLink();
  };

  /** Attach or detach the open asset. Two buttons rather than one input plus a
   *  save, because "attached to nothing" is a deliberate state an operator
   *  sets — it is not the absence of a value, and letting a blank field mean it
   *  would detach files nobody asked about. */
  const handleAttach = async (postId: string) => {
    if (!detailAsset) return;
    const trimmed = postId.trim();
    if (!trimmed) return;
    setSavingAttach(true);
    const res = await runMutation(
      () => mediaApi.attachToPost(detailAsset.id, trimmed),
      {
        fallbackError: "اتصال تصویر به نوشته انجام نشد",
        onSuccess: (updated) => {
          setDetailPostId(updated.post_id || "");
          setDetailAsset(updated);
        },
        invalidateKeys: [[MEDIA_QUERY_KEY]],
      },
    );
    setSavingAttach(false);
    if (res.ok) toast({ title: "تصویر به نوشته متصل شد" });
  };

  const handleCreateFolder = async () => {
    const path = newFolderPath.trim();
    if (!path) return;
    setCreatingFolder(true);
    const res = await runMutation(() => mediaApi.createFolder(path), {
      fallbackError: "ساخت پوشه انجام نشد",
      invalidateKeys: [[MEDIA_QUERY_KEY]],
    });
    setCreatingFolder(false);
    if (!res.ok) return;
    if (res.data.created) {
      toast({ title: "پوشه ساخته شد" });
    } else {
      // Creating something that already exists is a double-click, not a
      // fault. Saying so keeps the operator from retrying a button that works.
      toast({ title: "این پوشه از قبل وجود دارد" });
    }
    setNewFolderPath("");
    setNewFolderOpen(false);
  };

  const handleDetach = async () => {
    if (!detailAsset) return;
    setSavingAttach(true);
    const res = await runMutation(
      () => mediaApi.attachToPost(detailAsset.id, null),
      {
        fallbackError: "برداشتن اتصال تصویر انجام نشد",
        onSuccess: (updated) => {
          setDetailPostId("");
          setDetailAsset(updated);
        },
        invalidateKeys: [[MEDIA_QUERY_KEY]],
      },
    );
    setSavingAttach(false);
    if (res.ok) toast({ title: "اتصال تصویر به نوشته برداشته شد" });
  };

  const saveDetail = async () => {
    if (!detailAsset) return;
    setSavingDetail(true);
    const result = await runMutation(
      () =>
        mediaApi.update(detailAsset.id, {
          alt_text: detailAlt,
          title: detailTitle || null,
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

  // Replace the bytes behind the asset while its URL stays the same. The
  // confirmation says that explicitly, because "replace" and "re-upload" sound
  // like the same operation and only one of them keeps the existing links.
  const replaceFile = async (file: File) => {
    if (!detailAsset) return;
    setImageBusy("replace");
    const result = await runMutation(() => mediaApi.replaceFile(detailAsset.id, file), {
      fallbackError: "جایگزینی فایل ناموفق بود",
      invalidateKeys: [[MEDIA_QUERY_KEY]],
      onSuccess: () => {
        toast({
          title: "فایل جایگزین شد",
          description: "نشانی فایل تغییر نکرده؛ لینک‌های موجود هنوز کار می‌کنند.",
        });
        setDetailAsset(null);
      },
    });
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
    if (replaceRef.current) replaceRef.current.value = "";
  };

  // ── Image editing handlers (WordPress parity) ──────────────────────────

  const loadEditHistory = async () => {
    if (!detailAsset) return;
    try {
      setEditHistory(await mediaEditingApi.history(detailAsset.id));
    } catch {
      setEditHistory([]);
      toast({ title: "خواندن تاریخچه‌ی ویرایش ناموفق بود", variant: "destructive" });
    }
  };

  const restoreOriginal = async () => {
    if (!detailAsset) return;
    setImageBusy("restore");
    const result = await runMutation(
      () => mediaEditingApi.restoreOriginal(detailAsset.id),
      {
        fallbackError: "بازگردانی نسخه‌ی اصلی ناموفق بود",
        invalidateKeys: [[MEDIA_QUERY_KEY]],
        onSuccess: () => {
          toast({
            title: "نسخه‌ی اصلی بازگردانده شد",
            description:
              "فایل‌های ویرایش‌شده در کتابخانه می‌مانند؛ آن‌ها حذف نمی‌شوند چون ممکن است محصول یا مطلبی به آن‌ها لینک داده باشد.",
          });
          setDetailAsset(null);
          setEditHistory([]);
        },
      },
    );
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

  /** Undo/redo walk the edit chain. Every edit is its own asset linked by
   *  `source_asset_id`, so "undo" is opening the parent and "redo" the child —
   *  nothing is rewritten and no step is lost, which is what makes repeated
   *  undo/redo safe. */
  const navigateChain = (direction: "undo" | "redo") => {
    if (!detailAsset || editHistory.length === 0) return;
    const currentIndex = editHistory.findIndex((s) => s.is_current);
    if (currentIndex === -1) return;
    const targetIndex = direction === "undo" ? currentIndex - 1 : currentIndex + 1;
    if (targetIndex < 0 || targetIndex >= editHistory.length) return;
    const target = editHistory[targetIndex];
    if (!target) return;
    // Open the target step in the same dialog: its own history list will
    // reflect its position, so the operator can keep stepping.
    const asAsset = assets.find((a) => a.id === target.id);
    if (asAsset) {
      setDetailAsset(asAsset);
      setEditHistory([]);
      void loadHistoryFor(target.id);
    } else {
      toast({
        title: "این نسخه در صفحه‌ی فعلی کتابخانه نیست",
        description: "برای دیدنش به صفحه‌ی مربوطه بروید یا فهرست را بازخوانی کنید.",
        variant: "destructive",
      });
    }
  };

  const loadHistoryFor = async (assetId: string) => {
    try {
      setEditHistory(await mediaEditingApi.history(assetId));
    } catch {
      setEditHistory([]);
    }
  };

  const duplicateImage = async () => {
    if (!detailAsset) return;
    setImageBusy("duplicate");
    const result = await runMutation(() => mediaEditingApi.duplicate(detailAsset.id), {
      fallbackError: "ساخت کپی ناموفق بود",
      invalidateKeys: [[MEDIA_QUERY_KEY]],
      onSuccess: () => {
        toast({
          title: "کپی ساخته شد",
          description: "فایل جدید مستقل است و در زنجیره‌ی ویرایش این تصویر قرار نمی‌گیرد.",
        });
        setDetailAsset(null);
        setEditHistory([]);
      },
    });
    if (!result.ok) toast({ title: result.error, variant: "destructive" });
    setImageBusy(null);
  };

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

  // A drop is capped exactly like the file dialog, and silently discarding the
  // overflow would look like the upload worked: the admin dropped 40 photos
  // and 20 appeared with no explanation.
  const acceptDropped = useCallback((dropped: File[]) => {
    if (dropped.length > MEDIA_MAX_BATCH_FILES) {
      toast({
        title: `حداکثر ${MEDIA_MAX_BATCH_FILES} فایل در هر بار`,
        description: `${MEDIA_MAX_BATCH_FILES} فایل اول آپلود می‌شود؛ ${dropped.length - MEDIA_MAX_BATCH_FILES} فایل نادیده گرفته شد.`,
        variant: "destructive",
      });
    }
    void upload(dropped.slice(0, MEDIA_MAX_BATCH_FILES));
  }, [upload, toast]);

  return (
    <MediaDropzone
      onFiles={acceptDropped}
      disabled={uploading}
      hint={`حداکثر ${MEDIA_MAX_BATCH_FILES} فایل در هر بار — ${MEDIA_ACCEPT_ATTRIBUTE}`}
    >
    <div className="space-y-6" dir="rtl">
      <MediaTrashPanel onChanged={load} />
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
          <Button size="sm" variant="outline" onClick={() => setSideloadOpen(true)}>
            <Link2 className="h-4 w-4 ms-1" />
            افزودن از URL
          </Button>
        </div>
      </div>

      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        <ImageSizeSettingsCard />
        <WatermarkSettingsCard />
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
            <label
              htmlFor="media-unattached-filter"
              className="flex cursor-pointer items-center gap-2 pb-2 text-sm"
            >
              <input
                id="media-unattached-filter"
                type="checkbox"
                checked={unattachedOnly}
                onChange={(e) => {
                  setUnattachedOnly(e.target.checked);
                  setPage(1);
                }}
                className="h-4 w-4 rounded border-input"
              />
              فقط پیوست‌نشده
            </label>

            {/* WordPress's "uploaded between". Two date inputs rather than a
                range picker: the picker is a bigger dependency for a filter an
                operator uses once a week, and two <input type="date"> are
                keyboard- and mobile-friendly for free. */}
            <div className="flex items-center gap-1.5 pb-1 text-xs">
              <Label htmlFor="media-date-from" className="text-[11px] text-muted-foreground">
                از تاریخ
              </Label>
              <Input
                id="media-date-from"
                type="date"
                value={dateFrom}
                onChange={(e) => {
                  setDateFrom(e.target.value);
                  setPage(1);
                }}
                className="h-9 w-36 text-xs"
              />
              <Label htmlFor="media-date-to" className="text-[11px] text-muted-foreground">
                تا تاریخ
              </Label>
              <Input
                id="media-date-to"
                type="date"
                value={dateTo}
                onChange={(e) => {
                  setDateTo(e.target.value);
                  setPage(1);
                }}
                className="h-9 w-36 text-xs"
              />
              {(dateFrom || dateTo) && (
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    setDateFrom("");
                    setDateTo("");
                    setPage(1);
                  }}
                >
                  پاک کردن
                </Button>
              )}
            </div>

            {/* Grid shows what the images look like, list shows what is in
                here and when it arrived. Both are answers to different
                questions, so this is a toggle rather than a setting. */}
            <div className="flex items-center gap-1 pb-1">
              <Button
                size="sm"
                variant={viewMode === "grid" ? "default" : "outline"}
                onClick={() => setViewMode("grid")}
                aria-pressed={viewMode === "grid"}
              >
                <LayoutGrid className="h-4 w-4" />
                <span className="sr-only">نمای شبکه‌ای</span>
              </Button>
              <Button
                size="sm"
                variant={viewMode === "list" ? "default" : "outline"}
                onClick={() => setViewMode("list")}
                aria-pressed={viewMode === "list"}
              >
                <List className="h-4 w-4" />
                <span className="sr-only">نمای فهرستی</span>
              </Button>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setNewFolderOpen(true)}
            >
              <FolderPlus className="h-4 w-4" />
              پوشه‌ی جدید
            </Button>
            <span className="pb-2 text-xs text-muted-foreground sm:ms-auto">
              {toPersianDigits(String(totalAssets))} فایل
            </span>
          </Card>

          {selected.size > 0 && (
            <Card className="p-3 flex items-center gap-2">
              <span className="text-sm text-muted-foreground">
                {toPersianDigits(String(selected.size))} فایل انتخاب شده
              </span>
              <Button size="sm" variant="outline" onClick={moveSelected} disabled={bulkBusy}>
                <FolderInput className="h-4 w-4 ms-1" />
                انتقال به پوشه
              </Button>
              <Button
                size="sm"
                variant="destructive"
                onClick={deleteSelected}
                disabled={bulkBusy}
              >
                <Trash2 className="h-4 w-4 ms-1" />
                انتقال به سطل زباله
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
          ) : viewMode === "list" ? (
            /* List view. Answers "what is in here and when did it arrive",
               which the grid cannot: at forty files a page a grid shows a
               wall of thumbnails and no dates at all. Selection is kept —
               an operator who selects three rows here then switches back must
               not lose the selection, because the bulk bar is above both. */
            <Card className="overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="border-b bg-muted/40 text-xs text-muted-foreground">
                    <tr>
                      <th className="w-10 p-2" />
                      <th className="p-2 text-start font-medium">پیش‌نمایش</th>
                      <th className="p-2 text-start font-medium">نام فایل</th>
                      <th className="p-2 text-start font-medium">نوع</th>
                      <th className="p-2 text-start font-medium">اندازه</th>
                      <th className="p-2 text-start font-medium">پوشه</th>
                      <th className="p-2 text-start font-medium">تاریخ</th>
                    </tr>
                  </thead>
                  <tbody>
                    {assets.map((a) => (
                      <tr
                        key={a.id}
                        className={`border-b last:border-0 ${
                          selected.has(a.id) ? "bg-primary/5" : ""
                        }`}
                      >
                        <td className="p-2">
                          <input
                            type="checkbox"
                            checked={selected.has(a.id)}
                            onChange={() => toggleSelect(a.id)}
                            aria-label={`انتخاب ${a.file_name}`}
                          />
                        </td>
                        <td className="p-2">
                          <button
                            onClick={() => openDetail(a)}
                            className="block h-10 w-14 overflow-hidden rounded"
                          >
                            <ImageWithFallback asset={a} className="h-10 w-14 object-cover" />
                          </button>
                        </td>
                        <td className="p-2">
                          <button
                            onClick={() => openDetail(a)}
                            className="text-start font-medium hover:underline"
                            dir="ltr"
                          >
                            {a.file_name}
                          </button>
                          {needsAlt(a) && (
                            <span
                              className="ms-2 text-[10px] text-amber-600"
                              title="این تصویر متن جایگزین ندارد"
                            >
                              بدون متن جایگزین
                            </span>
                          )}
                        </td>
                        <td className="p-2 text-xs text-muted-foreground" dir="ltr">
                          {a.mime_type}
                        </td>
                        <td className="p-2 text-xs text-muted-foreground">
                          {fmtSize(a.file_size)}
                        </td>
                        <td className="p-2 text-xs text-muted-foreground" dir="ltr">
                          {a.folder || "—"}
                        </td>
                        <td className="p-2 text-xs text-muted-foreground">
                          {toPersianDigits(
                            new Date(a.created_at).toLocaleDateString("fa-IR"),
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>
          ) : (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {assets.map((a) => (
                <Card key={a.id} className="overflow-hidden">
                  <button onClick={() => toggleSelect(a.id)} className="block w-full">
                    <ImageWithFallback asset={a} className="h-32 w-full object-cover" />
                  </button>
                  {/* The API has computed needs_alt_text for this since the
                      schema shipped, and nothing read it: the operator had to
                      open every image to find out. Non-blocking, like WordPress —
                      the image still renders, it is just invisible to screen
                      readers and to image search. */}
                  {needsAlt(a) && (
                    <div
                      className="flex items-center gap-1 border-t border-amber-500/30 bg-amber-500/10 px-2 py-1 text-[10px] text-amber-700 dark:text-amber-400"
                      title="این تصویر متن جایگزین ندارد"
                    >
                      <AlertTriangle className="h-3 w-3 shrink-0" />
                      بدون متن جایگزین
                    </div>
                  )}
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

      {/* Create-folder dialog */}
      <Dialog open={newFolderOpen} onOpenChange={setNewFolderOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>ساخت پوشه‌ی جدید</DialogTitle>
            <DialogDescription>
              مسیر را با «/» جدا کنید. پوشه می‌تواند خالی بماند — لازم نیست اول
              فایلی داخلش آپلود کنید.
            </DialogDescription>
          </DialogHeader>
          <Input
            id="media-new-folder"
            value={newFolderPath}
            onChange={(e) => setNewFolderPath(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void handleCreateFolder();
            }}
            placeholder="products/shoes"
            dir="ltr"
            className="text-left text-sm"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setNewFolderOpen(false)}>
              انصراف
            </Button>
            <Button onClick={handleCreateFolder} disabled={creatingFolder || !newFolderPath.trim()}>
              {creatingFolder ? "در حال ساخت..." : "ساخت"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      {/* Side-load from a URL */}
      <Dialog open={sideloadOpen} onOpenChange={setSideloadOpen}>
        <DialogContent className="max-w-md" dir="rtl">
          <DialogHeader>
            <DialogTitle>افزودن تصویر از URL</DialogTitle>
            <DialogDescription>
              نشانی مستقیم تصویر را بچسبانید. سرور آن را دریافت و در کتابخانه
              ذخیره می‌کند — آدرس‌های داخلی و خصوصی برای جلوگیری از SSRF رد می‌شوند.
            </DialogDescription>
          </DialogHeader>
          <Input
            id="media-sideload-url"
            value={sideloadUrl}
            onChange={(e) => setSideloadUrl(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") void sideload();
            }}
            placeholder="https://example.com/photo.jpg"
            dir="ltr"
            className="text-left text-sm"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setSideloadOpen(false)}>
              انصراف
            </Button>
            <Button onClick={() => void sideload()} disabled={sideloading || !sideloadUrl.trim()}>
              {sideloading ? "در حال دریافت..." : "دریافت و ذخیره"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>

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
                {/* Preview. Three shapes: a PDF gets the browser's own viewer
                    in an iframe (no PDF library is in the project by design,
                    and the browser already has one); an image gets the img;
                    anything else gets the icon. The PDF branch is what was
                    missing — a PDF showed the same broken-image glyph as an
                    audio file, so an operator could not tell a good upload
                    from a bad one without downloading it. */}
                <div className="rounded-xl border border-border overflow-hidden bg-muted flex items-center justify-center p-2 min-h-[180px]">
                  {detailAsset.mime_type === "application/pdf" ? (
                    <iframe
                      src={detailAsset.file_url}
                      title={detailAsset.file_name}
                      className="h-56 w-full rounded bg-white"
                    />
                  ) : detailAsset.mime_type.startsWith("image/") ? (
                    /* eslint-disable-next-line @next/next/no-img-element */
                    <img
                      src={detailAsset.file_url}
                      alt={detailAsset.file_name}
                      className="max-h-56 max-w-full object-contain rounded"
                    />
                  ) : (
                    <div className="text-center text-muted-foreground">
                      <FileText className="mx-auto h-10 w-10" />
                      <p className="mt-1 text-xs">{detailAsset.mime_type}</p>
                    </div>
                  )}
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
                {/* WordPress's first attachment field, in its order: Title,
                    Alt, Caption, Description. Optional — an empty title means
                    the library keeps showing the file name. */}
                <div className="grid gap-1.5">
                  <Label htmlFor="med-title">عنوان رسانه (Title)</Label>
                  <Input
                    id="med-title"
                    value={detailTitle}
                    onChange={(e) => setDetailTitle(e.target.value)}
                    placeholder="مثلاً: کفش دویدن قرمز — نمای از پهلو"
                  />
                </div>

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

                {/* WordPress's "Attached to". A post id rather than a picker:
                    the store's post list is large and a select over it would be
                    slower than typing the id, which the operator usually has
                    from the post they are looking at. The "detach" button is
                    what makes this column useful — without it a file could be
                    attached but never unattached. */}
                <div className="grid gap-1.5 max-w-xs">
                  <Label htmlFor="med-post">نوشته‌ی متصل (شناسه)</Label>
                  <div className="flex items-center gap-1.5">
                    <Input
                      id="med-post"
                      value={detailPostId}
                      onChange={(e) => setDetailPostId(e.target.value)}
                      // onBlur, not onChange: an attach fires on every
                      // keystroke otherwise, and a half-typed uuid would 404
                      // the moment the first character landed.
                      onBlur={() => {
                        if (
                          detailPostId.trim() &&
                          detailPostId.trim() !== (detailAsset.post_id || "")
                        ) {
                          void handleAttach(detailPostId);
                        }
                      }}
                      placeholder={detailAsset.post_id ?? "پیوست‌نشده"}
                      dir="ltr"
                      className="text-left text-xs font-mono"
                    />
                    {detailAsset.post_id && (
                      <Button
                        type="button"
                        size="sm"
                        variant="outline"
                        onClick={handleDetach}
                        disabled={savingAttach}
                      >
                        جدا کردن
                      </Button>
                    )}
                  </div>
                </div>
              </div>

              {/* Image editing & processing (WordPress parity) */}
              {detailAsset.mime_type?.startsWith("image/") && (
                <div className="space-y-3 border-t border-border pt-3">
                  <div className="text-xs font-semibold">ویرایش و پردازش تصویر</div>

                  {/* Edit chain: every edit created a new file with no link to
                      its parent, so there was no way back to the original. The
                      steps are now recorded, and the root is one click away. */}
                  {detailAsset.source_asset_id && (
                    <div className="flex flex-wrap items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-2.5">
                      <History className="h-4 w-4 shrink-0 text-amber-600" />
                      <span className="text-xs text-amber-800 dark:text-amber-300">
                        این فایل حاصل ویرایش است
                        {detailAsset.edit_operation
                          ? ` (${detailAsset.edit_operation})`
                          : ""}
                        .
                      </span>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-xs"
                        disabled={imageBusy !== null}
                        onClick={() => void restoreOriginal()}
                      >
                        {imageBusy === "restore" ? (
                          "…"
                        ) : (
                          <>
                            <RotateCcw className="h-3.5 w-3.5" /> بازگردانی به اصل
                          </>
                        )}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 gap-1 text-xs"
                        disabled={imageBusy !== null}
                        onClick={() => void loadEditHistory()}
                      >
                        <History className="h-3.5 w-3.5" /> تاریخچه
                      </Button>
                      {/* Undo/redo step along the chain. Enabled from the
                          loaded history, so they cannot fire before there is
                          anywhere to go. */}
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-xs"
                        disabled={
                          imageBusy !== null ||
                          editHistory.findIndex((s) => s.is_current) <= 0
                        }
                        onClick={() => navigateChain("undo")}
                        title="واگرد — یک قدم به عقب در زنجیره‌ی ویرایش"
                      >
                        <Undo2 className="h-3.5 w-3.5" /> واگرد
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-xs"
                        disabled={
                          imageBusy !== null ||
                          editHistory.length === 0 ||
                          editHistory.findIndex((s) => s.is_current) === -1 ||
                          editHistory.findIndex((s) => s.is_current) >=
                            editHistory.length - 1
                        }
                        onClick={() => navigateChain("redo")}
                        title="ازنو — یک قدم به جلو در زنجیره‌ی ویرایش"
                      >
                        <Redo2 className="h-3.5 w-3.5" /> ازنو
                      </Button>
                      {/* Save-as-copy: a standalone asset, not another link
                          in this chain. */}
                      <Button
                        variant="outline"
                        size="sm"
                        className="h-7 gap-1 text-xs"
                        disabled={imageBusy !== null}
                        onClick={() => void duplicateImage()}
                        title="ذخیره به‌عنوان کپی مستقل"
                      >
                        {imageBusy === "duplicate" ? (
                          "…"
                        ) : (
                          <>
                            <CopyPlus className="h-3.5 w-3.5" /> ذخیره به‌عنوان کپی
                          </>
                        )}
                      </Button>
                    </div>
                  )}

                  {/* Only meaningful once a chain exists: an un-edited upload
                      has no steps to show. */}
                  {editHistory.length > 0 && (
                    <ol className="space-y-1.5 rounded-lg border border-border bg-muted/40 p-3 text-xs">
                      {editHistory.map((step) => (
                        <li
                          key={step.id}
                          className="flex items-center gap-2 rounded px-1 hover:bg-background/60"
                        >
                          <span
                            className={
                              step.is_current
                                ? "font-bold text-emerald-600"
                                : "text-muted-foreground"
                            }
                          >
                            {step.is_root
                              ? "نسخه‌ی اصلی"
                              : step.operation === "crop"
                                ? "برش"
                                : step.operation === "resize"
                                  ? "تغییر اندازه"
                                  : step.operation === "rotate"
                                    ? "چرخش"
                                    : step.operation === "flip"
                                      ? "قرینه"
                                      : step.operation ?? "ویرایش"}
                          </span>
                          <span className="truncate font-mono text-[11px] text-muted-foreground" dir="ltr">
                            {step.file_name}
                          </span>
                          {step.width && step.height && (
                            <span className="text-[11px] text-muted-foreground">
                              ({toPersianDigits(String(step.width))}×
                              {toPersianDigits(String(step.height))})
                            </span>
                          )}
                          {step.is_current && (
                            <Badge variant="outline" className="text-[10px]">
                              فعلی
                            </Badge>
                          )}
                        </li>
                      ))}
                    </ol>
                  )}

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
                    {/* Replace keeps the URL. It is the operation for "the
                        product photo changed", where delete + re-upload
                        would break every page that already points here. */}
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={imageBusy !== null}
                      onClick={() => replaceRef.current?.click()}
                      title="فایل جدیدی با همان نشانی اینترنتی جایگزین شود"
                    >
                      <UploadCloud className="h-4 w-4" />
                      {imageBusy === "replace" ? "…" : "جایگزینی فایل"}
                    </Button>
                    <input
                      ref={replaceRef}
                      type="file"
                      className="hidden"
                      accept={MEDIA_ACCEPT_ATTRIBUTE}
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) void replaceFile(file);
                      }}
                    />
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

              {/* Ready-made ratios. WordPress's crop tool offers the registered
                  image sizes (thumbnail/medium/large) plus a free crop; the
                  ratios here are the storefront's real ones — a square product
                  tile, 4:3 and 16:9 banners. The largest centered box with the
                  chosen ratio that fits inside the image is selected, so the
                  preset never asks for pixels that do not exist. */}
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[11px] text-muted-foreground">نسبت آماده:</span>
                {(
                  [
                    ["۱:۱", 1, 1],
                    ["۴:۳", 4, 3],
                    ["۳:۴", 3, 4],
                    ["۱۶:۹", 16, 9],
                    ["۹:۱۶", 9, 16],
                  ] as const
                ).map(([label, rw, rh]) => (
                  <Button
                    key={label}
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const W = detailAsset.width ?? 0;
                      const H = detailAsset.height ?? 0;
                      if (!W || !H) return;
                      // Largest box with this ratio inside the image.
                      const byWidth = Math.min(W, Math.floor((H * rw) / rh));
                      const w = Math.max(1, byWidth);
                      const h = Math.max(1, Math.round((w * rh) / rw));
                      setCrop({
                        x: Math.round((W - w) / 2),
                        y: Math.round((H - h) / 2),
                        width: w,
                        height: h,
                      });
                    }}
                  >
                    {label}
                  </Button>
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
    </MediaDropzone>
  );
}

/** Placeholder while the deep-link parameter resolves. */
function MediaPageSkeleton() {
  return (
    <div className="flex items-center justify-center gap-2 py-24 text-sm text-muted-foreground">
      <RefreshCw className="h-5 w-5 animate-spin" />
      در حال بارگذاری کتابخانه‌ی رسانه...
    </div>
  );
}
