import apiClient from "./client";

// --- Types ---

export interface AuditLog {
  id: string; // backend is UUIDv4
  actor_id: string | null;
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

export interface OperationalException {
  id: number | string;
  type?: string;
  exception_type?: string;
  severity: "low" | "medium" | "high" | "critical" | string;
  message?: string;
  details?: Record<string, unknown> | string | null;
  resource_type?: string;
  entity_type?: string;
  resource_id?: string;
  entity_id?: string;
  status: "open" | "assigned" | "resolved" | "dismissed" | string;
  assigned_to?: number | string | null;
  owner_id?: string | null;
  resolved_at?: string | null;
  resolution_notes?: string | null;
  created_at: string;
}

function normalizeException(raw: any): OperationalException {
  return {
    ...raw,
    type: raw.type || raw.exception_type || "",
    exception_type: raw.exception_type || raw.type || "",
    message: raw.message || (typeof raw.details === "string" ? raw.details : JSON.stringify(raw.details || "")),
    resource_type: raw.resource_type || raw.entity_type,
    entity_type: raw.entity_type || raw.resource_type,
    resource_id: raw.resource_id || raw.entity_id,
    entity_id: raw.entity_id || raw.resource_id,
    assigned_to: raw.assigned_to || raw.owner_id,
    owner_id: raw.owner_id || raw.assigned_to,
  };
}

/** یک ردیف تغییر سطح فیلد (ERP #9) */
export interface EntityChange {
  id: string;
  entity_type: string;
  entity_id: string;
  operation: "create" | "update" | "delete";
  changed_fields: Array<{ field: string; old_value: unknown; new_value: unknown }>;
  actor_id: string | null;
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

// Note: reconciliation endpoints are already covered by
// frontend/lib/api/reconciliation.ts — not duplicated here.

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

  /** لیست استثناهای عملیاتی */
  listExceptions: async (params?: {
    page?: number;
    status?: string;
    severity?: string;
  }): Promise<{ items: OperationalException[]; total: number }> => {
    const res = await apiClient.get<OperationalException[] | { items: OperationalException[]; total?: number }>(
      "/audit/admin/exceptions",
      { params },
    );
    const raw = res.data;
    // The endpoint may answer with a bare array or a paginated envelope; the
    // envelope is the only shape that carries a total.
    const items = Array.isArray(raw) ? raw : raw?.items || [];
    const total = Array.isArray(raw) ? raw.length : raw?.total ?? items.length;
    return {
      items: items.map(normalizeException),
      total,
    };
  },

  /** تخصیص استثنا به کاربر */
  assignException: async (exceptionId: number | string, assigneeId: number | string): Promise<OperationalException> => {
    const res = await apiClient.patch<OperationalException>(
      `/audit/admin/exceptions/${exceptionId}/assign`,
      { owner_id: String(assigneeId) },
    );
    return normalizeException(res.data);
  },

  /** حل‌وفصل استثنا */
  resolveException: async (exceptionId: number | string, resolution?: string): Promise<OperationalException> => {
    const notes = resolution && resolution.trim().length >= 3 ? resolution.trim() : "برطرف شد";
    const res = await apiClient.patch<OperationalException>(
      `/audit/admin/exceptions/${exceptionId}/resolve`,
      { resolution_notes: notes },
    );
    return normalizeException(res.data);
  },

  /** رد استثنا */
  dismissException: async (exceptionId: number | string, reason?: string): Promise<OperationalException> => {
    const notes = reason && reason.trim().length >= 3 ? reason.trim() : "نادیده گرفته شد";
    const res = await apiClient.patch<OperationalException>(
      `/audit/admin/exceptions/${exceptionId}/dismiss`,
      { resolution_notes: notes },
    );
    return normalizeException(res.data);
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
