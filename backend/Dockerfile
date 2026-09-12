# ==============================================================================
# Multi-stage Dockerfile for Iranian E-Commerce Backend
# ==============================================================================
# Build:   docker build -t ecommerce-backend .
# Run:     docker run -p 8000:8000 --env-file .env ecommerce-backend
# ==============================================================================

# ── Stage 1: Builder ─────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Install build dependencies (needed for argon2-cffi, asyncpg, Pillow)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only dependency files first for better layer caching
COPY pyproject.toml README.md ./
COPY app/__init__.py app/__init__.py

# Install dependencies into a virtual env
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Production dependencies only — dev/test tooling (pytest, ruff, ...)
# must never ship in the runtime image.
RUN pip install --upgrade pip setuptools wheel && \
    pip install "."

# ── Stage 2: Runtime ─────────────────────────────────────────────────────
FROM python:3.12-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

# Runtime system libraries
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    libjpeg62-turbo \
    zlib1g \
    libwebp7 \
    curl \
    tini \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 1000 appuser \
    && useradd --uid 1000 --gid appuser --shell /bin/bash --create-home appuser

# Copy the virtual env from builder
COPY --from=builder /opt/venv /opt/venv

# Copy application code
WORKDIR /app
COPY . .

# Ensure Unix line endings (in case git auto-converted to CRLF on Windows)
RUN sed -i 's/\r$//' scripts/*.sh && chmod +x scripts/*.sh

# Switch to non-root user
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Use tini as PID 1 for proper signal handling
ENTRYPOINT ["tini", "--"]
CMD ["scripts/start.sh"]
