"""Pydantic schemas for the tgnotif admin API."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class TgNotifConfigUpdate(BaseModel):
    """Request body for updating tgnotif config — all fields optional."""

    model_config = ConfigDict(extra="forbid")

    bot_token: str | None = None
    enabled: bool | None = None

    # Per-status routing
    chat_id_pending: str | None = None
    chat_id_processing: str | None = None
    chat_id_doing_verified: str | None = None
    chat_id_completed: str | None = None
    chat_id_canceled: str | None = None
    topic_id_pending: str | None = None
    topic_id_processing: str | None = None
    topic_id_doing_verified: str | None = None
    topic_id_completed: str | None = None
    topic_id_canceled: str | None = None

    # Webhook secret
    webhook_secret: str | None = None

    # Field toggles
    show_order_id: bool | None = None
    show_status: bool | None = None
    show_items: bool | None = None
    show_variant_info: bool | None = None
    show_sku: bool | None = None
    show_total: bool | None = None
    show_subtotal: bool | None = None
    show_shipping: bool | None = None
    show_tax: bool | None = None
    show_payment_method: bool | None = None
    show_payment_status: bool | None = None
    show_payment_ref: bool | None = None
    show_coupon: bool | None = None
    show_order_link: bool | None = None
    show_date: bool | None = None
    show_customer_name: bool | None = None
    show_phone: bool | None = None
    show_national_code: bool | None = None
    show_verified: bool | None = None
    show_ip: bool | None = None
    show_address: bool | None = None
    show_notes: bool | None = None
    show_custom_fields: bool | None = None


class TgNotifConfigResponse(BaseModel):
    """Response with (public) config values — bot_token + webhook_secret masked."""

    model_config = ConfigDict(extra="allow")

    bot_token: str = ""
    enabled: bool = True

    chat_id_pending: str = ""
    chat_id_processing: str = ""
    chat_id_doing_verified: str = ""
    chat_id_completed: str = ""
    chat_id_canceled: str = ""
    topic_id_pending: str = ""
    topic_id_processing: str = ""
    topic_id_doing_verified: str = ""
    topic_id_completed: str = ""
    topic_id_canceled: str = ""

    webhook_secret: str = ""

    show_order_id: bool = True
    show_status: bool = True
    show_items: bool = True
    show_variant_info: bool = True
    show_sku: bool = False
    show_total: bool = True
    show_subtotal: bool = False
    show_shipping: bool = False
    show_tax: bool = False
    show_payment_method: bool = True
    show_payment_status: bool = False
    show_payment_ref: bool = False
    show_coupon: bool = True
    show_order_link: bool = True
    show_date: bool = True
    show_customer_name: bool = True
    show_phone: bool = True
    show_national_code: bool = False
    show_verified: bool = True
    show_ip: bool = False
    show_address: bool = False
    show_notes: bool = False
    show_custom_fields: bool = True
