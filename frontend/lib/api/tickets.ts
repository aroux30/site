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

/** ارسال پیام تماس با ما (بدون نیاز به لاگین) */
export async function submitContactMessage(payload: {
  name: string;
  email?: string;
  phone?: string;
  subject: string;
  body?: string;
  message?: string;
}): Promise<{ success: boolean }> {
  const bodyPayload = {
    name: payload.name,
    email: payload.email || "guest@example.com",
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
