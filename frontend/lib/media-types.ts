/**
 * The MIME types the media store accepts.
 *
 * This mirrors `ALLOWED_MIME_TYPES` in
 * `backend/app/modules/media/application/media_service.py`. It is the single
 * frontend copy: the two `accept` attributes that used to be hardcoded
 * (`image/jpeg,image/png,image/webp` and the same list plus PDF) each named
 * fewer types than the backend allowed, so the file picker refused a video the
 * upload endpoint would have taken.
 *
 * Keys are what the file input needs, values are what the list filter needs.
 * `""` is the "all types" option on the filter and must not be used as a type.
 */
export const MEDIA_MIME_TYPES = {
  "image/jpeg": "تصویر JPEG",
  "image/png": "تصویر PNG",
  "image/webp": "تصویر WebP",
  "image/gif": "تصویر GIF",
  "image/avif": "تصویر AVIF",
  "application/pdf": "سند PDF",
  "audio/mpeg": "صوتی MP3",
  "audio/mp4": "صوتی M4A",
  "audio/ogg": "صوتی OGG",
  "audio/wav": "صوتی WAV",
  "audio/webm": "صوتی WebM",
  "video/mp4": "ویدیو MP4",
  "video/webm": "ویدیو WebM",
  "video/quicktime": "ویدیو MOV",
  "video/x-msvideo": "ویدیو AVI",
} as const;

export type MediaMimeType = keyof typeof MEDIA_MIME_TYPES;

/**
 * Coarse groups, matching the backend's own category constants.
 *
 * The values are MIME *prefixes* the list route matches with `startswith`,
 * except `""`, which means "no filter" and must not be sent as a type.
 */
export const MEDIA_MIME_PREFIXES = [
  { value: "", label: "همه انواع" },
  { value: "image/", label: "تصاویر" },
  { value: "application/pdf", label: "سند" },
  { value: "audio/", label: "فایل صوتی" },
  { value: "video/", label: "ویدیو" },
] as const;

/**
 * Every accepted type, for an `<input accept>` attribute.
 *
 * Typed from the table above so a type added to `MEDIA_MIME_TYPES` cannot be
 * forgotten here — which is how the two hardcoded lists drifted apart.
 */
export const MEDIA_ACCEPT_ATTRIBUTE: string = (
  Object.keys(MEDIA_MIME_TYPES) as MediaMimeType[]
).join(",");

/** How many files one batch upload may carry; matches the backend's cap. */
export const MEDIA_MAX_BATCH_FILES = 20;
