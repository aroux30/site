"""Catalog and Persian search browsing scenarios."""

import secrets
import urllib.parse
from locust import TaskSet, task

from load_tests.common.helpers import check_fastapi_response, get_random_search_query


class BrowsingTaskSet(TaskSet):
    """Simulates real Iranian shoppers browsing the catalog and searching with Persian keywords."""

    @task(10)
    def browse_categories(self) -> None:
        """Fetch category hierarchy (heavily cached / read-heavy)."""
        with self.client.get(
            "/api/v1/catalog/categories",
            catch_response=True,
            name="[Catalog] List Categories",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="List Categories")

    @task(15)
    def browse_products_paginated(self) -> None:
        """Browse paginated product listings."""
        page = secrets.randbelow(3) + 1
        size = secrets.choice([10, 20, 50])
        with self.client.get(
            f"/api/v1/catalog/products?page={page}&size={size}",
            catch_response=True,
            name="[Catalog] List Products (Paginated)",
        ) as response:
            data = check_fastapi_response(response, expected_status=200, name="List Products")
            if data and "items" in data and len(data["items"]) > 0:
                product = secrets.choice(data["items"])
                if isinstance(product, dict) and "id" in product:
                    self.user.discovered_product_id = product["id"]

    @task(8)
    def view_product_detail(self) -> None:
        """View a specific product detail page."""
        product_id = getattr(self.user, "discovered_product_id", None)
        if not product_id:
            return

        with self.client.get(
            f"/api/v1/catalog/products/{product_id}",
            catch_response=True,
            name="[Catalog] Product Detail",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="Product Detail")

    @task(12)
    def search_persian_products(self) -> None:
        """Search products with Persian queries containing Half-Space / ZWNJ."""
        query = get_random_search_query()
        encoded_query = urllib.parse.quote(query)
        with self.client.get(
            f"/api/v1/search?q={encoded_query}&size=10",
            catch_response=True,
            name="[Search] Persian Query with ZWNJ",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            elif response.status_code == 500:
                # Log degraded search service if Elasticsearch index is undergoing initialization
                response.failure(f"Elasticsearch service degraded: {response.text[:100]}")
            else:
                response.failure(f"Unexpected status: {response.status_code} - {response.text[:100]}")

    @task(6)
    def view_public_settings(self) -> None:
        """Fetch public store settings (/api/v1/settings/public)."""
        with self.client.get(
            "/api/v1/settings/public",
            catch_response=True,
            name="[Settings] Public Store Settings",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="Public Settings")
