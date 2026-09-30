import { Quote, Link2, ImageIcon, Music, Video, Grid3x3, MessageSquare } from "lucide-react";

import { BlogGallery } from "@/components/blog/blog-gallery";

/** Per-format presentation: icon, Persian label, and accent colour.
 *
 * The backend has always stored `post_format` and rendered it as a badge, so
 * a "quote" post looked identical to a "standard" one. WordPress uses the
 * format to choose a template; here it chooses a presentation.
 */
const FORMATS = {
  quote: { icon: Quote, label: "نقل قول", ring: "border-amber-500/40 bg-amber-500/5" },
  link: { icon: Link2, label: "پیوند", ring: "border-sky-500/40 bg-sky-500/5" },
  status: { icon: MessageSquare, label: "وضعیت", ring: "border-emerald-500/40 bg-emerald-500/5" },
  image: { icon: ImageIcon, label: "تصویر", ring: "border-violet-500/40 bg-violet-500/5" },
  gallery: { icon: Grid3x3, label: "گالری", ring: "border-teal-500/40 bg-teal-500/5" },
  audio: { icon: Music, label: " صوت", ring: "border-rose-500/40 bg-rose-500/5" },
  video: { icon: Video, label: "ویدیو", ring: "border-indigo-500/40 bg-indigo-500/5" },
} as const;

export type PostFormatKey = keyof typeof FORMATS;

export function isSpecialFormat(value: string | null | undefined): value is PostFormatKey {
  return !!value && value !== "standard" && value in FORMATS;
}

interface Props {
  format: PostFormatKey;
  content: string;
  /** Ordered media asset ids; used by the gallery format. */
  galleryImageIds?: string[];
  excerpt?: string | null;
}

/** First http(s) URL in plain-text content, for the `link` format. */
function firstUrl(text: string): string | null {
  return text.match(/https?:\/\/[^\s<>"')]+/)?.[0] ?? null;
}

/** First image URL in the body, for the `image` format. */
function firstImage(text: string): string | null {
  return text.match(/<img[^>]+src=["']([^"']+)["']/i)?.[1] ?? null;
}

/** First media element in the body, for the `audio` / `video` formats. */
function firstMedia(text: string, tag: "audio" | "video"): string | null {
  return text.match(new RegExp(`<${tag}[^>]+src=["']([^"']+)["']`, "i"))?.[1] ?? null;
}

/**
 * Renders the body according to the post format.
 *
 * Every format falls back to the plain article body when its special element
 * is missing, so picking a format can never hide content an editor wrote.
 */
export default function PostFormatBody({
  format,
  content,
  galleryImageIds = [],
  excerpt,
}: Props) {
  const config = FORMATS[format];
  const Icon = config.icon;

  const shell = (children: React.ReactNode) => (
    <div className={`mb-10 rounded-2xl border p-6 ${config.ring}`}>
      <div className="mb-4 flex items-center gap-2 text-xs font-medium text-muted-foreground">
        <Icon className="h-4 w-4" />
        {config.label}
      </div>
      {children}
    </div>
  );

  if (format === "quote") {
    return shell(
      <blockquote className="border-r-4 border-amber-500 ps-4 text-lg leading-relaxed italic">
        {excerpt || content || null}
      </blockquote>,
    );
  }

  if (format === "link") {
    const url = firstUrl(content) ?? firstUrl(excerpt ?? "");
    if (url) {
      return shell(
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="break-all text-primary underline underline-offset-4"
        >
          {url}
        </a>,
      );
    }
  }

  if (format === "image") {
    const src = firstImage(content);
    if (src) {
      return shell(
        // eslint-disable-next-line @next/next/no-img-element
        <img src={src} alt={excerpt ?? ""} className="w-full rounded-xl" />,
      );
    }
  }

  if (format === "gallery" && galleryImageIds.length > 0) {
    return shell(
      <BlogGallery imageUrls={galleryImageIds} title={excerpt ?? ""} />,
    );
  }

  if (format === "audio" || format === "video") {
    const src = firstMedia(content, format);
    if (src) {
      return shell(
        // eslint-disable-next-line jsx-a11y/media-has-caption
        format === "audio" ? (
          <audio src={src} controls className="w-full" />
        ) : (
          <video src={src} controls className="w-full rounded-lg" />
        ),
      );
    }
  }

  if (format === "status") {
    return shell(
      <p className="whitespace-pre-line text-base leading-relaxed">{content}</p>,
    );
  }

  return null;
}
