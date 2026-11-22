# ADR-001: FastAPI as the Web Framework

**Date:** 2026-09-09

**Status:** Accepted

## Context

We need a Python web framework for building a production-grade e-commerce platform that serves an Iranian market. The framework must support asynchronous request handling, have strong type safety guarantees, produce automatic API documentation, and deliver high throughput under concurrent load. Key candidates evaluated were Django REST Framework, Flask, and FastAPI.

Django REST Framework offers a mature ecosystem with built-in ORM, admin panel, and authentication. However, its synchronous-first architecture introduces performance bottlenecks under high concurrency, and its serializer layer adds verbosity without leveraging Python's native type system.

Flask is lightweight and flexible but lacks built-in support for async, data validation, and API documentation generation. Building these capabilities requires assembling numerous third-party packages, increasing maintenance burden.

FastAPI is built on top of Starlette and Pydantic, providing native async support, automatic request/response validation via Python type hints, and OpenAPI documentation generation out of the box.

## Decision

We will use **FastAPI** as the web framework for all HTTP-facing services in the platform.

### Rationale

1. **Asynchronous by default.** FastAPI is built on ASGI (Starlette), enabling native `async`/`await` support. This is critical for I/O-bound workloads such as database queries, Elasticsearch calls, payment gateway interactions, and S3 storage operations — all of which are central to our platform.

2. **Type safety and validation.** Pydantic models enforce strict request and response schemas at runtime. Combined with Python type hints, this catches data contract violations early, reduces boilerplate, and integrates well with static analysis tools like mypy.

3. **Automatic OpenAPI documentation.** FastAPI generates interactive Swagger UI and ReDoc documentation from code with zero additional effort. This is essential for frontend team collaboration and third-party integrations.

4. **Performance.** Benchmarks consistently place FastAPI among the fastest Python web frameworks, comparable to Node.js and Go for I/O-bound workloads. Under ASGI with Uvicorn, it handles significantly more concurrent requests than WSGI-based alternatives.

5. **Dependency injection system.** FastAPI's built-in `Depends()` mechanism provides a clean pattern for managing database sessions, authentication, authorization, and shared services without global state.

6. **Ecosystem compatibility.** FastAPI works seamlessly with SQLAlchemy (async), Celery, Redis, and the broader Python ecosystem. It does not impose an opinionated ORM or project structure, giving us full architectural control.

## Consequences

### Positive

- High throughput for concurrent I/O-bound operations without thread pool overhead.
- Self-documenting APIs reduce drift between implementation and documentation.
- Pydantic validation eliminates an entire class of data integrity bugs at the API boundary.
- Python type hints improve IDE support, refactoring safety, and code readability.
- The dependency injection system promotes testable, loosely coupled code.

### Negative

- No built-in ORM or admin panel; we must integrate SQLAlchemy and build admin tooling separately.
- The async ecosystem in Python is less mature than synchronous alternatives. Some libraries may require sync-to-async bridges.
- Developers unfamiliar with async Python will face a learning curve around event loop semantics, connection pooling, and avoiding blocking calls.
- FastAPI is younger than Django and Flask. While adoption is growing rapidly, certain edge cases may have less community coverage.

### Mitigations

- SQLAlchemy 2.0 with async support is mature and well-documented; we adopt it as the ORM layer.
- We establish coding guidelines that identify common async pitfalls (blocking calls in async contexts, connection leaks) and enforce them through code review and linting.
- We use `asyncio`-native libraries wherever possible (httpx, asyncpg, aioredis) to avoid sync bridges.
