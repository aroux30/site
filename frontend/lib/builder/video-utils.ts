export function normalizeVideoEmbedUrl(rawUrl: string, videoType?: string): string {
  const trimmed = rawUrl.trim();
  if (!trimmed) return "";
  if (!trimmed.startsWith("https://") && !trimmed.startsWith("http://") && !trimmed.startsWith("/")) {
    return "";
  }

  const lower = trimmed.toLowerCase();
  const isYoutube =
    videoType === "youtube" ||
    lower.includes("youtube.com") ||
    lower.includes("youtu.be");

  if (isYoutube) {
    try {
      const parsed = new URL(trimmed);
      const host = parsed.hostname.toLowerCase();
      let videoId = "";
      if (host.includes("youtu.be")) {
        videoId = parsed.pathname.split("/").filter(Boolean)[0] || "";
      } else if (parsed.pathname.startsWith("/embed/")) {
        videoId = parsed.pathname.split("/")[2] || "";
      } else if (parsed.pathname.startsWith("/shorts/")) {
        videoId = parsed.pathname.split("/")[2] || "";
      } else if (parsed.pathname.startsWith("/live/")) {
        videoId = parsed.pathname.split("/")[2] || "";
      } else {
        videoId = parsed.searchParams.get("v") || "";
      }
      if (videoId) {
        return `https://www.youtube.com/embed/${videoId}`;
      }
    } catch {
      // Fallback regex if URL parsing throws on partial input
      const ytMatch = trimmed.match(/(?:youtu\.be\/|youtube\.com\/(?:watch\?.*v=|embed\/|shorts\/|live\/))([A-Za-z0-9_-]{6,})/);
      if (ytMatch?.[1]) {
        return `https://www.youtube.com/embed/${ytMatch[1]}`;
      }
    }
    return trimmed;
  }

  const isAparat = videoType === "aparat" || lower.includes("aparat.com");
  if (isAparat) {
    if (lower.includes("/video/video/embed/videohash/")) {
      return trimmed;
    }
    const apMatch = trimmed.match(/aparat\.com\/v\/([A-Za-z0-9_-]+)/i);
    if (apMatch?.[1]) {
      return `https://www.aparat.com/video/video/embed/videohash/${apMatch[1]}/vt/frame`;
    }
    return trimmed;
  }

  return trimmed;
}
