import apiClient from "./client";

export interface TicketMessage {
  id: string;
  ticket_id: string;
  sender_id: string;
  body: string;
  is_staff: boolean;
  created_at: string;
}

export interface TicketItem {
  id: string;
  user_id: string;
  subject: string;
  priority: "low" | "medium" | "high" | "urgent";
  status: "open" | "in_progress" | "waiting" | "resolved" | "closed";
  assigned_to?: string | null;
  ticket_number: string;
  created_at: string;
  updated_at: string;
  /** Admin-list extras: identity + thread summary (null on customer routes). */
  customer_name?: string | null;
  customer_phone?: string | null;
  messages_count?: number | null;
  last_message_preview?: string | null;
  last_message_at?: string | null;
}

export interface TicketStats {
  byStatus: Map<TicketItem["status"], number>;
  totalTickets: number;
  urgentOpen: number;
  unassigned: number;
}

export interface TicketDetail extends TicketItem {
  messages: TicketMessage[];
}

export interface TicketListResponse {
  items: TicketItem[];
  total: number;
}

export interface CreateTicketInput {
  subject: string;
  priority?: TicketItem["priority"];
  body: string;
}

export interface TicketListParams {
  status?: TicketItem["status"];
  priority?: TicketItem["priority"];
  search?: string;
  skip?: number;
  limit?: number;
}

export async function fetchUserTickets(params?: TicketListParams): Promise<TicketListResponse> {
  const { data } = await apiClient.get<TicketListResponse>("/support/tickets", { params });
  return data;
}

export async function fetchUserTicketById(id: string): Promise<TicketDetail> {
  const { data } = await apiClient.get<TicketDetail>(`/support/tickets/${id}`);
  return data;
}

export async function createUserTicket(payload: CreateTicketInput): Promise<TicketItem> {
  const { data } = await apiClient.post<TicketItem>("/support/tickets", payload);
  return data;
}

export async function replyUserTicket(ticketId: string, body: string): Promise<TicketMessage> {
  const { data } = await apiClient.post<TicketMessage>(`/support/tickets/${ticketId}/messages`, { body });
  return data;
}

export async function fetchAdminTickets(params?: TicketListParams): Promise<TicketListResponse> {
  const { data } = await apiClient.get<TicketListResponse>("/support/admin/tickets", { params });
  return data;
}

/** Whole-table per-status counts for the admin board headers. */
export async function fetchAdminTicketStats(): Promise<TicketStats> {
  const { data } = await apiClient.get<{
    by_status: { status: string; count: number }[];
    total_tickets: number;
    urgent_open: number;
    unassigned: number;
  }>("/support/admin/tickets/stats");
  const byStatus = new Map<TicketItem["status"], number>();
  for (const row of data.by_status ?? []) {
    byStatus.set(row.status as TicketItem["status"], Number(row.count ?? 0));
  }
  return {
    byStatus,
    totalTickets: Number(data.total_tickets ?? 0),
    urgentOpen: Number(data.urgent_open ?? 0),
    unassigned: Number(data.unassigned ?? 0),
  };
}

export async function fetchAdminTicketById(id: string): Promise<TicketDetail> {
  const { data } = await apiClient.get<TicketDetail>(`/support/admin/tickets/${id}`);
  return data;
}

export async function replyAdminTicket(ticketId: string, body: string): Promise<TicketMessage> {
  const { data } = await apiClient.post<TicketMessage>(`/support/admin/tickets/${ticketId}/reply`, { body });
  return data;
}

export async function updateAdminTicketStatus(
  ticketId: string,
  status: TicketItem["status"],
): Promise<TicketItem> {
  const { data } = await apiClient.patch<TicketItem>(`/support/admin/tickets/${ticketId}`, { status });
  return data;
}

// --- Missing support endpoints ---

/** ارسال پیام تماس با ما (بدون نیاز به لاگین). The `email` field was removed
 *  on 2026-10-07 with the rest of the email feature. */
export async function submitContactMessage(payload: {
  name: string;
  phone?: string;
  subject: string;
  body?: string;
  message?: string;
}): Promise<{ success: boolean }> {
  const bodyPayload = {
    name: payload.name,
    subject: payload.subject,
    message: payload.message || payload.body || "",
  };
  const { data } = await apiClient.post<{ success: boolean }>("/support/contact", bodyPayload);
  return data;
}

/** بستن تیکت توسط کاربر */
export async function closeTicket(ticketId: string): Promise<TicketItem> {
  const { data } = await apiClient.post<TicketItem>(`/support/tickets/${ticketId}/close`);
  return data;
}

/** بازگشایی تیکت بسته‌شده */
export async function reopenTicket(ticketId: string): Promise<TicketItem> {
  const { data } = await apiClient.post<TicketItem>(`/support/tickets/${ticketId}/reopen`);
  return data;
}
