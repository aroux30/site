/**
 * Gamification administration — point rules and claimable rewards.
 *
 * Contract: backend/app/modules/gamification/api/routes.py +
 *           schemas/gamification.py
 *   GET   /gamification/admin/rules            — gamification:read
 *   POST  /gamification/admin/rules            — gamification:write
 *   PATCH /gamification/admin/rules/{rule_id}  — gamification:write
 *   POST  /gamification/admin/rewards          — gamification:write
 *   PATCH /gamification/admin/rewards/{id}     — gamification:write
 *
 * There is no admin LIST for rewards — only create and update. The panel reads
 * the customer-facing `GET /gamification/rewards`, which the backend serves
 * with `active_only=True`: **deactivated rewards do not appear in it at all**.
 * A panel that showed this list unlabelled would read as "these are all the
 * rewards", so `fetchRewards` reports that limitation and the page states it
 * on screen. This is a real gap in the backend surface, not a client shortcut.
 *
 * Rules award POINTS (integers, never money). Rewards cost POINTS and may have
 * a quantity; neither moves currency, which is why no amount here is treated as
 * a rial figure.
 */

import type { AxiosInstance } from "axios";
import apiClient from "./client";

export const RULES_PATH = "/gamification/admin/rules";
export const REWARDS_PATH = "/gamification/admin/rewards";
export const REWARDS_READ_PATH = "/gamification/rewards";

export interface GamificationRule {
  id: string;
  name: string;
  eventType: string;
  points: number | null;
  conditions: Record<string, unknown> | null;
  isActive: boolean;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface GamificationReward {
  id: string;
  name: string;
  description: string | null;
  type: string;
  pointsRequired: number | null;
  isActive: boolean;
  quantityAvailable: number | null;
  createdAt: string | null;
  updatedAt: string | null;
}

export interface RuleCreatePayload {
  name: string;
  eventType: string;
  points: number;
  conditions?: Record<string, unknown> | null;
  isActive: boolean;
}

export interface RuleUpdatePayload {
  name?: string;
  eventType?: string;
  points?: number;
  conditions?: Record<string, unknown> | null;
  isActive?: boolean;
}

export interface RewardCreatePayload {
  name: string;
  description?: string | null;
  type: string;
  pointsRequired: number;
  isActive: boolean;
  quantityAvailable?: number | null;
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

function readRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizeRule(raw: unknown): GamificationRule | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const name = readString(r.name);
  if (!id || !name) return null;
  return {
    id,
    name,
    eventType: readString(r.event_type) ?? "",
    points: readInt(r.points),
    conditions: readRecord(r.conditions),
    isActive: r.is_active === true,
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

export function normalizeReward(raw: unknown): GamificationReward | null {
  const r = readRecord(raw);
  if (!r) return null;
  const id = readString(r.id);
  const name = readString(r.name);
  if (!id || !name) return null;
  return {
    id,
    name,
    description: readString(r.description),
    type: readString(r.type) ?? "unknown",
    pointsRequired: readInt(r.points_required),
    isActive: r.is_active === true,
    quantityAvailable: readInt(r.quantity_available),
    createdAt: readString(r.created_at),
    updatedAt: readString(r.updated_at),
  };
}

export interface RuleList {
  items: GamificationRule[];
  invalidCount: number;
}

export async function fetchRules(
  client: AxiosInstance = apiClient,
): Promise<RuleList> {
  const res = await client.get<unknown>(RULES_PATH, { params: { limit: 200 } });
  const records = Array.isArray(res.data) ? res.data : [];
  const items: GamificationRule[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const rule = normalizeRule(raw);
    if (rule) items.push(rule);
    else invalidCount += 1;
  }
  return { items, invalidCount };
}

export interface RewardList {
  items: GamificationReward[];
  invalidCount: number;
  /**
   * Rewards the backend holds but this read did not return, when it reports a
   * total. Null when it did not.
   */
  missingCount: number | null;
  /**
   * Always false when read from the admin endpoint: every reward comes back,
   * active or not, so the table is the full set. Kept on the result type
   * because the flag documents which endpoint produced the list.
   */
  activeOnly: boolean;
}

export async function fetchRewards(
  client: AxiosInstance = apiClient,
): Promise<RewardList> {
  // Reads the ADMIN endpoint, not the customer-facing one. The customer list is
  // served `active_only=True`, so a reward an operator deactivated vanished
  // from the only list the panel could see and could not be reactivated. The
  // admin route takes `is_active` as a filter, and returns every reward when it
  // is omitted — which is what this view needs.
  const res = await client.get<unknown>(REWARDS_PATH);
  const envelope = readRecord(res.data);
  const records = Array.isArray(res.data)
    ? res.data
    : envelope && Array.isArray(envelope.items)
      ? envelope.items
      : [];
  const items: GamificationReward[] = [];
  let invalidCount = 0;
  for (const raw of records) {
    const reward = normalizeReward(raw);
    if (reward) items.push(reward);
    else invalidCount += 1;
  }
  const total = envelope ? readInt(envelope.total) : null;
  return {
    items,
    invalidCount,
    missingCount: total === null ? null : Math.max(0, total - records.length),
    activeOnly: false,
  };
}

export async function createRule(
  payload: RuleCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(RULES_PATH, {
    name: payload.name,
    event_type: payload.eventType,
    points: Math.trunc(payload.points),
    conditions: payload.conditions ?? null,
    is_active: payload.isActive,
  });
}

export async function updateRule(
  id: string,
  payload: RuleUpdatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.eventType !== undefined) body.event_type = payload.eventType;
  if (payload.points !== undefined) body.points = Math.trunc(payload.points);
  if (payload.conditions !== undefined) body.conditions = payload.conditions;
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  await client.patch(`${RULES_PATH}/${id}`, body);
}

export async function createReward(
  payload: RewardCreatePayload,
  client: AxiosInstance = apiClient,
): Promise<void> {
  await client.post(REWARDS_PATH, {
    name: payload.name,
    description: payload.description ?? null,
    type: payload.type,
    points_required: Math.trunc(payload.pointsRequired),
    is_active: payload.isActive,
    quantity_available: payload.quantityAvailable ?? null,
  });
}

export async function updateReward(
  id: string,
  payload: Partial<RewardCreatePayload>,
  client: AxiosInstance = apiClient,
): Promise<void> {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) body.name = payload.name;
  if (payload.description !== undefined) body.description = payload.description;
  if (payload.type !== undefined) body.type = payload.type;
  if (payload.pointsRequired !== undefined) {
    body.points_required = Math.trunc(payload.pointsRequired);
  }
  if (payload.isActive !== undefined) body.is_active = payload.isActive;
  if (payload.quantityAvailable !== undefined) {
    body.quantity_available = payload.quantityAvailable;
  }
  await client.patch(`${REWARDS_PATH}/${id}`, body);
}

export const REWARD_TYPES = ["discount", "gift", "badge", "physical"] as const;

export const REWARD_TYPE_LABELS: Record<string, string> = {
  discount: "کد تخفیف",
  gift: "هدیه",
  badge: "نشان",
  physical: "کالای فیزیکی",
};

export function rewardTypeLabel(type: string): string {
  return REWARD_TYPE_LABELS[type] ?? type;
}
