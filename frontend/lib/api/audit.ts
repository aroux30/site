import apiClient from "./client";

// --- Types ---

export interface AuditLog {
  id: string; // backend is UUIDv4
  actor_id: string | null;
  /** نام نمایشی عامل رویداد (از پروفایل)؛ null اگر حساب حذف شده باشد */
  actor_name?: string | null;
  /** شماره تماس عامل رویداد — شناسهٔ ورودی که اپراتور میشناسد */
  actor_phone?: string | null;
  action: string;
  resource: string;
  resource_id: string | null;
  before?: Record<string, unknown> | null;
  after?: Record<string, unknown> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  request_id?: string | null;
  extra_data?: Record<string, unknown> | null;
  created_at: string;
}

/** یک ردیف تغییر سطح فیلد (ERP #9) */
export interface EntityChange {
  id: string;
  entity_type: string;
  entity_id: string;
  operation: "create" | "update" | "delete";
  changed_fields: Array<{ field: string; old_value: unknown; new_value: unknown }>;
  actor_id: string | null;
  /** نام نمایشی عامل تغییر (از پروفایل)؛ null اگر حساب حذف شده باشد */
  actor_name?: string | null;
  /** شماره تماس عامل تغییر */
  actor_phone?: string | null;
  actor_type: "user" | "system" | "celery";
  request_id: string | null;
  source: "api" | "admin" | "service" | "seed";
  occurred_at: string;
  truncated: boolean;
  created_at: string;
}

/** نوع موجودیتی که تغییراتش ثبت شده */
export interface TrackedEntitySummary {
  entity_type: string;
  row_count: number;
  last_change_at: string | null;
}

// --- API (admin) ---

export const auditApi = {
  /** لیست لاگ‌های ممیزی */
  listAuditLogs: async (params?: {
    page?: number;
    page_size?: number;
    actor_id?: string;
    action?: string;
    resource?: string;
    resource_id?: string;
    from_date?: string;
    to_date?: string;
  }): Promise<{ items: AuditLog[]; total: number }> => {
    const res = await apiClient.get<{ items: AuditLog[]; total: number }>(
      "/audit/admin/audit-logs",
      { params },
    );
    return res.data;
  },
};

// ── Field-level change log (ERP feature #9) ─────────────────────────────────

export const changeLogApi = {
  /** لیست تغییرات سطح فیلد با فیلتر */
  list: async (params?: {
    entity_type?: string;
    entity_id?: string;
    actor_id?: string;
    field?: string;
    from_date?: string;
    to_date?: string;
    page?: number;
    page_size?: number;
  }): Promise<{ items: EntityChange[]; total: number; page: number; page_size: number; pages: number }> => {
    const res = await apiClient.get("/audit/admin/audit/changes", { params });
    return res.data;
  },

  /** موجودیت‌هایی که تغییراتشان ثبت شده */
  entities: async (): Promise<TrackedEntitySummary[]> => {
    const res = await apiClient.get<TrackedEntitySummary[]>(
      "/audit/admin/audit/changes/entities",
    );
    return res.data;
  },

  /** تایم‌لاین تغییرات یک رکورد مشخص */
  history: async (
    entityType: string,
    entityId: string,
  ): Promise<{ entity_type: string; entity_id: string; items: EntityChange[] }> => {
    const res = await apiClient.get(
      `/audit/admin/audit/entities/${encodeURIComponent(entityType)}/${encodeURIComponent(entityId)}/history`,
    );
    return res.data;
  },
};
