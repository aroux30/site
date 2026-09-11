"""Shopping Cart scenarios for concurrent sessions."""

from locust import TaskSet, task

from load_tests.common.helpers import check_fastapi_response, generate_session_id


class CartTaskSet(TaskSet):
    """Simulates realistic cart actions: fetch cart, add items, update quantities, validate cart."""

    def get_cart_headers(self) -> dict[str, str]:
        """Return session headers for cart operations."""
        sid = getattr(self.user, "session_id", None)
        if not sid:
            sid = generate_session_id()
            self.user.session_id = sid
        return {"X-Session-ID": sid}

    @task(10)
    def view_cart(self) -> None:
        """Fetch active cart for current session."""
        with self.client.get(
            "/api/v1/cart",
            headers=self.get_cart_headers(),
            catch_response=True,
            name="[Cart] View Cart",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="View Cart")

    @task(6)
    def add_item_to_cart(self) -> None:
        """Add product variant to cart (handles both 200 and 409 insufficient stock)."""
        variant_id = getattr(self.user, "test_variant_id", "3a06fdb3-207e-49f0-aa39-d1fd0576a1c7")
        payload = {
            "variant_id": variant_id,
            "quantity": 1,
        }
        with self.client.post(
            "/api/v1/cart/items",
            json=payload,
            headers=self.get_cart_headers(),
            catch_response=True,
            name="[Cart] Add Item",
        ) as response:
            if response.status_code in (200, 201):
                response.success()
            elif response.status_code == 409:
                # Valid business constraint (out of stock / concurrency lock)
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code} - {response.text[:200]}")

    @task(4)
    def validate_cart(self) -> None:
        """Validate cart stock and prices."""
        with self.client.post(
            "/api/v1/cart/validate",
            headers=self.get_cart_headers(),
            catch_response=True,
            name="[Cart] Validate Cart",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="Validate Cart")
