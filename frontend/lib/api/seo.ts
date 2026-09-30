/**
 * SEO metadata and the automated scoring engine (admin).
 *
 * Contract: backend/app/modules/seo/api/routes.py + schemas/seo.py
 *   POST /seo/analyze                      — pure computation, no auth needed
 *   GET  /seo/{resource_type}/{resource_id} — read metadata
 *   PUT  /seo/{resource_type}/{resource_id} — upsert metadata
 *   DELETE /seo/{resource_type}/{resource_id}
 *   GET  /admin/seo/redirects              — redirect rules (see cms-admin.ts)
 *
 * `analyze` is a pure function of the payload: it reads no database and writes
 * nothing. That is worth stating on the page, because a tool that LOOKS like it
 * saves a score might lead an editor to believe the score is persisted. It is
 * not — the result describes the draft that was submitted, nothing else.
 *
 * The previous version of this module declared `/seo/...` paths on an
 * authenticated admin client and parsed responses as `any`, so nothing about
 * the engine's contract was checked at the boundary. This one types the
 * response and validates the score rather than trusting it.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const SEO_ANALYZE_PATH = "/seo/analyze";

export interface SeoMeta {
  title: string | null;
  description: string | null;
  canonicalUrl: string | null;
  ogTitle: string | null;
  ogDescription: string | null;
  ogImage: string | null;
  schemaMarkup: Record<string, unknown> | null;
}

export interface SeoAnalysisRequest {
  title: string;
  content: string;
  focusKeyword: string;
  slug: string;
  metaDescription: string;
  imagesCount?: number | null;
  hasImageAlt?: boolean | null;
  internalLinksCount?: number | null;
}

export interface SeoCheckItem {
  passed: boolean;
  title: string;
  message: string;
  points: number | null;
  maxPoints: number | null;
  category: string | null;
}

export type SeoGradeColor = "green" | "yellow" | "red";

export interface SeoAnalysis {
  /** 0–100, clamped. Null when the backend did not report a usable number. */
  score: number | null;
  grade: string;
  gradeColor: SeoGradeColor;
  wordCount: number | null;
  keywordDensity: number | null;
  checklist: SeoCheckItem[];
  recommendations: string[];
}

function readString(value: unknown): string | null {
  if (typeof value !== "string") return null;
  const trimmed = value.trim();
  return trimmed ? trimmed : null;
}

function readInt(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return Math.trunc(value);
  if (typeof value === "string" && /^-?\d+$/.test(value.trim())) {
    return Number.parseInt(value.trim(), 10);
  }
  return null;
}

function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) {
    return Number(value);
  }
  return null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function readGradeColor(value: unknown): SeoGradeColor {
  // An unrecognised colour falls back to the neutral band rather than being
  // guessed green: a score chip must never claim "good" on an unknown verdict.
  return value === "green" || value === "yellow" || value === "red"
    ? value
    : "yellow";
}

function normalizeCheck(raw: unknown): SeoCheckItem | null {
  const r = readRecord(raw);
  if (!r) return null;
  const title = readString(r.title);
  if (!title) return null;
  return {
    passed: r.passed === true,
    title,
    message: readString(r.message) ?? "",
    points: readInt(r.points),
    maxPoints: readInt(r.max_points),
    category: readString(r.category),
  };
}

export function parseAnalysis(payload: unknown): SeoAnalysis {
  const r = readRecord(payload) ?? {};
  const rawScore = readInt(r.score);
  const checklistRaw = Array.isArray(r.checklist) ? r.checklist : [];
  const checklist: SeoCheckItem[] = [];
  for (const raw of checklistRaw) {
    const item = normalizeCheck(raw);
    if (item) checklist.push(item);
  }
  const recommendations = Array.isArray(r.recommendations)
    ? r.recommendations.filter(
        (v): v is string => typeof v === "string" && v.trim().length > 0,
      )
    : [];

  return {
    // Clamp: the contract says 0–100, but a score outside it would render a
    // nonsense bar, so it is bounded here rather than trusted.
    score: rawScore === null ? null : Math.min(100, Math.max(0, rawScore)),
    grade: readString(r.grade) ?? "—",
    gradeColor: readGradeColor(r.grade_color),
    wordCount: readInt(r.word_count),
    keywordDensity: readNumber(r.keyword_density),
    checklist,
    recommendations,
  };
}

export async function analyzeSeo(
  payload: SeoAnalysisRequest,
  client: AxiosInstance = apiClient,
): Promise<SeoAnalysis> {
  const res = await client.post<unknown>(SEO_ANALYZE_PATH, {
    title: payload.title,
    content: payload.content,
    focus_keyword: payload.focusKeyword,
    slug: payload.slug,
    meta_description: payload.metaDescription,
    images_count: payload.imagesCount ?? null,
    has_image_alt: payload.hasImageAlt ?? null,
    internal_links_count: payload.internalLinksCount ?? null,
  });
  return parseAnalysis(res.data);
}

export function parseSeoMeta(payload: unknown): SeoMeta | null {
  const r = readRecord(payload);
  if (!r) return null;
  return {
    title: readString(r.title),
    description: readString(r.description),
    canonicalUrl: readString(r.canonical_url),
    ogTitle: readString(r.og_title),
    ogDescription: readString(r.og_description),
    ogImage: readString(r.og_image),
    schemaMarkup: readRecord(r.schema_markup),
  };
}

export async function fetchSeoMeta(
  resourceType: string,
  resourceId: string,
  client: AxiosInstance = apiClient,
): Promise<SeoMeta | null> {
  const res = await client.get<unknown>(
    `/seo/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`,
  );
  return parseSeoMeta(res.data);
}

export async function upsertSeoMeta(
  resourceType: string,
  resourceId: string,
  data: Partial<SeoMeta>,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (data.title !== undefined) body.title = data.title;
  if (data.description !== undefined) body.description = data.description;
  if (data.canonicalUrl !== undefined) body.canonical_url = data.canonicalUrl;
  if (data.ogTitle !== undefined) body.og_title = data.ogTitle;
  if (data.ogDescription !== undefined) body.og_description = data.ogDescription;
  if (data.ogImage !== undefined) body.og_image = data.ogImage;
  if (data.schemaMarkup !== undefined) body.schema_markup = data.schemaMarkup;
  await client.put(
    `/seo/${encodeURIComponent(resourceType)}/${encodeURIComponent(resourceId)}`,
    body,
  );
}

/** Score band label. Kept here so the page and any future view agree. */
export const SEO_SCORE_BANDS = [
  { min: 80, label: "عالی", color: "green" as const },
  { min: 50, label: "نیازمند بهبود", color: "yellow" as const },
  { min: 0, label: "ضعیف", color: "red" as const },
];

export function scoreBand(score: number): { label: string; color: SeoGradeColor } {
  for (const band of SEO_SCORE_BANDS) {
    if (score >= band.min) return { label: band.label, color: band.color };
  }
  return { label: "ضعیف", color: "red" };
}
