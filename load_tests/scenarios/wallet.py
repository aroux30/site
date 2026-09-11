"""Wallet operations and concurrent balance lookup scenarios."""

from locust import TaskSet, task

from load_tests.common.helpers import check_fastapi_response


class WalletTaskSet(TaskSet):
    """Simulates wallet balance inquiries and high-concurrency ledger operations."""

    @task(5)
    def query_wallet_balance(self) -> None:
        """Fetch wallet balance with row-lock awareness."""
        token = getattr(self.user, "auth_token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        with self.client.get(
            "/api/v1/wallet",
            headers=headers,
            catch_response=True,
            name="[Wallet] Get Wallet Balance",
        ) as response:
            if token:
                check_fastapi_response(response, expected_status=200, name="Get Wallet")
            else:
                if response.status_code == 401:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")

    @task(3)
    def list_wallet_transactions(self) -> None:
        """Fetch wallet transaction history."""
        token = getattr(self.user, "auth_token", None)
        headers = {"Authorization": f"Bearer {token}"} if token else {}

        with self.client.get(
            "/api/v1/wallet/transactions?limit=10",
            headers=headers,
            catch_response=True,
            name="[Wallet] List Transactions",
        ) as response:
            if token:
                check_fastapi_response(response, expected_status=200, name="List Transactions")
            else:
                if response.status_code == 401:
                    response.success()
                else:
                    response.failure(f"Unexpected status: {response.status_code}")
