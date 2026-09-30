import apiClient from "./client";

/** The caller's stable referral code and the shareable invite link. */
export interface ApiReferralCode {
  referral_code: string;
  referral_link: string;
}

/** Aggregated referral statistics for the authenticated user. */
export interface ApiReferralStats {
  total_referrals: number;
  completed_referrals: number;
  pending_referrals: number;
  level1_count: number;
  level2_count: number;
  total_commission_earned: number;
  total_commission_pending: number;
}

export interface ApiReferral {
  id: string;
  referrer_id: string;
  referred_id: string;
  code: string;
  level: number;
  status: string;
  created_at: string;
}

export interface ApiReferralList {
  items: ApiReferral[];
  total: number;
}

/**
 * Fetch the caller's referral code.
 *
 * The code is persisted server-side, so it is stable across calls — it is
 * safe to display and share.
 */
export async function fetchReferralCode(): Promise<ApiReferralCode> {
  const { data } = await apiClient.get<ApiReferralCode>("/referrals/referral");
  return data;
}

export async function fetchReferralStats(): Promise<ApiReferralStats> {
  const { data } = await apiClient.get<ApiReferralStats>("/referrals/referral/stats");
  return data;
}

export async function fetchReferrals(skip = 0, limit = 20): Promise<ApiReferralList> {
  const { data } = await apiClient.get<ApiReferralList>("/referrals/referrals", {
    params: { skip, limit },
  });
  return data;
}

export interface ApiCommission {
  id: string;
  referral_id: string;
  order_id: string;
  amount: number;
  level: number;
  status: "pending" | "credited" | "expired";
  created_at: string;
  credited_at?: string;
}

export interface ApiCommissionList {
  items: ApiCommission[];
  total: number;
}

export async function fetchCommissions(skip = 0, limit = 20): Promise<ApiCommissionList> {
  const { data } = await apiClient.get<ApiCommissionList>("/referrals/referral/commissions", {
    params: { skip, limit },
  });
  return data;
}

/** Build the absolute invite URL a friend can open to be linked to the referrer. */
export function buildInviteUrl(referralLink: string): string {
  const origin = typeof window === "undefined" ? "" : window.location.origin;
  return `${origin}${referralLink.startsWith("/") ? "" : "/"}${referralLink}`;
}
