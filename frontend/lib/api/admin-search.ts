import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type SearchEntity = "order" | "customer" | "ticket" | "product" | "vendor";

export interface SearchHit {
  entity_type: SearchEntity;
  entity_label: string;
  entity_id: string;
  title: string;
  subtitle: string | null;
  status: string | null;
  url: string;
  extra: Record<string, unknown>;
}

export interface AdminSearchResult {
  term: string;
  groups: Record<string, SearchHit[]>;
  total: number;
  errors: Record<string, string>;
  searched_at?: string;
  note?: string;
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const adminSearchApi = {
  /** جست‌وجوی سراسری روی سفارش، مشتری، تیکت، محصول و فروشنده */
  search: async (params: {
    q: string;
    entities?: SearchEntity[];
    per_type_limit?: number;
  }): Promise<AdminSearchResult> => {
    const res = await apiClient.get<AdminSearchResult>("/admin/search/global", {
      params,
      paramsSerializer: { indexes: null },
    });
    return res.data;
  },

  /** انواع موجودیت و برچسب فارسی‌شان */
  entities: async (): Promise<Record<string, string>> => {
    const res = await apiClient.get<Record<string, string>>("/admin/search/entities");
    return res.data;
  },
};
