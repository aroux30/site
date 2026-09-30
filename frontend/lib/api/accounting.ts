import apiClient from "./client";

// ── Accounting feed (دفتر روزنامه و کدینگ حسابها) admin API ─────────────────

export type AccountType = "asset" | "liability" | "equity" | "revenue" | "expense";
export type JournalEntryStatus = "draft" | "posted" | "reversed";
export type JournalSourceType =
  | "order"
  | "payment"
  | "refund"
  | "wallet"
  | "settlement"
  | "manual";
export type PeriodStatus = "open" | "closed";

export interface Account {
  id: string;
  code: string;
  name_fa: string;
  type: AccountType;
  parent_id: string | null;
  is_active: boolean;
  description: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface AccountList {
  items: Account[];
  total: number;
}

export interface JournalLine {
  id: string;
  account_id: string;
  account_code: string | null;
  account_name_fa: string | null;
  position: number;
  debit_rial: number;
  credit_rial: number;
  description: string | null;
}

export interface JournalEntry {
  id: string;
  number: string | null;
  fiscal_period: string | null;
  entry_date: string;
  source_type: JournalSourceType;
  source_id: string | null;
  entry_type: string;
  description: string;
  status: JournalEntryStatus;
  hash: string | null;
  previous_hash: string | null;
  posted_at: string | null;
  reversal_of_id: string | null;
  reversal_reason: string | null;
  lines: JournalLine[];
  total_debit_rial: number;
  total_credit_rial: number;
  balanced: boolean;
  created_at: string | null;
}

export interface JournalEntryList {
  items: JournalEntry[];
  total: number;
  page: number;
  page_size: number;
}

export interface AccountingPeriod {
  id: string;
  fiscal_period: string;
  status: PeriodStatus;
  closed_at: string | null;
  closed_by: string | null;
  entry_count: number;
  debit_total_rial: number;
  credit_total_rial: number;
}

export interface PeriodList {
  items: AccountingPeriod[];
  total: number;
}

export interface ChainBrokenLink {
  entry_id: string;
  number: string | null;
  fiscal_period: string | null;
  previous_hash_ok: boolean;
  own_hash_ok: boolean;
}

export interface ChainVerification {
  valid: boolean;
  entries_checked: number;
  first_broken: ChainBrokenLink | null;
}

export interface JournalLineInput {
  account_code?: string;
  account_id?: string;
  debit_rial: number;
  credit_rial: number;
  description?: string;
}

const ADMIN = "/admin/accounting";

export const accountingApi = {
  // ── Chart of accounts ────────────────────────────────────────────────────
  listAccounts: async (params?: {
    type?: AccountType;
    is_active?: boolean;
  }): Promise<AccountList> => {
    const response = await apiClient.get<AccountList>(`${ADMIN}/accounts`, { params });
    return response.data;
  },

  createAccount: async (data: {
    code: string;
    name_fa: string;
    type: AccountType;
    parent_id?: string | null;
    is_active?: boolean;
    description?: string | null;
  }): Promise<Account> => {
    const response = await apiClient.post<Account>(`${ADMIN}/accounts`, data);
    return response.data;
  },

  updateAccount: async (
    id: string,
    data: Partial<{
      name_fa: string;
      parent_id: string | null;
      is_active: boolean;
      description: string | null;
    }>,
  ): Promise<Account> => {
    const response = await apiClient.patch<Account>(`${ADMIN}/accounts/${id}`, data);
    return response.data;
  },

  seedAccounts: async (): Promise<AccountList> => {
    const response = await apiClient.post<AccountList>(`${ADMIN}/accounts/seed`);
    return response.data;
  },

  // ── Journal ──────────────────────────────────────────────────────────────
  listEntries: async (params?: {
    fiscal_period?: string;
    status?: JournalEntryStatus;
    source_type?: JournalSourceType;
    page?: number;
    page_size?: number;
  }): Promise<JournalEntryList> => {
    const response = await apiClient.get<JournalEntryList>(`${ADMIN}/journal`, { params });
    return response.data;
  },

  getEntry: async (id: string): Promise<JournalEntry> => {
    const response = await apiClient.get<JournalEntry>(`${ADMIN}/journal/${id}`);
    return response.data;
  },

  createEntry: async (data: {
    entry_date?: string;
    description: string;
    lines: JournalLineInput[];
    post_now?: boolean;
  }): Promise<JournalEntry> => {
    const response = await apiClient.post<JournalEntry>(`${ADMIN}/journal`, data);
    return response.data;
  },

  postEntry: async (id: string): Promise<JournalEntry> => {
    const response = await apiClient.post<JournalEntry>(`${ADMIN}/journal/${id}/post`);
    return response.data;
  },

  reverseEntry: async (id: string, reason: string): Promise<JournalEntry> => {
    const response = await apiClient.post<JournalEntry>(`${ADMIN}/journal/${id}/reverse`, {
      reason,
    });
    return response.data;
  },

  verifyChain: async (params?: { fiscal_period?: string }): Promise<ChainVerification> => {
    const response = await apiClient.get<ChainVerification>(`${ADMIN}/journal/verify-chain`, {
      params,
    });
    return response.data;
  },

  // ── Periods ──────────────────────────────────────────────────────────────
  listPeriods: async (params?: { fiscal_period?: string }): Promise<PeriodList> => {
    const response = await apiClient.get<PeriodList>(`${ADMIN}/periods`, { params });
    return response.data;
  },

  closePeriod: async (fiscal_period: string): Promise<AccountingPeriod> => {
    const response = await apiClient.post<AccountingPeriod>(`${ADMIN}/periods/close`, {
      fiscal_period,
    });
    return response.data;
  },

  // ── Export ───────────────────────────────────────────────────────────────
  exportCsv: async (params?: {
    from?: string;
    to?: string;
    fiscal_period?: string;
  }): Promise<Blob> => {
    const response = await apiClient.get(`${ADMIN}/export.csv`, {
      params,
      responseType: "blob",
    });
    return response.data as Blob;
  },

  exportJson: async (params?: {
    from?: string;
    to?: string;
    fiscal_period?: string;
  }): Promise<Record<string, unknown>> => {
    const response = await apiClient.get<Record<string, unknown>>(`${ADMIN}/export.json`, {
      params,
    });
    return response.data;
  },
};
