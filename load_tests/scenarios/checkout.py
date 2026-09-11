"""Checkout and Order placement scenarios under high concurrent load."""

from locust import TaskSet, task

from load_tests.common.helpers import check_fastapi_response, get_random_province


class CheckoutTaskSet(TaskSet):
    """Simulates high-stress checkout operations: price quotes, coupon redemption, and stock locks."""

    @task(5)
    def calculate_checkout_quote(self) -> None:
        """Calculate server-authoritative checkout quote with shipping and VAT."""
        token = getattr(self.user, "auth_token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        payload = {
            "shipping_method_slug": "pishtaz",
            "shipping_address": {
                "province": get_random_province(),
                "city": "مرکز استان",
                "postal_code": "1234567890",
                "street_address": "بلوار جمهوری، پلاک ۱۲",
                "recipient_name": "کاربر تستی بارگذاری",
                "recipient_phone": "09120000000",
            },
            "coupon_code": "WELCOME",
        }

        with self.client.post(
            "/api/v1/checkout/quote",
            json=payload,
            headers=headers,
            catch_response=True,
            name="[Checkout] Calculate Quote",
        ) as response:
            if token:
                check_fastapi_response(response, expected_status=200, name="Calculate Quote")
            else:
                if response.status_code == 401:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def validate_checkout_readiness(self) -> None:
        """Validate checkout readiness (inventory locks, address verification)."""
        token = getattr(self.user, "auth_token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        payload = {
            "shipping_method_slug": "pishtaz",
            "shipping_address": {
                "province": "تهران",
                "city": "تهران",
                "postal_code": "1234567890",
                "street_address": "خیابان آزادی",
                "recipient_name": "تست استرس",
                "recipient_phone": "09121111111",
            },
        }

        with self.client.post(
            "/api/v1/checkout/validate",
            json=payload,
            headers=headers,
            catch_response=True,
            name="[Checkout] Validate Checkout",
        ) as response:
            if token:
                check_fastapi_response(response, expected_status=200, name="Validate Checkout")
            else:
                if response.status_code == 401:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")
