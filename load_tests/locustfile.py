"""Main Locust load testing file for Iranian E-Commerce Platform.

Supports high-throughput simulations using FastHttpUser (geventhttpclient),
supporting 10,000+ concurrent simulated users in distributed mode.
"""

from locust import between
from locust.contrib.fasthttp import FastHttpUser

from load_tests.common.config import LOAD_TEST_SECRET_HEADER, TARGET_HOST
from load_tests.common.helpers import generate_session_id
from load_tests.scenarios.browsing import BrowsingScenarioMixin
from load_tests.scenarios.cart import CartScenarioMixin
from load_tests.scenarios.checkout import CheckoutScenarioMixin
from load_tests.scenarios.health import HealthCheckMixin
from load_tests.scenarios.wallet import WalletScenarioMixin


class AnonymousCatalogBrowserUser(FastHttpUser, BrowsingScenarioMixin, HealthCheckMixin):
    """Represents 60% of traffic: Iranian visitors browsing catalog & searching with Persian ZWNJ."""

    weight = 60
    host = TARGET_HOST
    wait_time = between(1.0, 3.0)
    default_headers = dict(LOAD_TEST_SECRET_HEADER)

    def on_start(self) -> None:
        self.session_id = generate_session_id()


class ActiveShopperUser(FastHttpUser, BrowsingScenarioMixin, CartScenarioMixin):
    """Represents 30% of traffic: Shoppers actively browsing, adding to cart, and checking stock."""

    weight = 30
    host = TARGET_HOST
    wait_time = between(1.5, 4.0)
    default_headers = dict(LOAD_TEST_SECRET_HEADER)

    def on_start(self) -> None:
        self.session_id = generate_session_id()
        self.test_variant_id = "3a06fdb3-207e-49f0-aa39-d1fd0576a1c7"


class TransactionalCheckoutUser(FastHttpUser, CheckoutScenarioMixin, WalletScenarioMixin, CartScenarioMixin):
    """Represents 10% of traffic: High-intensity transactional operations (quote, wallet, lock)."""

    weight = 10
    host = TARGET_HOST
    wait_time = between(2.0, 5.0)
    default_headers = dict(LOAD_TEST_SECRET_HEADER)

    def on_start(self) -> None:
        self.session_id = generate_session_id()
        self.test_variant_id = "3a06fdb3-207e-49f0-aa39-d1fd0576a1c7"
        self.auth_token = None


class StressHammerUser(FastHttpUser, BrowsingScenarioMixin, CartScenarioMixin, HealthCheckMixin):
    """Zero-delay rapid hammer user for testing peak concurrency and connection pooling limits."""

    weight = 0
    host = TARGET_HOST
    wait_time = between(0.05, 0.2)
    default_headers = dict(LOAD_TEST_SECRET_HEADER)

    def on_start(self) -> None:
        self.session_id = generate_session_id()
        self.test_variant_id = "3a06fdb3-207e-49f0-aa39-d1fd0576a1c7"
