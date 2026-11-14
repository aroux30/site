import apiClient from "./client";

/**
 * Live-chat widget + admin console API.
 *
 * The public functions are what the storefront widget calls (config, session,
 * message, poll, heartbeat); the `admin*` functions are the staff console.
 * Mirrors the WordPress plugin's AJAX actions 1:1.
 */

// ── Types ────────────────────────────────────────────────────────────────

export interface ChatPublicConfig {
  enabled: boolean;
  lang: string;
  color_primary: string;
  color_header: string;
  color_button: string;
  color_chatbg: string;
  color_viewbg: string;
  welcome_title: string;
  welcome_sub: string;
  welcome_message: string;
  widget_width: number;
  widget_height: number;
  btn_bottom_desktop: number;
  btn_side_desktop: number;
  btn_bottom_mobile: number;
  btn_side_mobile: number;
  widget_icon_url: string;
  user_avatar_url: string;
  ai_avatar_url: string;
  admin_avatar_url: string;
  handoff_button_text: string;
  handoff_success_text: string;
  quick_replies: string[];
  quick_flow: QuickFlowNode[];
  prechat_fields: PrechatField[];
  faqs: { q: string; a: string; cat?: string }[];
  news: { title: string; desc: string; link?: string; icon?: string }[];
  proactive_enabled: boolean;
  proactive_delay: number;
  proactive_text: string;
  proactive_cooldown: number;
  color_proactive_bg: string;
  color_proactive_text: string;
  config_hash: string;
}

export interface PrechatField {
  label: string;
  key: string;
  type: string;
  required: boolean;
}

export interface QuickFlowNode {
  id?: string;
  text: string;
  actionType: "reply" | "menu";
  replyText?: string;
  children?: QuickFlowNode[];
}

export interface ChatMessage {
  id: number;
  role: "user" | "ai" | "admin" | "system";
  message: string;
  time: string;
  is_read: boolean;
  sender_name: string;
}

export interface ChatPollResult {
  messages: ChatMessage[];
  updates: { id: number; is_read: boolean }[];
  handoff_until: number;
}

export interface ChatConversation {
  session_key: string;
  user_name: string;
  time_ago: string;
  last_message: string;
  unread_count: number;
  is_online: boolean;
  last_seen_text: string;
  current_page: string;
}

export interface ChatOnlineUser {
  session_key: string;
  user_name: string;
  last_seen: string;
  user_ip: string;
  user_agent: string;
  user_phone: string;
  user_email: string;
  is_wp_user: boolean;
  tabs: { url: string; title: string }[];
}

// ── Public widget ────────────────────────────────────────────────────────

export async function fetchChatConfig(): Promise<ChatPublicConfig> {
  const { data } = await apiClient.get<ChatPublicConfig>("/chat/config");
  return data;
}

export async function startChatSession(payload: {
  session_key: string;
  user_name?: string;
  user_email?: string;
  user_phone?: string;
  user_data?: Record<string, unknown>;
}): Promise<{ session_key: string; user_name: string; handoff_until: string | null }> {
  const { data } = await apiClient.post("/chat/session", payload);
  return data;
}

export async function sendChatMessage(
  sessionKey: string,
  message: string,
): Promise<{ id: number }> {
  const { data } = await apiClient.post<{ id: number }>("/chat/message", {
    session_key: sessionKey,
    message,
  });
  return data;
}

export async function completeChatFlow(
  sessionKey: string,
  flowContext: { role: string; message: string; sender_name?: string }[],
  finalMsg: string,
): Promise<{ last_id: number; saved_ids: number[] }> {
  const { data } = await apiClient.post("/chat/flow-complete", {
    session_key: sessionKey,
    flow_context: flowContext,
    final_msg: finalMsg,
  });
  return data;
}

export async function pollChatMessages(
  sessionKey: string,
  lastId: number,
): Promise<ChatPollResult> {
  const { data } = await apiClient.post<ChatPollResult>("/chat/messages", {
    session_key: sessionKey,
    last_id: lastId,
  });
  return data;
}

export async function fetchChatHistory(sessionKey: string): Promise<{
  messages: ChatMessage[];
  handoff_until: number;
}> {
  const { data } = await apiClient.post("/chat/history", { session_key: sessionKey });
  return data;
}

export async function requestChatHandoff(sessionKey: string): Promise<{ handoff_until: number }> {
  const { data } = await apiClient.post("/chat/handoff", { session_key: sessionKey });
  return data;
}

export async function sendChatHeartbeat(payload: {
  session_key: string;
  tab_id: string;
  page_url: string;
  page_title: string;
}): Promise<void> {
  await apiClient.post("/chat/heartbeat", payload);
}

export async function fetchChatUnreadCounts(
  sessionKeys: string[],
): Promise<Record<string, number>> {
  const { data } = await apiClient.post<Record<string, number>>("/chat/unread-counts", {
    session_keys: sessionKeys,
  });
  return data;
}

export async function validateChatSessions(sessionKeys: string[]): Promise<string[]> {
  const { data } = await apiClient.post<string[]>("/chat/validate-sessions", {
    session_keys: sessionKeys,
  });
  return data;
}

export async function uploadChatFile(file: File): Promise<{ url: string; name: string }> {
  const fd = new FormData();
  fd.append("file", file);
  const { data } = await apiClient.post("/chat/upload", fd, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return data;
}

/**
 * Subscribe to the live SSE stream for a session.
 *
 * Returns a disposer. The stream is a *notification* channel — it says "there
 * are messages newer than last_id", and the caller fetches them via the normal
 * endpoint. If `EventSource` is unavailable or the connection errors, the
 * caller's polling loop keeps working (this is the upgrade, not a replacement).
 */
export function subscribeChatStream(
  sessionKey: string,
  lastId: number,
  onMessages: (info: { last_id: number; count: number }) => void,
): () => void {
  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    return () => {};
  }
  const url = `/api/v1/chat/stream?session_key=${encodeURIComponent(sessionKey)}&last_id=${lastId}`;
  const source = new EventSource(url, { withCredentials: true });
  source.addEventListener("messages", (ev) => {
    try {
      onMessages(JSON.parse((ev as MessageEvent).data));
    } catch {
      /* malformed frame — ignore, the poller will reconcile */
    }
  });
  // On error the browser auto-reconnects; nothing to do here.
  return () => source.close();
}

// ── Admin console ────────────────────────────────────────────────────────

export async function fetchChatConversations(): Promise<ChatConversation[]> {
  const { data } = await apiClient.get<ChatConversation[]>("/admin/chat/conversations");
  return data;
}

export async function fetchChatAdminHistory(sessionKey: string): Promise<{
  messages: ChatMessage[];
  handoff_until: number;
}> {
  const { data } = await apiClient.post("/admin/chat/history", { session_key: sessionKey });
  return data;
}

export async function pollChatAdmin(
  sessionKey: string,
  lastId: number,
): Promise<ChatPollResult> {
  const { data } = await apiClient.post<ChatPollResult>("/admin/chat/poll", {
    session_key: sessionKey,
    last_id: lastId,
  });
  return data;
}

export async function sendChatAdminMessage(
  sessionKey: string,
  message: string,
): Promise<{ id: number }> {
  const { data } = await apiClient.post<{ id: number }>("/admin/chat/send", {
    session_key: sessionKey,
    message,
  });
  return data;
}

export async function fetchChatSessionInfo(
  sessionKey: string,
): Promise<{ fields: { label: string; value: string }[] }> {
  const { data } = await apiClient.post("/admin/chat/session-info", {
    session_key: sessionKey,
  });
  return data;
}

export async function deleteChatSession(sessionKey: string): Promise<void> {
  await apiClient.post("/admin/chat/delete-session", { session_key: sessionKey });
}

export async function toggleChatHandoff(
  sessionKey: string,
  state: number,
): Promise<{ handoff_until: number }> {
  const { data } = await apiClient.post("/admin/chat/handoff-toggle", {
    session_key: sessionKey,
    state,
  });
  return data;
}

export async function fetchChatOnlineUsers(): Promise<{
  users: ChatOnlineUser[];
  show_fields: string[];
}> {
  const { data } = await apiClient.get("/admin/chat/online-users");
  return data;
}

export async function fetchChatAdminConfig(): Promise<{ config: Record<string, unknown> }> {
  const { data } = await apiClient.get("/admin/chat/config");
  return data;
}

export async function updateChatAdminConfig(
  config: Record<string, unknown>,
): Promise<{ config: Record<string, unknown> }> {
  const { data } = await apiClient.put("/admin/chat/config", { config });
  return data;
}
