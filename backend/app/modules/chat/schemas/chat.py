"""Pydantic v2 schemas for the chat module."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Public widget config ─────────────────────────────────────────────────


class ChatPublicConfig(BaseModel):
    """The subset of widget config the storefront may read without auth.

    Deliberately excludes ``n8n_webhook_url``, ``telegram_bot_token`` and
    ``telegram_chat_id`` — those live in the same settings row but must never
    reach a browser.
    """

    enabled: bool = True
    lang: str = "fa"
    color_primary: str = "#007ACC"
    color_header: str = "#007ACC"
    color_button: str = "#007ACC"
    color_chatbg: str = "#EEEEEE"
    color_viewbg: str = "#EEEEEE"
    welcome_title: str = ""
    welcome_sub: str = ""
    welcome_message: str = ""
    widget_width: int = 394
    widget_height: int = 650
    btn_bottom_desktop: int = 20
    btn_side_desktop: int = 20
    btn_bottom_mobile: int = 70
    btn_side_mobile: int = 12
    widget_icon_url: str = ""
    user_avatar_url: str = ""
    ai_avatar_url: str = ""
    admin_avatar_url: str = ""
    handoff_button_text: str = "انتقال به انسان"
    handoff_success_text: str = "✅ وصل شد"
    quick_replies: list[str] = Field(default_factory=list)
    quick_flow: list[dict[str, Any]] = Field(default_factory=list)
    prechat_fields: list[dict[str, Any]] = Field(default_factory=list)
    faqs: list[dict[str, Any]] = Field(default_factory=list)
    news: list[dict[str, Any]] = Field(default_factory=list)
    proactive_enabled: bool = False
    proactive_delay: int = 5
    proactive_text: str = "سلام! راهنمایی نیاز دارید؟"
    proactive_cooldown: int = 6
    color_proactive_bg: str = "#ffffff"
    color_proactive_text: str = "#101010"
    #: Cache-busting hash of the config (the plugin's ``config.hash``).
    config_hash: str = ""


# ── Session ──────────────────────────────────────────────────────────────


class ChatSessionStartRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    user_name: str = Field(default="", max_length=200)
    user_email: str = Field(default="", max_length=200)
    user_phone: str = Field(default="", max_length=50)
    user_data: dict[str, Any] = Field(default_factory=dict)


class ChatSessionResponse(BaseModel):
    session_key: str
    user_name: str
    handoff_until: datetime | None = None


# ── Messages ─────────────────────────────────────────────────────────────


class ChatMessageCreate(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    message: str = Field(..., min_length=1, max_length=8000)


class ChatMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    role: str
    message: str
    time: str = ""
    is_read: bool = False
    sender_name: str = ""


class ChatMessageCreatedResponse(BaseModel):
    id: int


class ChatHistoryResponse(BaseModel):
    messages: list[ChatMessageResponse]
    handoff_until: int = 0


class ChatPollResponse(BaseModel):
    messages: list[ChatMessageResponse]
    updates: list[dict[str, Any]] = Field(default_factory=list)
    handoff_until: int = 0


class ChatReadRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)


class ChatFlowEntry(BaseModel):
    role: str = "ai"
    message: str = ""
    sender_name: str = ""


class ChatFlowCompleteRequest(BaseModel):
    """A completed quick-reply flow: the entries to save + an optional final text."""

    session_key: str = Field(..., min_length=4, max_length=120)
    flow_context: list[ChatFlowEntry] = Field(default_factory=list)
    final_msg: str = ""


class ChatFlowCompleteResponse(BaseModel):
    last_id: int = 0
    saved_ids: list[int] = Field(default_factory=list)


class ChatPollRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    last_id: int = 0


# ── Heartbeat / presence ─────────────────────────────────────────────────


class ChatHeartbeatRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    tab_id: str = Field(default="def", max_length=40)
    page_url: str = Field(default="", max_length=2000)
    page_title: str = Field(default="", max_length=500)


# ── Handoff ──────────────────────────────────────────────────────────────


class ChatHandoffRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)


class ChatHandoffResponse(BaseModel):
    handoff_until: int = 0


class ChatHandoffToggleRequest(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    state: int = 0  # 1 = human owns the thread, 0 = back to AI


# ── Admin ────────────────────────────────────────────────────────────────


class ChatConversationRow(BaseModel):
    session_key: str
    user_name: str
    time_ago: str
    last_message: str
    unread_count: int
    is_online: bool
    last_seen_text: str = ""
    current_page: str = ""


class ChatAdminMessageCreate(BaseModel):
    session_key: str = Field(..., min_length=4, max_length=120)
    message: str = Field(..., min_length=1, max_length=8000)


class ChatSessionInfoField(BaseModel):
    label: str
    value: str


class ChatSessionInfoResponse(BaseModel):
    fields: list[ChatSessionInfoField]


class ChatOnlineUser(BaseModel):
    session_key: str
    user_name: str
    last_seen: str
    user_ip: str = ""
    user_agent: str = ""
    user_phone: str = ""
    user_email: str = ""
    is_wp_user: bool = False
    tabs: list[dict[str, str]] = Field(default_factory=list)


class ChatOnlineUsersResponse(BaseModel):
    users: list[ChatOnlineUser]
    show_fields: list[str]


class ChatConfigUpdateRequest(BaseModel):
    """The admin write payload — the whole private config object."""

    config: dict[str, Any]


class ChatConfigResponse(BaseModel):
    config: dict[str, Any]


class ChatUnreadCountsRequest(BaseModel):
    session_keys: list[str] = Field(default_factory=list)


class ChatIdResponse(BaseModel):
    id: int


class ChatOkResponse(BaseModel):
    ok: bool = True


class ChatValidateSessionsRequest(BaseModel):
    session_keys: list[str] = Field(default_factory=list)
