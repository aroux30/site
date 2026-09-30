"""Approval policy matching and chain materialisation.

A policy answers one question: *given a request's resource and amount, how
many signatures does it need, and from whom?* Policies are data rows, so the
matching rule is the only thing code has to get right, and it is pure — the
same inputs always produce the same chain, which is what makes it testable
and auditable.

Matching order (most specific wins):

1. Exact ``resource`` match beats the wildcard ``"*"``.
2. Among matching rules, the highest ``priority`` wins.
3. Among equal priority, the highest ``min_amount_rial`` that is ``<=`` the
   amount wins — i.e. the tightest band containing the amount.

A request whose amount matches no active policy gets an empty chain: one
implicit step, the v1 behaviour. Adding policies can only ever *add*
signatures, never silently remove the single-reviewer path.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import structlog
from sqlalchemy import select

from app.modules.approvals.domain.models import (
    ApprovalPolicy,
    ApprovalRequest,
    ApprovalStep,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

#: Wildcard resource — a policy that applies to every resource.
WILDCARD = "*"


def _amount_of(payload: dict[str, Any] | None) -> int | None:
    """Extract the Rial amount a policy decision is about, if any.

    Read from the request payload (``amount`` is the platform-wide key for
    integer-Rial figures in approval payloads). Absent is not zero: a
    no-amount request matches only policies with no band.
    """
    if not payload:
        return None
    raw = payload.get("amount")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def policy_matches(policy: ApprovalPolicy, resource: str, amount: int | None) -> bool:
    """True when an active policy covers this (resource, amount).

    A policy with a lower band bound does not match a request with no amount:
    "refunds over 50M need finance" cannot be evaluated for an unknown figure,
    and silently applying it would demand a signature the rule never asked
    for. Amount-less requests therefore match only unbounded policies.
    """
    if policy.resource not in (resource, WILDCARD):
        return False
    if policy.min_amount_rial is not None:
        if amount is None or amount < policy.min_amount_rial:
            return False
    if policy.max_amount_rial is not None:
        if amount is None or amount >= policy.max_amount_rial:
            return False
    return True


def _rank(policy: ApprovalPolicy) -> tuple[int, int, int]:
    """Sort key: exact-resource first, then priority, then tightest band."""
    exact = 0 if policy.resource == WILDCARD else 1
    band = policy.min_amount_rial or 0
    return (exact, policy.priority, band)


def select_policy(
    policies: list[ApprovalPolicy],
    *,
    resource: str,
    amount: int | None,
) -> ApprovalPolicy | None:
    """Pick the winning policy from candidates, or None. Pure."""
    matching = [p for p in policies if p.is_active and policy_matches(p, resource, amount)]
    if not matching:
        return None
    return max(matching, key=_rank)


async def load_candidate_policies(db: AsyncSession, resource: str) -> list[ApprovalPolicy]:
    """Active policies for a resource (exact or wildcard)."""
    rows = (
        await db.execute(
            select(ApprovalPolicy).where(
                ApprovalPolicy.is_active.is_(True),
                ApprovalPolicy.resource.in_([resource, WILDCARD]),
            )
        )
    ).scalars().all()
    return list(rows)


def build_steps(step_defs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate and normalise a policy's step definitions.

    Each entry is ``{"role": str | None, "label": str | None}``. A malformed
    entry raises rather than producing a chain that cannot be satisfied — a
    policy that silently demanded an impossible signature would deadlock
    money. Returns insertable values for ``ApprovalStep``.
    """
    steps: list[dict[str, Any]] = []
    for index, entry in enumerate(step_defs or []):
        if not isinstance(entry, dict):
            raise ValueError(f"policy step {index} must be an object")
        role = entry.get("role")
        if role is not None and not isinstance(role, str):
            raise ValueError(f"policy step {index} role must be a string or null")
        label = entry.get("label")
        if label is not None and not isinstance(label, str):
            raise ValueError(f"policy step {index} label must be a string or null")
        steps.append({"step_order": index, "required_role": role, "label": label})
    return steps


async def materialise_steps(
    db: AsyncSession,
    request: ApprovalRequest,
) -> list[ApprovalStep]:
    """Attach the policy's chain to a request at submission time.

    The chain is frozen here on purpose: a policy edited while a request is
    in flight must not change the rules that request is judged by. Returns
    the created steps (empty when no policy applies — the single-step path).
    """
    resource = (request.resource or "").strip().lower()
    amount = _amount_of(request.data)

    policies = await load_candidate_policies(db, resource)
    policy = select_policy(policies, resource=resource, amount=amount)
    if policy is None:
        return []

    try:
        normalised = build_steps(policy.steps or [])
    except ValueError:
        # A broken policy must not block the request; fall back to the
        # single-step path and leave a loud trace for the operator.
        await logger.aerror(
            "approval_policy_invalid_steps",
            policy_id=str(policy.id),
            resource=resource,
        )
        return []

    if not normalised:
        return []

    steps = [
        ApprovalStep(
            request_id=request.id,
            step_order=entry["step_order"],
            required_role=entry["required_role"],
            label=entry["label"],
        )
        for entry in normalised
    ]
    db.add_all(steps)
    await logger.ainfo(
        "approval_chain_materialised",
        request_id=str(request.id),
        resource=resource,
        steps=len(steps),
        policy_id=str(policy.id),
    )
    return steps


# ── Default policy seeding ──────────────────────────────────────────────────

#: The three money-carrying flows the gap analysis called out, with the
#: thresholds an Iranian commerce operation would plausibly start from.
#: 50,000,000 Rial = 5,000,000 Toman; 200,000,000 Rial = 20,000,000 Toman.
DEFAULT_POLICIES: list[dict[str, Any]] = [
    {
        "resource": "refund",
        "min_amount_rial": 50_000_000,
        "max_amount_rial": None,
        "steps": [
            {"role": None, "label": "تایید کارشناس ارشد"},
            {"role": None, "label": "تایید مالی"},
        ],
        "priority": 0,
        "description": "بازپرداخت‌های بالای ۵ میلیون تومان نیازمند دو تایید",
    },
    {
        "resource": "wallet_withdrawal",
        "min_amount_rial": 20_000_000,
        "max_amount_rial": None,
        "steps": [
            {"role": None, "label": "تایید مالی"},
        ],
        "priority": 0,
        "description": "برداشت از کیف پول بالای ۲ میلیون تومان نیازمند تایید مالی",
    },
    {
        "resource": "vendor_settlement",
        "min_amount_rial": 100_000_000,
        "max_amount_rial": None,
        "steps": [
            {"role": None, "label": "تایید مالی"},
            {"role": None, "label": "تایید مدیر عملیات"},
        ],
        "priority": 0,
        "description": "تسویه فروشندگان بالای ۱۰ میلیون تومان نیازمند دو تایید",
    },
]


async def seed_default_policies(db: AsyncSession) -> int:
    """Insert the default money policies once. Idempotent by (resource, min)."""
    created = 0
    for spec in DEFAULT_POLICIES:
        existing = (
            await db.execute(
                select(ApprovalPolicy.id).where(
                    ApprovalPolicy.resource == spec["resource"],
                    ApprovalPolicy.min_amount_rial == spec["min_amount_rial"],
                )
            )
        ).first()
        if existing is not None:
            continue
        db.add(
            ApprovalPolicy(
                resource=spec["resource"],
                min_amount_rial=spec["min_amount_rial"],
                max_amount_rial=spec["max_amount_rial"],
                steps=spec["steps"],
                priority=spec["priority"],
                is_active=True,
                description=spec["description"],
            )
        )
        created += 1
    if created:
        await db.flush()
        await logger.ainfo("approval_policies_seeded", created=created)
    return created


def chain_summary(steps: list[ApprovalStep]) -> dict[str, int]:
    """Small counts helper for the admin UI. Pure."""
    summary = {"total": len(steps), "pending": 0, "approved": 0, "rejected": 0}
    for step in steps:
        summary[step.status.value] = summary.get(step.status.value, 0) + 1
    return summary
