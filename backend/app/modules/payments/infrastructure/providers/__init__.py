"""Payment gateway providers package."""

from app.modules.payments.infrastructure.providers.base import (
    PaymentProvider,
    PaymentResult,
)
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

__all__ = [
    "CardToCardProvider",
    "IDPayProvider",
    "MockProvider",
    "NowPaymentsProvider",
    "PaymentProvider",
    "PaymentResult",
    "WalletPaymentProvider",
    "ZarinpalProvider",
]
