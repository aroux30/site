"""Capability-registry vocabulary.

The registry describes *locally provable configuration facts* only. These
enums are deliberately small and stable:

- ``CapabilityStatus`` answers "how far can we trust this capability?".
- ``CapabilityReason`` answers "why is it in that state?".

Both are closed sets so that API consumers (and the admin UI) can switch on
them exhaustively, and neither ever carries a credential, merchant id, token,
host name, or any other secret-bearing value. Nothing here probes an external
provider: a status is derived from configuration, never from runtime health.
"""

from __future__ import annotations

import enum


class CapabilityCategory(str, enum.Enum):
    """Bounded set of integration categories the registry reports."""

    PAYMENT = "payment"
    SHIPPING = "shipping"
    MESSAGING = "messaging"
    SEARCH = "search"
    STORAGE = "storage"
    IDENTITY = "identity"


class CapabilityStatus(str, enum.Enum):
    """Conservative readiness of a capability.

    ``LIVE`` is reserved for capabilities that are *fully local* and therefore
    provably operational without contacting anything external. A capability
    that depends on an external provider whose runtime health has not been
    verified must never be ``LIVE`` — ``BETA`` or ``DEGRADED`` is used
    instead, with a reason code explaining why.
    """

    LIVE = "LIVE"
    BETA = "BETA"
    MOCK = "MOCK"
    DISABLED = "DISABLED"
    DEGRADED = "DEGRADED"
    # Reserved for operator-declared maintenance. No local configuration
    # source currently produces this state, so the registry never emits it in
    # this release; it is part of the contract so consumers can render it
    # without a schema change once a declaration surface exists.
    MAINTENANCE = "MAINTENANCE"


class CapabilityReason(str, enum.Enum):
    """Stable, non-secret explanation of a capability's operational caveat."""

    # No caveat.
    NONE = "none"
    # Required local credential/identifier absent.
    NOT_CONFIGURED = "not_configured"
    # Deliberately turned off by configuration even though it could run.
    FEATURE_DISABLED = "feature_disabled"
    # Operational, but every transaction requires an operator decision.
    MANUAL_APPROVAL = "manual_approval"
    # Configured, but nothing has verified the external provider is reachable.
    UNVERIFIED_RUNTIME_HEALTH = "unverified_runtime_health"
    # Configured, but pointed at a provider sandbox rather than live money.
    SANDBOX_MODE = "sandbox_mode"
    # The provider itself is a simulation, not a real gateway.
    SIMULATION_PROVIDER = "simulation_provider"
    # Delivery is acknowledged by an in-process stub instead of being sent.
    SIMULATED_DELIVERY = "simulated_delivery"
    # The callback/inbound path cannot be authenticated without another secret.
    WEBHOOK_VERIFICATION_UNCONFIGURED = "webhook_verification_unconfigured"
    # Hard-blocked by the environment (never offered here).
    PRODUCTION_RESTRICTED = "production_restricted"
