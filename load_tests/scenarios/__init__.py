"""User scenarios and TaskSets for Locust stress testing."""

from load_tests.scenarios.browsing import BrowsingTaskSet
from load_tests.scenarios.cart import CartTaskSet
from load_tests.scenarios.checkout import CheckoutTaskSet
from load_tests.scenarios.health import HealthTaskSet
from load_tests.scenarios.wallet import WalletTaskSet

__all__ = [
    "BrowsingTaskSet",
    "CartTaskSet",
    "CheckoutTaskSet",
    "HealthTaskSet",
    "WalletTaskSet",
]
