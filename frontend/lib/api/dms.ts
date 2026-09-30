import apiClient from "./client";

// ── Types ───────────────────────────────────────────────────────────────────

export type AttachmentKind =
  | "general"
  | "contract"
  | "invoice"
  | "receipt"
  | "shipping_label"
  | "inspection"
  | "return_form"
  | "other";

export type ArchivedDocumentKind =
  | "invoice"
  | "credit_note"
  | "receipt"
  | "settlement"
  | "other";

export interface Attachment {
  id: string;
  entity_type: string;
  entity_id: string;
  kind: AttachmentKind;
  file_name: string;
  file_url: string;
  file_size: number;
  content_type: string | null;
  title: string | null;
  notes: string | null;
  uploaded_by_id: string | null;
  created_at: string;
}

export interface ArchivedDocument {
  id: string;
  kind: ArchivedDocumentKind;
  document_key: string;
  entity_type: string;
  entity_id: string;
  archive_path: string;
  content_type: string;
  file_size: number | null;
  content_hash: string | null;
  metadata_json: Record<string, unknown> | null;
  fiscal_period: string | null;
  is_superseded: boolean;
  created_at: string;
}

// ── API (admin) ─────────────────────────────────────────────────────────────

export const dmsApi = {
  /** انواع موجودیت پذیرنده پیوست */
  attachableTypes: async (): Promise<{ entity_types: string[] }> => {
    const res = await apiClient.get<{ entity_types: string[] }>(
      "/documents/admin/attachable-types",
    );
    return res.data;
  },

  /** پیوست به رکورد */
  createAttachment: async (payload: {
    entity_type: string;
    entity_id: string;
    file_name: string;
    file_url: string;
    file_size: number;
    content_type?: string | null;
    kind?: AttachmentKind;
    title?: string | null;
    notes?: string | null;
  }): Promise<Attachment> => {
    const res = await apiClient.post<Attachment>(
      "/documents/admin/attachments",
      payload,
    );
    return res.data;
  },

  /** پیوست‌های یک رکورد */
  listAttachments: async (entityType: string, entityId: string, kind?: AttachmentKind): Promise<Attachment[]> => {
    const res = await apiClient.get<Attachment[]>("/documents/admin/attachments", {
      params: { entity_type: entityType, entity_id: entityId, kind },
    });
    return res.data;
  },

  /** برآی پیوست یک رکورد (برای نشان شکم‌ها) */
  attachmentCounts: async (entityType: string, entityId: string): Promise<Record<string, number>> => {
    const res = await apiClient.get<Record<string, number>>(
      "/documents/admin/attachments/counts",
      { params: { entity_type: entityType, entity_id: entityId } },
    );
    return res.data;
  },

  /** حذف پیوست */
  deleteAttachment: async (attachmentId: string): Promise<void> => {
    await apiClient.delete(`/documents/admin/attachments/${attachmentId}`);
  },

  /** جست‌وجو در بایگانی اسناد */
  searchArchive: async (params?: {
    kind?: ArchivedDocumentKind;
    entity_type?: string;
    entity_id?: string;
    fiscal_period?: string;
    document_key?: string;
    include_superseded?: boolean;
    limit?: number;
  }): Promise<ArchivedDocument[]> => {
    const res = await apiClient.get<ArchivedDocument[]>("/documents/admin/archive", {
      params,
    });
    return res.data;
  },
};