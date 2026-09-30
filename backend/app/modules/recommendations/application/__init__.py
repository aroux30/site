"""Recommendations application package."""

from app.modules.recommendations.application.recommendation_service import (
    RecommendationService,
    get_frequently_bought_together,
    get_personalized_recommendations,
    get_similar_products,
    get_trending_products,
    recommendation_service,
)

__all__ = [
    "RecommendationService",
    "get_frequently_bought_together",
    "get_personalized_recommendations",
    "get_similar_products",
    "get_trending_products",
    "recommendation_service",
]
