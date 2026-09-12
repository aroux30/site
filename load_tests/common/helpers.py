"""Helper utilities for realistic user simulation and assertions."""

import secrets
import uuid
from typing import Any
from locust.clients import ResponseContextManager

from load_tests.common.config import PERSIAN_SEARCH_QUERIES, SAMPLE_PROVINCES


def generate_session_id() -> str:
    """Generate a UUID session id for guest cart and tracking."""
    return str(uuid.uuid4())


def get_random_search_query() -> str:
    """Return a randomly chosen Persian search query with ZWNJ."""
    return secrets.choice(PERSIAN_SEARCH_QUERIES)


def get_random_province() -> str:
    """Return a random Iranian province."""
    return secrets.choice(SAMPLE_PROVINCES)


def check_fastapi_response(
    response: ResponseContextManager,
    expected_status: int = 200,
    name: str = "API Request",
) -> dict[str, Any] | None:
    """Validate status code and JSON payload integrity, recording Locust failure if invalid."""
    if response.status_code != expected_status:
        response.failure(f"[{name}] Expected HTTP {expected_status}, got {response.status_code}: {response.text[:200]}")
        return None
    try:
        data = response.json()
        return data
    except Exception as exc:
        response.failure(f"[{name}] Invalid JSON response: {exc} | Raw: {response.text[:100]}")
        return None
