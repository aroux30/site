# ADR-003: Modular Monolith Over Microservices

**Date:** 2026-09-09

**Status:** Accepted

## Context

The platform encompasses multiple business domains: product catalog, user management, orders, payments, inventory, search, notifications, and content management. A critical architectural decision is whether to deploy these as independent microservices or as a single deployable unit with clear internal module boundaries.

Microservices offer independent deployability, technology heterogeneity, and isolated scaling. However, they introduce significant complexity: distributed transactions, service discovery, inter-service communication latency, data consistency challenges, operational overhead of managing multiple deployments, and the need for a mature DevOps practice.

Our team is small, the product is in its early stages, and domain boundaries are still evolving. Premature decomposition into microservices risks creating tightly coupled distributed systems that are harder to change than a well-structured monolith.

## Decision

We will adopt a **modular monolith** architecture: a single deployable application with strictly enforced module boundaries that align with business domains.

### Rationale

1. **Reduced operational complexity.** A single deployment unit eliminates the need for service mesh, API gateways, distributed tracing across services, and container orchestration from day one. The team can focus on delivering business value rather than managing infrastructure.

2. **Transactional integrity.** Business operations that span multiple domains (e.g., placing an order that updates inventory and triggers payment) can leverage database transactions instead of implementing distributed saga patterns.

3. **Faster development velocity.** Refactoring across module boundaries is a code change, not a cross-service API migration. Domain boundaries can be adjusted as understanding of the business deepens without the cost of restructuring service APIs and data stores.

4. **Clear path to decomposition.** By enforcing module boundaries through Python package structure, explicit public APIs per module, and prohibited cross-module database access, individual modules can be extracted into independent services when — and only when — scaling or organizational needs justify it.

5. **Team size alignment.** Microservices work best with multiple autonomous teams. With a small team, the coordination overhead of microservices outweighs the benefits.

### Module Boundary Rules

- Each module exposes a public service interface; other modules interact only through this interface.
- Modules own their database tables exclusively. No module may directly query another module's tables.
- Cross-module communication within the monolith uses in-process function calls through the public interface or domain events.
- Shared kernel (common value objects, base classes) is kept minimal and explicitly managed.

## Consequences

### Positive

- Dramatically simpler deployment, monitoring, and debugging compared to microservices.
- ACID transactions across modules where business logic requires them.
- Faster iteration and refactoring during the critical early phase of the product.
- Lower infrastructure costs — one application server, one database, fewer moving parts.
- Modules can be extracted into services later if needed, with clear boundaries already in place.

### Negative

- All modules share a single process; a memory leak or crash in one module affects the entire application.
- Scaling is all-or-nothing at the application level (though see ADR-014 for horizontal scaling strategy).
- Discipline is required to maintain module boundaries. Without enforcement, the codebase risks devolving into a tangled monolith.
- Technology choices are uniform across all modules (Python/FastAPI), limiting the ability to use different languages or frameworks for specific domains.

### Mitigations

- We enforce module boundaries through linting rules, code review checklists, and architectural fitness functions (automated tests that verify no cross-module imports violate boundaries).
- We use domain events for loose coupling between modules, making future extraction straightforward.
- We implement health checks and resource limits to contain the blast radius of module-level failures.
- We document the extraction criteria: when a module should become a service (independent scaling needs, different deployment cadence, team ownership boundary).
