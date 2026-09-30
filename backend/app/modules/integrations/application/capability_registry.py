"""Builds the integration capability registry from local configuration.

Design boundaries, in order of importance:

1. **No probing, no money, no selection.** This module reads the settings
   object and nothing else. It never opens a socket, never calls a provider,
   never touches a database, and never influences which gateway handles a
   payment. Every value it reports is a statement about *local configuration*,
   so it can never be the authority for a financial decision.
2. **Conservative statuses.** ``LIVE`` is withheld from anything that depends
   on an external provider, because configuration presence is not evidence of
   runtime health. Those capabilities are reported ``BETA`` (or ``DEGRADED``
   where a specific impairment is provable from configuration) with a reason
   code. Only fully local capabilities — the wallet, internal shipping rates,
   local disk storage — may be ``LIVE``.
3. **Secret-free by construction.** Records contain no credential, merchant
   id, token, host name, endpoint URL, stack trace, or environment value. The
   builder only ever *tests* configured values for emptiness; it never copies
   them into a record.

The status rules are written as one small function per capability so each
rule can be read, and tested, on its own.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from app.core.config.settings import Settings
from app.modules.integrations.domain.capability import (
    CapabilityRecord,
    is_available_to_customers,
)
from app.modules.integrations.domain.status import (
    CapabilityCategory,
    CapabilityReason,
    CapabilityStatus,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Rationale per capability is recorded at each rule below. The contract already
# publishes a machine-readable "why" for every record through ``reason_code``,
# so no separate note field is exposed: the stable code is the explanation.


def _configured(value: str | None) -> bool:
    """Whether a configuration value is present and non-blank.

    The value itself is never returned, logged, or stored — only this verdict.
    """
    return bool((value or "").strip())


def _record(
    *,
    capability_id: str,
    category: CapabilityCategory,
    display_name: str,
    status: CapabilityStatus,
    configured: bool,
    customer_visible: bool,
    reason_code: CapabilityReason,
    updated_at: datetime,
) -> CapabilityRecord:
    """Assemble a record, deriving the availability flag from the other fields."""
    return CapabilityRecord(
        id=capability_id,
        category=category,
        display_name=display_name,
        status=status,
        configured=configured,
        customer_visible=customer_visible,
        available_to_customers=is_available_to_customers(
            status=status, configured=configured, customer_visible=customer_visible
        ),
        reason_code=reason_code,
        updated_at=updated_at,
    )


def _gateway_is_offered(settings: Settings, provider_name: str) -> bool:
    """Whether the deployment offers this gateway to buyers.

    This mirrors the predicate the payment module itself uses to decide
    ``is_enabled`` on the buyer-facing method list: the provider is either the
    one this deployment routes through, or the environment is development
    where every gateway is offered for testing. Mirroring the existing rule
    rather than inventing a parallel one is what keeps the registry from
    disagreeing with the authority it describes.
    """
    return (
        provider_name == settings.PAYMENT_PROVIDER
        or settings.ENVIRONMENT == "development"
    )


def _external_status(
    *,
    configured: bool,
    sandbox: bool,
    updated_at: datetime,
    capability_id: str,
    category: CapabilityCategory,
    display_name: str,
    customer_visible: bool,
    enabled: bool = True,
) -> CapabilityRecord:
    """Status rule shared by externally-hosted gateways.

    An external provider can never be reported ``LIVE``: nothing in this
    process has verified that the remote side answers. Sandbox mode is called
    out ahead of the generic caveat because it is the more specific fact.

    ``enabled`` is the offering fact: a gateway that is configured but not
    offered is switched off, not merely unverified, so it is reported
    ``DISABLED`` with ``feature_disabled`` rather than implying a buyer could
    select it. Configuration absence is checked first, because "has no
    credential" is the more fundamental reason.
    """
    if not configured:
        status, reason = CapabilityStatus.DISABLED, CapabilityReason.NOT_CONFIGURED
    elif not enabled:
        status, reason = CapabilityStatus.DISABLED, CapabilityReason.FEATURE_DISABLED
    elif sandbox:
        status, reason = CapabilityStatus.BETA, CapabilityReason.SANDBOX_MODE
    else:
        status, reason = (
            CapabilityStatus.BETA,
            CapabilityReason.UNVERIFIED_RUNTIME_HEALTH,
        )
    return _record(
        capability_id=capability_id,
        category=category,
        display_name=display_name,
        status=status,
        configured=configured,
        customer_visible=customer_visible,
        reason_code=reason,
        updated_at=updated_at,
    )


# ── Payments ──────────────────────────────────────────────────────────────


def _payment_capabilities(
    settings: Settings, *, zarinpal_merchant_id_configured: bool, now: datetime
) -> list[CapabilityRecord]:
    records: list[CapabilityRecord] = []

    # Zarinpal: configured when an id arrives from either the deployment
    # environment or the runtime admin override. Both are provisioned out of
    # band, so presence is checkable but health is not. A stored merchant id
    # also switches gateway routing to Zarinpal, so it counts as offered even
    # when the environment names a different provider.
    records.append(
        _external_status(
            configured=_configured(settings.PAYMENT_MERCHANT_ID)
            or zarinpal_merchant_id_configured,
            enabled=(
                _gateway_is_offered(settings, "zarinpal")
                or zarinpal_merchant_id_configured
            ),
            sandbox=bool(settings.PAYMENT_SANDBOX),
            updated_at=now,
            capability_id="payment.zarinpal",
            category=CapabilityCategory.PAYMENT,
            display_name="Zarinpal",
            customer_visible=True,
        )
    )

    # IDPay has no credential field of its own — it reuses the shared gateway
    # identifier. Claiming it is configured whenever *that* value is present
    # would misreport the Zarinpal merchant id as an IDPay credential, so the
    # provider selection is required as well.
    idpay_selected = settings.PAYMENT_PROVIDER == "idpay"
    records.append(
        _external_status(
            configured=idpay_selected and _configured(settings.PAYMENT_MERCHANT_ID),
            enabled=_gateway_is_offered(settings, "idpay"),
            sandbox=bool(settings.PAYMENT_SANDBOX),
            updated_at=now,
            capability_id="payment.idpay",
            category=CapabilityCategory.PAYMENT,
            display_name="IDPay",
            customer_visible=True,
        )
    )

    # Crypto: three distinct configuration facts, so it gets its own rule.
    # A missing webhook secret does not stop payment *creation*, but it does
    # disable authenticated confirmation — a provable impairment, hence
    # DEGRADED rather than a generic health caveat.
    crypto_configured = _configured(settings.NOWPAYMENTS_API_KEY)
    if not crypto_configured:
        crypto_status = CapabilityStatus.DISABLED
        crypto_reason = CapabilityReason.NOT_CONFIGURED
    elif settings.NOWPAYMENTS_SANDBOX:
        crypto_status = CapabilityStatus.BETA
        crypto_reason = CapabilityReason.SANDBOX_MODE
    elif not _configured(settings.NOWPAYMENTS_IPN_SECRET):
        crypto_status = CapabilityStatus.DEGRADED
        crypto_reason = CapabilityReason.WEBHOOK_VERIFICATION_UNCONFIGURED
    else:
        crypto_status = CapabilityStatus.BETA
        crypto_reason = CapabilityReason.UNVERIFIED_RUNTIME_HEALTH
    records.append(
        _record(
            capability_id="payment.crypto",
            category=CapabilityCategory.PAYMENT,
            display_name="NowPayments (crypto)",
            status=crypto_status,
            configured=crypto_configured,
            customer_visible=True,
            reason_code=crypto_reason,
            updated_at=now,
        )
    )

    # Card-to-card is local end to end: the customer transfers out of band and
    # submits a receipt. Nothing external is called, so it can be LIVE — but a
    # human approves every settlement, which is the caveat the reason carries.
    card_configured = _configured(settings.CARD_TO_CARD_NUMBER)
    records.append(
        _record(
            capability_id="payment.card_transfer",
            category=CapabilityCategory.PAYMENT,
            display_name="Card-to-card transfer",
            status=(
                CapabilityStatus.LIVE if card_configured else CapabilityStatus.DISABLED
            ),
            configured=card_configured,
            customer_visible=True,
            reason_code=(
                CapabilityReason.MANUAL_APPROVAL
                if card_configured
                else CapabilityReason.NOT_CONFIGURED
            ),
            updated_at=now,
        )
    )

    # Wallet: internal balance, no provider, no credential. Provably LIVE.
    records.append(
        _record(
            capability_id="payment.wallet",
            category=CapabilityCategory.PAYMENT,
            display_name="Wallet balance",
            status=CapabilityStatus.LIVE,
            configured=True,
            customer_visible=True,
            reason_code=CapabilityReason.NONE,
            updated_at=now,
        )
    )

    # Mock gateway: the settings validator refuses to boot production with it,
    # so in production it is reported as hard-blocked rather than simulated.
    mock_in_production = settings.ENVIRONMENT == "production"
    records.append(
        _record(
            capability_id="payment.mock",
            category=CapabilityCategory.PAYMENT,
            display_name="Simulation gateway (development only)",
            status=(
                CapabilityStatus.DISABLED
                if mock_in_production
                else CapabilityStatus.MOCK
            ),
            configured=True,
            customer_visible=not mock_in_production,
            reason_code=(
                CapabilityReason.PRODUCTION_RESTRICTED
                if mock_in_production
                else CapabilityReason.SIMULATION_PROVIDER
            ),
            updated_at=now,
        )
    )
    return records


# ─ Shipping ──────────────────────────────────────────────────────────────


def _shipping_capabilities(settings: Settings, now: datetime) -> list[CapabilityRecord]:
    records = [
        _record(
            capability_id="shipping.internal",
            category=CapabilityCategory.SHIPPING,
            display_name="In-house delivery",
            status=CapabilityStatus.LIVE,
            configured=True,
            customer_visible=True,
            reason_code=CapabilityReason.NONE,
            updated_at=now,
        )
    ]

    # The carrier adapters accept credentials as constructor arguments, but no
    # carrier credential is declared in the settings surface, and the shipping
    # service builds them without any. There is therefore no local
    # configuration that could make these dispatch-capable, and in production
    # they raise rather than silently fake a shipment. Reporting them as
    # unconfigured is the honest, conservative read.
    for capability_id, display_name in (
        ("shipping.tipax", "Tipax courier"),
        ("shipping.post_iran", "Iran Post (express)"),
    ):
        records.append(
            _record(
                capability_id=capability_id,
                category=CapabilityCategory.SHIPPING,
                display_name=display_name,
                status=CapabilityStatus.DISABLED,
                configured=False,
                customer_visible=False,
                reason_code=CapabilityReason.NOT_CONFIGURED,
                updated_at=now,
            )
        )
    return records


# ─ Messaging ─────────────────────────────────────────────────────────────


def _messaging_capabilities(
    settings: Settings, now: datetime
) -> list[CapabilityRecord]:
    records: list[CapabilityRecord] = []

    # Kavenegar is the only sender that actually checks a credential; without
    # the key it declines and the dispatch falls through to the next provider.
    records.append(
        _external_status(
            configured=_configured(settings.SMS_API_KEY),
            sandbox=False,
            updated_at=now,
            capability_id="messaging.sms_kavenegar",
            category=CapabilityCategory.MESSAGING,
            display_name="Kavenegar SMS",
            customer_visible=False,
        )
    )

    # The two failover senders acknowledge in-process without contacting the
    # operator, so their success result is simulated. Reporting them as
    # unconfigured would understate the risk; they are reachable and they
    # report success, which is precisely what makes them worth flagging.
    for capability_id, display_name in (
        ("messaging.sms_ippanel", "IPPanel / FarazSMS"),
        ("messaging.sms_smsir", "SMS.ir"),
    ):
        records.append(
            _record(
                capability_id=capability_id,
                category=CapabilityCategory.MESSAGING,
                display_name=display_name,
                status=CapabilityStatus.MOCK,
                configured=True,
                customer_visible=False,
                reason_code=CapabilityReason.SIMULATED_DELIVERY,
                updated_at=now,
            )
        )

    # Last-resort acknowledgement when every real provider declines.
    sms_mock_in_production = settings.ENVIRONMENT == "production"
    records.append(
        _record(
            capability_id="messaging.sms_simulation",
            category=CapabilityCategory.MESSAGING,
            display_name="Internal SMS acknowledgement (development only)",
            status=(
                CapabilityStatus.DISABLED
                if sms_mock_in_production
                else CapabilityStatus.MOCK
            ),
            configured=True,
            customer_visible=False,
            reason_code=(
                CapabilityReason.PRODUCTION_RESTRICTED
                if sms_mock_in_production
                else CapabilityReason.SIMULATION_PROVIDER
            ),
            updated_at=now,
        )
    )

    # SMTP email: real transport when host + sender are configured (still
    # never LIVE — runtime health is unverified). Unconfigured means the
    # service falls back to log-only simulation, so the record distinguishes
    # "off" from "pointed somewhere we have not probed".
    smtp_configured = _configured(settings.SMTP_HOST) and _configured(
        settings.SMTP_FROM_ADDRESS
    )
    records.append(
        _external_status(
            configured=smtp_configured,
            sandbox=False,
            updated_at=now,
            capability_id="messaging.email_smtp",
            category=CapabilityCategory.MESSAGING,
            display_name="SMTP email delivery",
            customer_visible=False,
        )
    )
    if not smtp_configured:
        # Mirror of the sms_simulation record: without SMTP settings every
        # email is acknowledged in-process and nothing leaves the platform.
        records.append(
            _record(
                capability_id="messaging.email_simulation",
                category=CapabilityCategory.MESSAGING,
                display_name="Internal email acknowledgement (SMTP not configured)",
                status=CapabilityStatus.MOCK,
                configured=True,
                customer_visible=False,
                reason_code=CapabilityReason.SIMULATED_DELIVERY,
                updated_at=now,
            )
        )

    # Telegram Bot API: real transport when a bot token is configured (still
    # never LIVE — runtime health is unverified). Unconfigured means the
    # service falls back to log-only simulation, so the record distinguishes
    # "off" from "pointed somewhere we have not probed".
    telegram_configured = _configured(settings.TELEGRAM_BOT_TOKEN)
    records.append(
        _external_status(
            configured=telegram_configured,
            sandbox=False,
            updated_at=now,
            capability_id="messaging.telegram_bot",
            category=CapabilityCategory.MESSAGING,
            display_name="Telegram bot delivery",
            customer_visible=False,
        )
    )
    if not telegram_configured:
        records.append(
            _record(
                capability_id="messaging.telegram_simulation",
                category=CapabilityCategory.MESSAGING,
                display_name="Internal Telegram acknowledgement (bot token not configured)",
                status=CapabilityStatus.MOCK,
                configured=True,
                customer_visible=False,
                reason_code=CapabilityReason.SIMULATED_DELIVERY,
                updated_at=now,
            )
        )

    # Web push (VAPID): real dispatch additionally needs the pywebpush
    # package, which is currently NOT installed (documented dependency gap
    # in notifications/application/push_service.py). Report the channel as
    # MOCK whenever a real send is impossible so the registry never
    # overstates the integration.
    push_keys_configured = _configured(settings.VAPID_PUBLIC_KEY) and _configured(
        settings.VAPID_PRIVATE_KEY
    )
    from app.modules.notifications.application.push_service import PYWEBPUSH_AVAILABLE

    webpush_real = push_keys_configured and PYWEBPUSH_AVAILABLE
    records.append(
        _record(
            capability_id="messaging.webpush_vapid",
            category=CapabilityCategory.MESSAGING,
            display_name="Web push (VAPID)",
            status=(
                CapabilityStatus.BETA
                if webpush_real
                else CapabilityStatus.MOCK
            ),
            configured=push_keys_configured,
            customer_visible=False,
            reason_code=(
                CapabilityReason.UNVERIFIED_RUNTIME_HEALTH
                if webpush_real
                else (
                    CapabilityReason.NOT_CONFIGURED
                    if not push_keys_configured
                    else CapabilityReason.SIMULATED_DELIVERY
                )
            ),
            updated_at=now,
        )
    )
    return records


# ── Search, storage, identity ─────────────────────────────────────────────


def _platform_capabilities(settings: Settings, now: datetime) -> list[CapabilityRecord]:
    return [
        # Declared unconditionally (the URL has a default), reachable health
        # unverified: a cluster outage currently degrades search to an empty
        # result set rather than an error, so the caveat matters.
        _external_status(
            configured=True,
            sandbox=False,
            updated_at=now,
            capability_id="search.elasticsearch",
            category=CapabilityCategory.SEARCH,
            display_name="Product search index",
            customer_visible=True,
        ),
        # The storage path uploads actually take, and it is local: no remote
        # call is made, so this one can be LIVE.
        _record(
            capability_id="storage.local_filesystem",
            category=CapabilityCategory.STORAGE,
            display_name="Local media storage",
            status=CapabilityStatus.LIVE,
            configured=True,
            customer_visible=True,
            reason_code=CapabilityReason.NONE,
            updated_at=now,
        ),
        # Declared and readiness-gated, but no upload path consumes it yet.
        # Marked not customer-visible so the public registry makes no claim
        # about media delivery through the object store.
        _external_status(
            configured=True,
            sandbox=False,
            updated_at=now,
            capability_id="storage.object_store",
            category=CapabilityCategory.STORAGE,
            display_name="Object storage (S3-compatible)",
            customer_visible=False,
        ),
        _external_status(
            configured=_configured(settings.IDENTITY_PROVIDER_TOKEN),
            sandbox=False,
            updated_at=now,
            capability_id="identity.zohal",
            category=CapabilityCategory.IDENTITY,
            display_name="Identity and mobile-ownership inquiry",
            customer_visible=False,
        ),
    ]


# ── Entry point ───────────────────────────────────────────────────────────


def build_capability_registry(
    settings: Settings,
    *,
    zarinpal_merchant_id_configured: bool = False,
    now: datetime | None = None,
) -> list[CapabilityRecord]:
    """Return the full capability registry, in a stable order.

    ``zarinpal_merchant_id_configured`` lets the caller report a merchant id
    that lives in the runtime settings store instead of the environment. It is
    a bare boolean on purpose: the registry never needs the value, so the value
    is never passed this far.

    Order is fixed (payments, shipping, messaging, search, storage, identity)
    so the output is byte-stable between calls and diffable in tests.
    """
    generated_at = now or datetime.now(UTC)
    return [
        *_payment_capabilities(
            settings,
            zarinpal_merchant_id_configured=zarinpal_merchant_id_configured,
            now=generated_at,
        ),
        *_shipping_capabilities(settings, generated_at),
        *_messaging_capabilities(settings, generated_at),
        *_platform_capabilities(settings, generated_at),
    ]


def customer_visible_capabilities(
    registry: list[CapabilityRecord],
) -> list[CapabilityRecord]:
    """The public subset: records a customer-facing surface may render.

    Filtering happens here rather than in the route so the rule is testable in
    isolation and the public/admin split cannot drift between the two routes.
    """
    return [record for record in registry if record.customer_visible]


# ── Runtime settings probe ────────────────────────────────────────────────


async def zarinpal_merchant_override_configured(db: AsyncSession) -> bool:
    """Whether an admin-registered Zarinpal merchant id exists in the settings store.

    The merchant id can be provisioned two ways: through the deployment
    environment (read by the settings object) or at runtime through the admin
    settings UI (stored in ``site_settings``). Only the second lives in the
    database, so it has to be probed separately.

    Returns a boolean, never the id: the registry composes presence
    information, and the value itself must not travel any further than it
    already does on the payment path.

    A missing key is an ordinary state and yields ``False``. Any other failure
    is allowed to propagate — reporting a gateway as unconfigured because the
    database was unreachable would be a false statement about the system, which
    is worse than an error on an informational endpoint.
    """
    from app.core.exceptions.handlers import NotFoundError
    from app.modules.settings.application.settings_service import SettingsService

    try:
        setting = await SettingsService.get_by_key(db, "payment.zarinpal.merchant_id")
    except NotFoundError:
        return False
    value = setting.value
    if isinstance(value, dict):
        return _configured(str(value.get("merchant_id") or ""))
    return _configured(str(value or ""))
