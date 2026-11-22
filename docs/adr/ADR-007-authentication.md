# ADR-007: Authentication and Session Security Strategy

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform requires a robust authentication system that supports multiple client types (web browser, potential future mobile app), protects against common attack vectors (XSS, CSRF, token theft, brute force), and provides a smooth user experience for the Iranian market where phone-based verification is standard.

Key requirements:

- Stateless authentication that scales horizontally with the modular monolith (ADR-003).
- Protection against cross-site scripting (XSS) token theft.
- Graceful token expiration without forcing frequent re-authentication.
- Phone-based OTP verification as a primary or secondary authentication factor.
- Password hashing that resists GPU-based and ASIC-based brute force attacks.

## Decision

We will implement authentication using **JWT access tokens with refresh token rotation**, stored in **HttpOnly cookies**, with **OTP-based verification** and **Argon2id** for password hashing.

### Components

#### 1. JWT Access Tokens
- Short-lived (15 minutes) signed tokens containing user ID, roles, and permissions.
- Used for stateless request authentication on every API call.
- Signed with RS256 (asymmetric) to allow token verification without exposing the signing key.

#### 2. Refresh Token Rotation
- Long-lived refresh tokens (7 days) stored in the database, issued alongside access tokens.
- When a client uses a refresh token to obtain a new access token, the old refresh token is invalidated and a new one is issued (rotation).
- If a previously used refresh token is presented, all refresh tokens for that user are invalidated (replay detection), forcing re-authentication.

#### 3. HttpOnly Cookies
- Both access and refresh tokens are delivered via `HttpOnly`, `Secure`, `SameSite=Lax` cookies.
- `HttpOnly` prevents JavaScript access, mitigating XSS-based token theft.
- `Secure` ensures cookies are only sent over HTTPS.
- `SameSite=Lax` provides baseline CSRF protection while allowing top-level navigations.

#### 4. OTP Verification
- One-time passwords sent via SMS for phone number verification and as a secondary authentication factor.
- OTP codes are stored in Redis (ADR-005) with a 2-minute TTL and are single-use.
- Rate limiting (via Redis) prevents OTP brute force attempts: maximum 5 attempts per code, maximum 3 OTP requests per phone number per 10-minute window.

#### 5. Argon2id Password Hashing
- Argon2id is the winner of the Password Hashing Competition and is resistant to both GPU and side-channel attacks.
- Parameters are tuned to require approximately 250ms per hash on production hardware, balancing security with user experience.
- Parameters: memory cost 64 MiB, time cost 3 iterations, parallelism 4.

## Consequences

### Positive

- Stateless JWT authentication scales horizontally without shared session state.
- Refresh token rotation limits the window of exposure if a refresh token is compromised.
- HttpOnly cookies eliminate the most common XSS-based token theft vector compared to localStorage.
- OTP provides a familiar authentication experience for Iranian users accustomed to phone-based verification.
- Argon2id provides the strongest available protection against offline password cracking.
- Replay detection (reuse of rotated refresh tokens) provides an early warning of token compromise.

### Negative

- JWT tokens cannot be individually revoked before expiration without maintaining a server-side blocklist, which partially negates the stateless benefit.
- HttpOnly cookies require careful CORS and cookie domain configuration, especially during development with different frontend/backend origins.
- OTP delivery depends on SMS provider reliability, which can be variable in the Iranian market.
- Argon2id's memory-hard computation increases server CPU and memory usage during login spikes.
- Refresh token rotation adds database writes on every token refresh.

### Mitigations

- We maintain a Redis-based token blocklist for critical operations (password change, account compromise), checking only high-risk endpoints to minimize performance impact.
- We document cookie configuration for all environments (local dev, staging, production) and provide a development proxy setup to avoid cross-origin cookie issues.
- We implement OTP delivery through multiple SMS providers with automatic failover.
- We use connection pooling and rate limiting at the login endpoint to bound the server load from Argon2id computation.
- Refresh token database writes are lightweight (single row upsert) and the table is indexed on user ID and token hash.
