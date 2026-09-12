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

export const FALLBACK_REWARDS: ApiReward[] = [
  {
    id: "rew-discount-10",
    name: "کد تخفیف ۱۰٪ (تا سقف ۵۰ هزار تومان)",
    description: "قابل استفاده برای کلیه کالاهای فروشگاه بدون محدودیت دسته‌بندی",
    type: "discount",
    points_required: 50,
    is_active: true,
    quantity_available: 150,
  },
  {
    id: "rew-free-shipping",
    name: "کد ارسال رایگان سفارش",
    description: "حذف هزینه پست پیشتاز یا ارسال اکسپرس برای یک سفارش دلخواه",
    type: "voucher",
    points_required: 75,
    is_active: true,
    quantity_available: 200,
  },
  {
    id: "rew-cash-50",
    name: "بن تخفیف ۵۰ هزار تومانی",
    description: "کسر مستقیم ۵۰,۰۰۰ تومان از سبد خرید برای سفارش‌های بالای ۲۰۰ هزار تومان",
    type: "discount",
    points_required: 120,
    is_active: true,
    quantity_available: 80,
  },
  {
    id: "rew-cash-100",
    name: "کارت هدیه ۱۰۰ هزار تومانی",
    description: "کد هدیه ۱۰۰,۰۰۰ تومانی بدون محدودیت حداقل خرید و قابل انتقال به دیگران",
    type: "voucher",
    points_required: 200,
    is_active: true,
    quantity_available: 45,
  },
  {
    id: "rew-gift-mug",
    name: "ماگ سرامیکی اختصاصی باشگاه مشتریان",
    description: "ماگ طرح اختصاصی با پوشش مات و ارسال به عنوان هدیه همراه سفارش بعدی",
    type: "gift",
    points_required: 250,
    is_active: true,
    quantity_available: 30,
  },
  {
    id: "rew-cash-200",
    name: "بن خرید ۲۰۰ هزار تومانی پلاتینیوم",
    description: "ویژه مشتریان طلایی و پلاتینیوم، قابل اعمال بر روی تمام محصولات تخفیف‌دار",
    type: "voucher",
    points_required: 380,
    is_active: true,
    quantity_available: 20,
  },
];

/**
 * Fetch current user's gamification points summary and available rewards.
 */
export async function fetchGamificationSummary(): Promise<ApiUserPointsSummary> {
  try {
    const { data } = await apiClient.get<ApiUserPointsSummary>("/gamification/summary");
    return data;
  } catch (error) {
    // Backend unavailable/401 → honest zero balance (never invent points).
    // The catalog still comes from FALLBACK_REWARDS so the page renders.
    return {
      total_points_earned: 0,
      points_spent: 0,
      points_available: 0,
      rank: "bronze",
      available_rewards: FALLBACK_REWARDS,
    };
  }
}

/**
 * Fetch claimable rewards catalog from GET /api/v1/gamification/rewards
 */
export async function fetchGamificationRewards(): Promise<ApiReward[]> {
  try {
    const { data } = await apiClient.get<ApiReward[]>("/gamification/rewards");
    if (Array.isArray(data) && data.length > 0) {
      return data;
    }
    return FALLBACK_REWARDS;
  } catch (error) {
    return FALLBACK_REWARDS;
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

/**
 * Earn points via backend loyalty API if available
 */
export async function earnLoyaltyPoints(
  points: number,
  description: string,
  referenceType: string = "gamification_wheel",
): Promise<void> {
  try {
    await apiClient.post("/loyalty/earn", {
      points,
      description,
      reference_type: referenceType,
    });
  } catch {
    // Silently ignore if offline or unauthenticated
  }
}
