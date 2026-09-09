"""Factory for resolving a payment provider by name."""

from __future__ import annotations

from functools import lru_cache

from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
)


def get_payment_provider(provider_name: str) -> PaymentProvider:
    """Return the :class:`PaymentProvider` implementation for *provider_name*.

    Parameters
    ----------
    provider_name:
        One of ``"zarinpal"``, ``"idpay"``, ``"mock"``.

    Raises
    ------
    ValueError
        If the provider name is not recognised.
    """
    name = provider_name.lower().strip()
    registry = _provider_registry()

    if name not in registry:
        supported = ", ".join(sorted(registry.keys()))
        raise ValueError(
            f"Unknown payment provider '{provider_name}'. "
            f"Supported providers: {supported}"
        )

    return registry[name]


@lru_cache(maxsize=1)
def _provider_registry() -> dict[str, PaymentProvider]:
    """Lazily build and cache the provider registry.

    Imports are deferred so that the factory module itself has no heavy
    dependencies at import time.
    """
    from app.modules.payments.infrastructure.providers.idpay import (
        IDPayProvider,
    )
    from app.modules.payments.infrastructure.providers.mock import (
        MockProvider,
    )
    from app.modules.payments.infrastructure.providers.zarinpal import (
        ZarinpalProvider,
    )

    return {
        "zarinpal": ZarinpalProvider(),
        "idpay": IDPayProvider(),
        "mock": MockProvider(),
    }
