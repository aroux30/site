"""Health and Readiness probe scenarios."""

from locust import task
from locust.contrib.fasthttp import FastHttpUser
from load_tests.common.helpers import check_fastapi_response


class HealthCheckMixin:
    """Tasks for validating container and dependency health under heavy load."""

    @task(3)
    def test_liveness_probe(self: FastHttpUser) -> None:
        """Verify API liveness (/api/health/live)."""
        with self.client.get(
            "/api/health/live",
            catch_response=True,
            name="[Health] Liveness Probe",
        ) as response:
            check_fastapi_response(response, expected_status=200, name="Liveness Probe")

    @task(1)
    def test_readiness_probe(self: FastHttpUser) -> None:
        """Verify subsystem readiness (/api/health/ready) including DB, Redis, ES, and S3."""
        with self.client.get(
            "/api/health/ready",
            catch_response=True,
            name="[Health] Readiness Probe",
        ) as response:
            data = check_fastapi_response(response, expected_status=200, name="Readiness Probe")
            if data and data.get("status") != "ok":
                response.failure(f"Subsystems degraded: {data}")
