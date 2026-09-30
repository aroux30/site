import apiClient from "./client";

export interface ApiReward {
  id: string;
  name: string;
  description?: string | null;
  type: "discount" | "gift" | "badge" | "physical" | "voucher" | string;
  points_required: number;
  is_active: boolean;
  quantity_available?: number | null;
  created_at?: string;
  updated_at?: string;
  icon?: string;
  code_template?: string;
}

export interface ApiUserPointsSummary {
  total_points_earned: number;
  points_spent: number;
  points_available: number;
  rank: "bronze" | "silver" | "gold" | "platinum" | string;
  available_rewards: ApiReward[];
  total_earned?: number;
  available_points?: number;
}

export interface ApiClaimRewardRequest {
  notes?: string;
}

export interface ApiClaimRewardResponse {
  reward_id: string;
  reward_name: string;
  points_spent: number;
  remaining_points: number;
  claimed_at: string;
  message: string;
  coupon_code?: string;
}

export interface ApiGamificationEvent {
  id: string;
  user_id: string;
  rule_id?: string;
  points_earned: number;
  event_data?: Record<string, unknown> | null;
  created_at: string;
  rule_name?: string | null;
}

export interface ApiGamificationEventListResponse {
  items: ApiGamificationEvent[];
  total: number;
}

export interface ApiClaimRecord {
  id: string;
  reward_id: string;
  reward_name: string;
  reward_type: string;
  points_spent: number;
  claimed_at: string;
  code: string;
  status: "active" | "used" | "expired";
}

/**
 * Fetch current user's gamification points summary and available rewards.
 */
export async function fetchGamificationSummary(): Promise<ApiUserPointsSummary> {
  try {
    const { data } = await apiClient.get<ApiUserPointsSummary>("/gamification/summary");
    if (data) {
      if (data.total_earned === undefined && data.total_points_earned !== undefined) {
        data.total_earned = data.total_points_earned;
      }
      if (data.available_points === undefined && data.points_available !== undefined) {
        data.available_points = data.points_available;
      }
    }
    return data;
  } catch (error) {
    // Backend unavailable/401 → honest zero balance (never invent points) and
    // an empty catalog — the rewards page shows its real empty state instead
    // of a fabricated prize list the user could try to claim (BUG-FE-08).
    return {
      total_points_earned: 0,
      points_spent: 0,
      points_available: 0,
      total_earned: 0,
      available_points: 0,
      rank: "bronze",
      available_rewards: [],
    };
  }
}

/**
 * Fetch claimable rewards catalog from GET /api/v1/gamification/rewards
 */
export async function fetchGamificationRewards(): Promise<ApiReward[]> {
  try {
    const { data } = await apiClient.get<ApiReward[]>("/gamification/rewards");
    if (Array.isArray(data)) {
      return data;
    }
    return [];
  } catch (error) {
    // No fabricated catalog on failure (BUG-FE-08).
    return [];
  }
}

/**
 * Claim reward using loyalty points via POST /api/v1/gamification/rewards/{reward_id}/claim
 */
export async function claimGamificationReward(
  rewardId: string,
  payload?: ApiClaimRewardRequest,
): Promise<ApiClaimRewardResponse> {
  try {
    const { data } = await apiClient.post<ApiClaimRewardResponse>(
      `/gamification/rewards/${rewardId}/claim`,
      payload || {},
    );
    return data;
  } catch (error) {
    // Never fabricate a success here: the caller deducts points and shows a
    // coupon code to the user. A backend failure must surface as a real error.
    throw error;
  }
}

/**
 * Fetch point-earning history from GET /api/v1/gamification/history
 */
export async function fetchGamificationHistory(
  skip: number = 0,
  limit: number = 20,
): Promise<ApiGamificationEventListResponse> {
  try {
    const { data } = await apiClient.get<ApiGamificationEventListResponse>(
      "/gamification/history",
      {
        params: { skip, limit },
      },
    );
    return data;
  } catch (error) {
    return {
      items: [],
      total: 0,
    };
  }
}

