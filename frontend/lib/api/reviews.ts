/**
 * Product review moderation (admin).
 *
 * Contract: backend/app/modules/reviews/api/routes.py + schemas/review.py
 *   GET  /reviews/admin/reviews/pending            — reviews:moderate
 *   POST /reviews/admin/reviews/{review_id}/moderate — reviews:moderate
 *
 * The moderation endpoint takes `{status: "approved"|"rejected", reason}` —
 * a target status, not an `action` verb. The previous client sent
 * `{action: "approve"}`, which the backend's `^(approved|rejected)$` pattern
 * rejects with a 422 on every call.
 *
 * The pending list is a read-only moderation queue: it never mutates a review
 * on load and holds no money.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const PENDING_REVIEWS_PATH = "/reviews/admin/reviews/pending";

export const REVIEW_STATUSES = ["pending", "approved", "rejected"] as const;
export type ReviewModerationDecision = "approved" | "rejected";

export const REVIEW_STATUS_LABELS: Record<string, string> = {
  pending: "در انتظار بررسی",
  approved: "تأییدشده",
  rejected: "ردشده",
};

export function reviewStatusLabel(status: string): string {
  return REVIEW_STATUS_LABELS[status] ?? status;
}

export interface ReviewUser {
  id: string;
  displayName: string | null;
}

export interface AdminReview {
  id: string;
  user: ReviewUser;
  productId: string;
  rating: number | null;
  title: string | null;
  body: string | null;
  pros: string[] | null;
  cons: string[] | null;
  isVerifiedPurchase: boolean;
  status: string;
  helpfulCount: number | null;
  unhelpfulCount: number | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface RatingDistribution {
  star1: number | null;
  star2: number | null;
  star3: number | null;
  star4: number | null;
  star5: number | null;
}

export interface PendingReviewPage {
  reviews: AdminReview[];
  total: number | null;
  page: number;
  size: number;
  totalPages: number | null;
  averageRating: number | null;
  distribution: RatingDistribution;
  /** Records returned that could not be read as reviews. Never silent. */
  invalidCount: number;
  /**
   * Reviews the backend holds but this read did not return. Null when the
   * total was not reported.
   */
  missingCount: number | null;
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

function readStringList(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const out = value.filter((v): v is string => typeof v === "string" && v.trim().length > 0);
  return out.length ? out : null;
}

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizeReview(raw: unknown): AdminReview | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const productId = readString(r.product_id);
  if (!id || !productId) return null;

  const userRecord = readRecord(r.user);
  return {
    id,
    user: {
      id: userRecord ? (readString(userRecord.id) ?? "") : readString(r.user_id) ?? "",
      displayName: userRecord ? readString(userRecord.display_name) : null,
    },
    productId,
    rating: readInt(r.rating),
    title: readString(r.title),
    body: readString(r.body),
    pros: readStringList(r.pros),
    cons: readStringList(r.cons),
    isVerifiedPurchase: r.is_verified_purchase === true,
    status: readString(r.status) ?? "pending",
    helpfulCount: readInt(r.helpful_count),
    unhelpfulCount: readInt(r.unhelpful_count),
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

function parseDistribution(raw: unknown): RatingDistribution {
  const r = readRecord(raw) ?? {};
  return {
    star1: readInt(r.star_1),
    star2: readInt(r.star_2),
    star3: readInt(r.star_3),
    star4: readInt(r.star_4),
    star5: readInt(r.star_5),
  };
}

export function parsePendingPage(payload: unknown): PendingReviewPage {
  const r = readRecord(payload) ?? {};
  const records = Array.isArray(r.reviews) ? r.reviews : [];
  const reviews: AdminReview[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const review = normalizeReview(raw);
    if (review) reviews.push(review);
    else invalidCount += 1;
  }
  const stats = readRecord(r.stats);
  const total = readInt(r.total);
  return {
    reviews,
    total,
    page: readInt(r.page) ?? 1,
    size: readInt(r.size) ?? reviews.length,
    totalPages: readInt(r.total_pages),
    averageRating: stats ? readNumber(stats.average_rating) : null,
    distribution: parseDistribution(stats ? stats.distribution : null),
    invalidCount,
    missingCount: total === null ? null : Math.max(0, total - records.length),
  };
}

export async function fetchPendingReviews(
  params: { page?: number; size?: number } = {},
  client: AxiosInstance = apiClient,
): Promise<PendingReviewPage> {
  const res = await client.get<unknown>(PENDING_REVIEWS_PATH, {
    params: { page: params.page ?? 1, size: params.size ?? 20 },
  });
  return parsePendingPage(res.data);
}

export async function moderateReview(
  reviewId: string,
  status: ReviewModerationDecision,
  reason: string | null,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(`/reviews/admin/reviews/${reviewId}/moderate`, {
    status,
    reason: reason && reason.trim() ? reason.trim() : null,
  });
}
