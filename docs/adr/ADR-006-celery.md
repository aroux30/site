# ADR-006: Celery for Background Task Processing

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform requires asynchronous processing for operations that should not block HTTP request/response cycles:

- **Email and SMS notifications.** Sending order confirmations, OTP codes, and marketing emails must not delay API responses.
- **Payment verification.** Polling payment gateways for transaction status after user redirect requires background polling with timeout handling.
- **Image processing.** Resizing, compressing, and generating thumbnails for product images is CPU-intensive and should not occupy web worker processes.
- **Report generation.** Sales reports, inventory summaries, and analytics exports are long-running queries that must execute outside the request cycle.
- **Scheduled tasks.** Periodic jobs such as clearing expired sessions, syncing search indices, and generating sitemaps require a scheduling mechanism.

Candidates evaluated included Celery, Dramatiq, ARQ, and raw `asyncio` background tasks.

ARQ is async-native but has a smaller ecosystem and less mature retry/scheduling support. Dramatiq is simpler than Celery but lacks built-in scheduling (requires APScheduler integration). Raw `asyncio.create_task()` provides no persistence, retry logic, or scheduling.

## Decision

We will use **Celery** with Redis as the message broker for all background task processing and periodic scheduling.

### Rationale

1. **Mature task queue.** Celery is the most established Python task queue, with over a decade of production use, extensive documentation, and a large community. Edge cases around task serialization, worker management, and failure handling are well-documented.

2. **Retry and error handling.** Celery provides built-in retry mechanisms with configurable backoff strategies, max retry limits, and dead-letter handling. This is essential for unreliable external integrations like payment gateways and SMS providers.

3. **Celery Beat scheduler.** The built-in periodic task scheduler eliminates the need for external cron jobs or separate scheduling services. Schedules can be defined in code and version-controlled.

4. **Task routing and priority.** Tasks can be routed to specific queues, allowing separation of fast tasks (notifications) from slow tasks (report generation) with dedicated worker pools for each.

5. **Monitoring and observability.** Flower provides a real-time web dashboard for task monitoring. Celery emits events that integrate with standard monitoring tools for tracking task throughput, failure rates, and queue depth.

6. **Redis broker integration.** Using Redis (ADR-005) as the Celery broker avoids introducing a separate message queue service (e.g., RabbitMQ), reducing infrastructure complexity.

## Consequences

### Positive

- HTTP responses are fast because expensive operations are offloaded to background workers.
- Built-in retry with exponential backoff handles transient failures in external services gracefully.
- Periodic tasks are managed in code, version-controlled, and deployable alongside the application.
- Task routing allows resource isolation between different workload types.
- Flower dashboard provides operational visibility into task processing.

### Negative

- Celery adds operational complexity: worker processes must be deployed, monitored, and scaled independently of web workers.
- Celery's configuration surface is large and can be confusing. Default settings are not always production-appropriate.
- Celery workers are synchronous by default. Running async code in Celery tasks requires bridging between sync and async contexts.
- Task serialization (pickling) can introduce security concerns and compatibility issues across deployments.

### Mitigations

- We use JSON serialization instead of pickle for all tasks, eliminating deserialization security risks and ensuring cross-version compatibility.
- We establish a standard Celery configuration template with production-appropriate defaults (prefetch multiplier, acknowledgment settings, result expiration).
- We define separate queues for different task priorities (e.g., `notifications`, `payments`, `reports`) with dedicated worker pools.
- For async operations within Celery tasks, we use `asgiref.sync.async_to_sync` or run a dedicated event loop within the task when necessary.
- We configure health checks for worker processes and alerting for queue depth thresholds.
