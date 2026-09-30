"""Newsletter schemas package."""

from app.modules.newsletter.schemas.newsletter import (
    ConfirmRequest,
    SubscribeRequest,
    SubscribeResponse,
    SubscriberListResponse,
    SubscriberResponse,
    SubscriptionStatusResponse,
    UnsubscribeRequest,
)

__all__ = [
    "ConfirmRequest",
    "SubscribeRequest",
    "SubscribeResponse",
    "SubscriberListResponse",
    "SubscriberResponse",
    "SubscriptionStatusResponse",
    "UnsubscribeRequest",
]
