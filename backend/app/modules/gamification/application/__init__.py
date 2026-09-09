"""Gamification application services."""

from app.modules.gamification.application.gamification_service import (
    GamificationService,
    admin_create_reward,
    admin_create_rule,
    admin_list_rules,
    admin_update_reward,
    award_points_for_event,
    claim_reward,
    get_user_points,
    list_rewards,
)

__all__ = [
    "GamificationService",
    "admin_create_reward",
    "admin_create_rule",
    "admin_list_rules",
    "admin_update_reward",
    "award_points_for_event",
    "claim_reward",
    "get_user_points",
    "list_rewards",
]
