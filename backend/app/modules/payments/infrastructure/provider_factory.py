"""Factory for resolving a payment provider by name."""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.payments.infrastructure.providers.base import (
        PaymentProvider,
    )


def get_payment_provider(
    provider_name: str,
    merchant_id: str | None = None,
) -> PaymentProvider:
    """Return the :class:`PaymentProvider` implementation for *provider_name*.

    Parameters
    ----------
    provider_name:
        One of ``"zarinpal"``, ``"idpay"``, ``"mock"``, ``"wallet"``,
        ``"crypto"``, ``"card_transfer"`` (or alias ``"card_to_card"``).
    merchant_id:
        Optional gateway credential override (e.g. a Zarinpal merchant id
        registered through the admin settings UI at runtime).

    Raises
    ------
    ValueError
        If the provider name is not recognised.
    """
    name = provider_name.lower().strip()
    # Normalize aliases
    if name in ("card_to_card", "c2c", "card"):
        name = "card_transfer"
    elif name in ("nowpayments", "usdt", "btc", "eth"):
        name = "crypto"

    if name == "mock":
        from app.core.config.settings import get_settings

        settings = get_settings()
        if settings.ENVIRONMENT == "production":
            raise ValueError(
                "Security violation: Mock payment provider is strictly disabled in production environment"  # noqa: E501
            )

    registry = _provider_registry()

    if name not in registry:
        supported = ", ".join(sorted(registry.keys()))
        raise ValueError(
            f"Unknown payment provider '{provider_name}'. Supported providers: {supported}"
        )

    if merchant_id and name == "zarinpal":
        from app.modules.payments.infrastructure.providers.zarinpal import (
            ZarinpalProvider,
        )

        return ZarinpalProvider(merchant_id=merchant_id)

    return registry[name]


@lru_cache(maxsize=1)
def _provider_registry() -> dict[str, PaymentProvider]:
    """Lazily build and cache the provider registry.

    Imports are deferred so that the factory module itself has no heavy
    dependencies at import time.
    """
    from app.modules.payments.infrastructure.providers.card_to_card import (
        CardToCardProvider,
    )
    from app.modules.payments.infrastructure.providers.crypto import (
        NowPaymentsProvider,
    )
    from app.modules.payments.infrastructure.providers.idpay import (
        IDPayProvider,
    )
    from app.modules.payments.infrastructure.providers.mock import (
        MockProvider,
    )
    from app.modules.payments.infrastructure.providers.wallet import (
        WalletPaymentProvider,
    )
    from app.modules.payments.infrastructure.providers.zarinpal import (
        ZarinpalProvider,
    )

    card_provider = CardToCardProvider()
    crypto_provider = NowPaymentsProvider()

    return {
        "zarinpal": ZarinpalProvider(),
        "idpay": IDPayProvider(),
        "mock": MockProvider(),
        "wallet": WalletPaymentProvider(),
        "crypto": crypto_provider,
        "card_transfer": card_provider,
        "card_to_card": card_provider,
    }
