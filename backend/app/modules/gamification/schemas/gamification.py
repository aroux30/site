"""Pydantic v2 schemas for the gamification module."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    model_validator,
)

# ---------------------------------------------------------------------------
# Gamification Rules
# ---------------------------------------------------------------------------


class GamificationRuleCreate(BaseModel):
    """Schema for creating a gamification rule."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name of the gamification rule",
    )
    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Event type identifier (e.g. order_completed, review_submitted)",
    )
    points: int = Field(
        ...,
        gt=0,
        description="Points awarded when the rule conditions are met",
    )
    conditions: dict[str, Any] | None = Field(
        default=None,
        description="Optional JSON conditions evaluated against event_data",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this rule is active and eligible for matching",
    )


class GamificationRuleUpdate(BaseModel):
    """Schema for updating an existing gamification rule."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    event_type: str | None = Field(default=None, min_length=1, max_length=100)
    points: int | None = Field(default=None, gt=0)
    conditions: dict[str, Any] | None = None
    is_active: bool | None = None


class GamificationRuleResponse(BaseModel):
    """Schema for returning gamification rule details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    event_type: str
    points: int
    conditions: dict[str, Any] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class GamificationRuleListResponse(BaseModel):
    """Paginated or listed gamification rules response."""

    items: list[GamificationRuleResponse]
    total: int


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------


class RewardCreate(BaseModel):
    """Schema for creating a redeemable reward."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Display name of the reward",
    )
    description: str | None = Field(
        default=None,
        description="Detailed description of the reward",
    )
    type: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Reward type (e.g. discount, gift, badge, physical)",
    )
    points_required: int = Field(
        ...,
        gt=0,
        description="Points required to claim this reward",
    )
    is_active: bool = Field(
        default=True,
        description="Whether the reward is currently claimable",
    )
    quantity_available: int | None = Field(
        default=None,
        ge=0,
        description="Available inventory, or None for unlimited",
    )


class RewardUpdate(BaseModel):
    """Schema for updating a redeemable reward."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    type: str | None = Field(default=None, min_length=1, max_length=50)
    points_required: int | None = Field(default=None, gt=0)
    is_active: bool | None = None
    quantity_available: int | None = Field(default=None, ge=0)


class RewardResponse(BaseModel):
    """Schema for returning reward details."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    type: str
    points_required: int
    is_active: bool
    quantity_available: int | None = None
    created_at: datetime
    updated_at: datetime


class RewardListResponse(BaseModel):
    """Paginated or listed rewards response."""

    items: list[RewardResponse]
    total: int


# ---------------------------------------------------------------------------
# Claiming Rewards
# ---------------------------------------------------------------------------


class ClaimRewardRequest(BaseModel):
    """Optional payload when claiming a reward."""

    notes: str | None = Field(
        default=None,
        max_length=500,
        description="Optional user notes or instructions for the claim",
    )


class ClaimRewardResponse(BaseModel):
    """Response returned when a reward is successfully claimed."""

    reward_id: uuid.UUID
    reward_name: str
    points_spent: int
    remaining_points: int
    claimed_at: datetime
    message: str = "Reward claimed successfully"


# ---------------------------------------------------------------------------
# Points and Summary
# ---------------------------------------------------------------------------


class UserPointsSummaryResponse(BaseModel):
    """User points summary covering total earned, spent, available, and rank."""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    total_points_earned: int = Field(
        description="Total points earned by the user across all events"
    )
    points_spent: int = Field(
        default=0,
        description="Total points spent/redeemed by the user",
    )
    points_available: int = Field(
        description="Current points balance available to spend",
    )
    rank: str = Field(
        default="bronze",
        description="User tier or ranking level",
    )
    available_rewards: list[RewardResponse] = Field(
        default_factory=list,
        description="Currently active and claimable rewards",
    )

    @model_validator(mode="before")
    @classmethod
    def _normalize_point_aliases(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "total_points_earned" not in data and "total_earned" in data:
                data["total_points_earned"] = data["total_earned"]
            if "points_available" not in data and "available_points" in data:
                data["points_available"] = data["available_points"]
        return data

    @computed_field
    @property
    def total_earned(self) -> int:
        """Alias for total_points_earned."""
        return self.total_points_earned

    @computed_field
    @property
    def available_points(self) -> int:
        """Alias for points_available."""
        return self.points_available


# ---------------------------------------------------------------------------
# Gamification Events
# ---------------------------------------------------------------------------


class GamificationEventResponse(BaseModel):
    """Recorded gamification point award event."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    rule_id: uuid.UUID
    points_earned: int
    event_data: dict[str, Any] | None = None
    created_at: datetime
    rule_name: str | None = None


class GamificationEventListResponse(BaseModel):
    """Paginated list of user gamification events."""

    items: list[GamificationEventResponse]
    total: int


class AwardPointsRequest(BaseModel):
    """Request payload to manually trigger or test gamification point awards."""

    event_type: str = Field(..., min_length=1, max_length=100)
    event_data: dict[str, Any] | None = None


class AwardPointsResponse(BaseModel):
    """Result of evaluating and awarding points for an event."""

    points_awarded: int
    events: list[GamificationEventResponse]
