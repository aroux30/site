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
  /** Rank Math's "focus keyword" — the keyphrase the content targets. */
  focusKeyword: string | null;
  /** Advanced tab. null = no explicit operator choice (site defaults apply). */
  robotsNoindex: boolean | null;
  robotsNofollow: boolean | null;
  ogType: string | null;
  twitterTitle: string | null;
  twitterDescription: string | null;
  twitterImage: string | null;
  secondaryFocusKeywords: string | null;
  seoScore: number | null;
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
    focusKeyword: readString(r.focus_keyword),
    // Booleans keep null distinct from false: false is an explicit operator
    // choice ("indexable"), null is "no choice" — collapsing them would make
    // the Advanced tab unable to express "force index".
    robotsNoindex: typeof r.robots_noindex === "boolean" ? r.robots_noindex : null,
    robotsNofollow: typeof r.robots_nofollow === "boolean" ? r.robots_nofollow : null,
    ogType: readString(r.og_type),
    twitterTitle: readString(r.twitter_title),
    twitterDescription: readString(r.twitter_description),
    twitterImage: readString(r.twitter_image),
    secondaryFocusKeywords: readString(r.secondary_focus_keywords),
    seoScore: typeof r.seo_score === "number" ? r.seo_score : null,
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
  if (data.focusKeyword !== undefined) body.focus_keyword = data.focusKeyword;
  if (data.robotsNoindex !== undefined) body.robots_noindex = data.robotsNoindex;
  if (data.robotsNofollow !== undefined) body.robots_nofollow = data.robotsNofollow;
  if (data.ogType !== undefined) body.og_type = data.ogType;
  if (data.twitterTitle !== undefined) body.twitter_title = data.twitterTitle;
  if (data.twitterDescription !== undefined)
    body.twitter_description = data.twitterDescription;
  if (data.twitterImage !== undefined) body.twitter_image = data.twitterImage;
  if (data.secondaryFocusKeywords !== undefined)
    body.secondary_focus_keywords = data.secondaryFocusKeywords;
  if (data.seoScore !== undefined) body.seo_score = data.seoScore;
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

/* ── SEO dashboard + 404 monitor (the SEO menu's own panels) ─────────────── */

export interface SeoDashboard {
  redirects_total: number;
  redirects_active: number;
  not_found_distinct_paths: number;
  not_found_total_hits: number;
  not_found_paths_last_7_days: number;
  blog_posts_with_seo: number;
  blog_posts_missing_seo: number;
}

export interface NotFoundLog {
  id: string;
  path: string;
  referrer: string | null;
  user_agent: string | null;
  hit_count: number;
  first_seen_at: string;
  last_seen_at: string;
}

export interface NotFoundLogList {
  items: NotFoundLog[];
  total: number;
  page: number;
  page_size: number;
}

export async function fetchSeoDashboard(): Promise<SeoDashboard> {
  const { data } = await apiClient.get<SeoDashboard>("/admin/seo/dashboard");
  return data;
}

export async function fetchNotFoundLogs(params?: {
  page?: number;
  page_size?: number;
  search?: string;
}): Promise<NotFoundLogList> {
  const { data } = await apiClient.get<NotFoundLogList>("/admin/seo/404", {
    params,
  });
  return data;
}

/* ── Titles & Meta (default templates per content type) ──────────────────── */

export interface TitlesMetaTemplateEntry {
  content_type: string;
  label: string;
  title_template: string;
  description_template: string;
  title_customized: boolean;
  description_customized: boolean;
}

export interface TitlesMetaVariable {
  name: string;
  label: string;
  example: string;
}

export interface TitlesMeta {
  separator: string;
  templates: TitlesMetaTemplateEntry[];
  variables: TitlesMetaVariable[];
}

export async function fetchTitlesMeta(): Promise<TitlesMeta> {
  const { data } = await apiClient.get<TitlesMeta>("/admin/seo/titles-meta");
  return data;
}

export async function updateTitlesMeta(body: {
  separator?: string;
  templates?: Record<string, { title?: string; description?: string }>;
}): Promise<TitlesMeta> {
  const { data } = await apiClient.put<TitlesMeta>("/admin/seo/titles-meta", body);
  return data;
}

export async function previewTitlesMeta(body: {
  template: string;
  content_type?: string;
}): Promise<{ rendered: string; used_default: boolean }> {
  const { data } = await apiClient.post<{ rendered: string; used_default: boolean }>(
    "/admin/seo/titles-meta/preview",
    body,
  );
  return data;
}

/* ── Schema builder (Rich Snippets) ──────────────────────────────────────── */

export interface SchemaTypeField {
  key: string;
  label: string;
  kind: string;
  required: boolean;
  placeholder: string;
  options?: string[] | null;
}

export interface SchemaTypeEntry {
  type: string;
  label: string;
  description: string;
  fields: SchemaTypeField[];
}

export async function fetchSchemaTypes(): Promise<SchemaTypeEntry[]> {
  const { data } = await apiClient.get<{ types: SchemaTypeEntry[] }>(
    "/admin/seo/schema/types",
  );
  return data.types;
}

export async function buildSchema(body: {
  schema_type: string;
  fields: Record<string, string>;
  resource_type?: string;
  resource_id?: string;
}): Promise<{ node: Record<string, unknown>; problems: string[] }> {
  const { data } = await apiClient.post<{
    node: Record<string, unknown>;
    problems: string[];
  }>("/admin/seo/schema/build", body);
  return data;
}

export async function applySchema(body: {
  schema_type: string;
  fields: Record<string, string>;
  resource_type: string;
  resource_id: string;
}): Promise<{ node: Record<string, unknown>; problems: string[] }> {
  const { data } = await apiClient.post<{
    node: Record<string, unknown>;
    problems: string[];
  }>("/admin/seo/schema/apply", body);
  return data;
}

/* ── Link counter (internal/external counts + orphans) ───────────────────── */

export interface PostLinkCounts {
  post_id: string;
  slug: string;
  title: string;
  internal: number;
  external: number;
  anchor: number;
  total: number;
  external_urls: string[];
  is_orphan: boolean;
}

export interface LinkCounterResult {
  items: PostLinkCounts[];
  total: number;
  page: number;
  page_size: number;
  orphan_count: number;
  external_hosts: string[];
}

export async function fetchLinkCounter(params?: {
  page?: number;
  page_size?: number;
  orphans_only?: boolean;
}): Promise<LinkCounterResult> {
  const { data } = await apiClient.get<LinkCounterResult>("/admin/seo/link-counter", {
    params,
  });
  return data;
}

/* ── Instant Indexing (IndexNow + Google skeleton) ───────────────────────── */

export interface IndexingStatus {
  indexnow_enabled: boolean;
  indexnow_key: string | null;
  key_file_path: string | null;
  google: { connected: boolean; note: string };
}

export interface IndexingSubmitResult {
  submitted: number;
  status: string;
  reason?: string | null;
  http_status?: number | null;
}

export async function fetchIndexingStatus(): Promise<IndexingStatus> {
  const { data } = await apiClient.get<IndexingStatus>("/admin/seo/indexing");
  return data;
}

export async function toggleIndexNow(enabled: boolean): Promise<IndexingStatus> {
  const { data } = await apiClient.put<IndexingStatus>("/admin/seo/indexing", { enabled });
  return data;
}

export async function submitToIndexNow(urls: string[]): Promise<IndexingSubmitResult> {
  const { data } = await apiClient.post<IndexingSubmitResult>("/admin/seo/indexing/submit", {
    urls,
  });
  return data;
}

/* ── Status & Tools ──────────────────────────────────────────────────────── */

export interface SeoStatusCheck {
  key: string;
  label: string;
  status: "pass" | "warn" | "fail";
  detail: string;
  fix: string;
}

export interface SeoStatusResult {
  checks: SeoStatusCheck[];
  pass_count: number;
  warn_count: number;
  fail_count: number;
}

export interface IncompleteData {
  blog_posts_without_seo_metadata: number;
  blog_post_ids: string[];
  products_without_seo_title: number;
}

export async function fetchSeoStatus(): Promise<SeoStatusResult> {
  const { data } = await apiClient.get<SeoStatusResult>("/admin/seo/status");
  return data;
}

export async function fetchIncompleteData(): Promise<IncompleteData> {
  const { data } = await apiClient.get<IncompleteData>("/admin/seo/tools/incomplete-data");
  return data;
}

export async function exportSeoSettings(): Promise<Record<string, string>> {
  const { data } = await apiClient.get<{ settings: Record<string, string> }>(
    "/admin/seo/tools/settings-export",
  );
  return data.settings;
}

export async function importSeoSettings(
  settings: Record<string, string>,
): Promise<{ written: number; total: number; errors: Array<{ key: string; error: string }> }> {
  const { data } = await apiClient.post<{
    written: number;
    total: number;
    errors: Array<{ key: string; error: string }>;
  }>("/admin/seo/tools/settings-import", { settings });
  return data;
}

/* ── Local SEO (business profile) ────────────────────────────────────────── */

export interface LocalSeoField {
  key: string;
  label: string;
  placeholder: string;
}

export interface LocalSeoData {
  values: Record<string, string>;
  fields: LocalSeoField[];
  business_types: string[];
}

export async function fetchLocalSeo(): Promise<LocalSeoData> {
  const { data } = await apiClient.get<LocalSeoData>("/admin/seo/local-seo");
  return data;
}

export async function saveLocalSeo(values: Record<string, string>): Promise<LocalSeoData> {
  const { data } = await apiClient.put<LocalSeoData>("/admin/seo/local-seo", { values });
  return data;
}

export async function previewLocalSeo(): Promise<{
  node: Record<string, unknown> | null;
  configured: boolean;
}> {
  const { data } = await apiClient.get<{
    node: Record<string, unknown> | null;
    configured: boolean;
  }>("/admin/seo/local-seo/preview");
  return data;
}

/* ── Content AI (meta suggestions via configured LLM) ────────────────────── */

export interface ContentAiStatus {
  connected: boolean;
  model: string;
  note: string;
}

export interface ContentAiSuggestion {
  status: string;
  suggestion: string | null;
  reason: string | null;
}

export async function fetchContentAiStatus(): Promise<ContentAiStatus> {
  const { data } = await apiClient.get<ContentAiStatus>("/admin/seo/content-ai");
  return data;
}

export async function configureContentAi(body: {
  api_key?: string;
  base_url?: string;
  model?: string;
}): Promise<ContentAiStatus> {
  const { data } = await apiClient.put<ContentAiStatus>("/admin/seo/content-ai", body);
  return data;
}

export async function generateContentAiSuggestion(body: {
  title: string;
  content: string;
  kind: "title" | "description";
}): Promise<ContentAiSuggestion> {
  const { data } = await apiClient.post<ContentAiSuggestion>(
    "/admin/seo/content-ai/generate",
    body,
  );
  return data;
}

export async function deleteNotFoundLog(missId: string): Promise<void> {
  // `miss_id` is a query parameter on purpose: the generic
  // `DELETE /admin/seo/{resource_type}/{resource_id}` route would capture a
  // two-segment path and answer it as a metadata delete.
  await apiClient.delete("/admin/seo/404", { params: { miss_id: missId } });
}

export async function clearNotFoundLogs(): Promise<{ removed: number }> {
  const { data } = await apiClient.post<{ removed: number }>("/admin/seo/404/clear");
  return data;
}

/* ── Link Genius (internal-link suggestions + keyword maps) ──────────────── */

export interface LinkSuggestion {
  post_id: string;
  title: string;
  slug: string;
  url: string;
  score: number;
  excerpt: string;
}

export interface LinkSuggestionsResult {
  source_post_id: string;
  suggestions: LinkSuggestion[];
  total: number;
}

export interface IncomingLink {
  post_id: string;
  title: string;
  slug: string;
  url: string;
  anchor_text: string;
}

export interface IncomingLinksResult {
  post_id: string;
  incoming: IncomingLink[];
  total: number;
}

export interface LinkMapVariation {
  id: string;
  keyword: string;
  kind: "manual" | "ai";
}

export interface LinkMap {
  id: string;
  name: string;
  target_url: string;
  target_post_id: string | null;
  max_links_per_post: number;
  auto_link_on_publish: boolean;
  case_sensitive: boolean;
  is_active: boolean;
  variations: LinkMapVariation[];
}

export async function fetchLinkSuggestions(
  postId: string,
  limit = 20,
): Promise<LinkSuggestionsResult> {
  const { data } = await apiClient.get<LinkSuggestionsResult>(
    `/admin/seo/posts/${encodeURIComponent(postId)}/link-suggestions`,
    { params: { limit } },
  );
  return data;
}

export async function fetchIncomingLinks(postId: string): Promise<IncomingLinksResult> {
  const { data } = await apiClient.get<IncomingLinksResult>(
    `/admin/seo/posts/${encodeURIComponent(postId)}/incoming-links`,
  );
  return data;
}

export async function reindexPostLinks(postId: string): Promise<{ indexed: number }> {
  const { data } = await apiClient.post<{ indexed: number }>(
    `/admin/seo/posts/${encodeURIComponent(postId)}/reindex-links`,
  );
  return data;
}

export async function fetchLinkMaps(): Promise<{ items: LinkMap[]; total: number }> {
  const { data } = await apiClient.get<{ items: LinkMap[]; total: number }>(
    "/admin/seo/link-maps",
  );
  return data;
}

export async function createLinkMap(body: {
  name: string;
  target_url: string;
  max_links_per_post?: number;
  auto_link_on_publish?: boolean;
  case_sensitive?: boolean;
  is_active?: boolean;
  variations?: Array<{ keyword: string; kind?: "manual" | "ai" }>;
}): Promise<LinkMap> {
  const { data } = await apiClient.post<LinkMap>("/admin/seo/link-maps", body);
  return data;
}

export async function updateLinkMap(
  mapId: string,
  body: Partial<{
    name: string;
    target_url: string;
    max_links_per_post: number;
    auto_link_on_publish: boolean;
    case_sensitive: boolean;
    is_active: boolean;
    variations: Array<{ keyword: string; kind: "manual" | "ai" }>;
  }>,
): Promise<LinkMap> {
  const { data } = await apiClient.patch<LinkMap>(
    `/admin/seo/link-maps/${encodeURIComponent(mapId)}`,
    body,
  );
  return data;
}

export async function deleteLinkMap(mapId: string): Promise<void> {
  await apiClient.delete(`/admin/seo/link-maps/${encodeURIComponent(mapId)}`);
}

export async function previewLinkMap(body: {
  post_id: string;
  target_url: string;
  keywords: string[];
  max_links_per_post?: number;
  case_sensitive?: boolean;
}): Promise<{ inserted: number; matches: string[] }> {
  const { data } = await apiClient.post<{ inserted: number; matches: string[] }>(
    "/admin/seo/link-maps/preview",
    body,
  );
  return data;
}

export async function applyLinkMap(body: {
  map_id: string;
  post_id?: string;
  all_posts?: boolean;
}): Promise<{ posts_updated: number; links_inserted: number }> {
  const { data } = await apiClient.post<{ posts_updated: number; links_inserted: number }>(
    "/admin/seo/link-maps/apply",
    body,
  );
  return data;
}

/* ── Broken-link crawler (Link Genius audit) ─────────────────────────────── */

export type LinkAuditCategory =
  | "ok"
  | "broken"
  | "redirect"
  | "timeout"
  | "error"
  | "blocked";

export interface LinkAuditItem {
  id: string;
  url: string;
  http_status: number | null;
  category: LinkAuditCategory;
  detail: string | null;
  is_marked_safe: boolean;
  last_checked_at: string;
}

export interface LinkAuditList {
  items: LinkAuditItem[];
  total: number;
  page: number;
  page_size: number;
  counts: Record<string, number>;
}

export interface LinkAuditRun {
  checked: number;
  broken: number;
  redirect: number;
  total: number;
  timeout: number;
  error: number;
  blocked: number;
}

export async function fetchLinkAudit(params?: {
  category?: LinkAuditCategory;
  page?: number;
  page_size?: number;
  hide_safe?: boolean;
}): Promise<LinkAuditList> {
  const { data } = await apiClient.get<LinkAuditList>("/admin/seo/link-audit", {
    params,
  });
  return data;
}

export async function runLinkAudit(params?: {
  force?: boolean;
  batch_size?: number;
}): Promise<LinkAuditRun> {
  const { data } = await apiClient.post<LinkAuditRun>("/admin/seo/link-audit/run", null, {
    params,
  });
  return data;
}

export async function markLinkSafe(auditId: string, safe: boolean): Promise<void> {
  await apiClient.patch(`/admin/seo/link-audit/${encodeURIComponent(auditId)}/safe`, {
    safe,
  });
}

export async function clearLinkAudit(): Promise<void> {
  await apiClient.delete("/admin/seo/link-audit");
}
