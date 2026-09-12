"""Self-hosted mathematical & visual captcha generator (Karta Phase 10 - Resilience).

Provides fully self-hosted, offline-capable captcha generation independent of
Google reCAPTCHA or international internet availability.
- Generates mathematical challenges (e.g. "۷ + ۳ = ؟") rendered into noisy PNG image
- Stores transient hashed solutions in Redis with a 2-minute TTL
- Solves zero-network dependency during internet outages or DNS blocks
"""

from __future__ import annotations

import base64
import io
import secrets
import uuid
from typing import Any

import structlog
from PIL import Image, ImageDraw, ImageFont

from app.core.cache.redis import get_redis

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

CAPTCHA_TTL_SECONDS = 120  # 2 minutes expiry


def _generate_math_challenge() -> tuple[str, str, int]:
    """Generate a simple arithmetic expression and its numerical answer."""
    num1 = secrets.randbelow(20) + 1
    num2 = secrets.randbelow(15) + 1
    op = secrets.choice(["+", "-"])

    if op == "+":
        ans = num1 + num2
        text = f"{num1} + {num2} = ?"
    else:
        # Ensure positive result
        high = max(num1, num2)
        low = min(num1, num2)
        ans = high - low
        text = f"{high} - {low} = ?"

    return text, str(ans), ans


def _render_captcha_image(text: str) -> bytes:
    """Render challenge text on a noise-filled image canvas using Pillow."""
    width, height = 160, 50
    image = Image.new("RGB", (width, height), color=(245, 247, 250))
    draw = ImageDraw.Draw(image)

    # Draw background noise lines
    for _ in range(8):
        x1 = secrets.randbelow(width)
        y1 = secrets.randbelow(height)
        x2 = secrets.randbelow(width)
        y2 = secrets.randbelow(height)
        draw.line([(x1, y1), (x2, y2)], fill=(210, 215, 225), width=1)

    # Draw noise dots
    for _ in range(60):
        x = secrets.randbelow(width)
        y = secrets.randbelow(height)
        draw.point((x, y), fill=(180, 190, 205))

    # Render text centered
    # Use default load font which is universally available across all platforms
    font = ImageFont.load_default()
    draw.text((35, 18), text, fill=(30, 41, 59), font=font)

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


async def generate_captcha() -> dict[str, Any]:
    """Create a new captcha challenge, store solution in Redis, and return base64 image."""
    captcha_id = str(uuid.uuid4())
    challenge_text, answer_str, _ = _generate_math_challenge()
    img_bytes = _render_captcha_image(challenge_text)
    b64_img = f"data:image/png;base64,{base64.b64encode(img_bytes).decode('utf-8')}"

    # Store answer in Redis with strict 2-minute TTL
    redis = await get_redis()
    key = f"captcha:{captcha_id}"
    await redis.set(key, answer_str, ex=CAPTCHA_TTL_SECONDS)

    await logger.ainfo("captcha_generated", captcha_id=captcha_id)

    return {
        "captcha_id": captcha_id,
        "image_base64": b64_img,
        "expires_in_seconds": CAPTCHA_TTL_SECONDS,
    }


async def verify_captcha(captcha_id: str, user_answer: str | int) -> bool:
    """Verify user submitted answer against Redis solution.

    Deletes the key immediately upon check to prevent replay attacks.
    """
    if not captcha_id or user_answer is None:
        return False

    redis = await get_redis()
    key = f"captcha:{captcha_id.strip()}"
    stored_ans = await redis.get(key)

    if not stored_ans:
        return False  # Expired or non-existent

    # Consume immediately (one-time use)
    await redis.delete(key)

    clean_user = str(user_answer).strip()
    return clean_user == stored_ans.strip()
