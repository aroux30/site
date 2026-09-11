"""User scenarios for Locust stress testing."""

from load_tests.scenarios.browsing import BrowsingScenarioMixin
from load_tests.scenarios.cart import CartScenarioMixin
from load_tests.scenarios.checkout import CheckoutScenarioMixin
from load_tests.scenarios.health import HealthCheckMixin
from load_tests.scenarios.wallet import WalletScenarioMixin

__all__ = [
    "BrowsingScenarioMixin",
    "CartScenarioMixin",
    "CheckoutScenarioMixin",
    "HealthCheckMixin",
    "WalletScenarioMixin",
]
