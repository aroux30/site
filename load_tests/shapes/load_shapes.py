"""Custom Locust Load Test Shapes for 10,000 Concurrent User Simulations."""

from locust import LoadTestShape


class TenThousandUserSpikeShape(LoadTestShape):
    """Simulates an instantaneous Flash Sale stampede (10,000 concurrent users).
    
    Timeline:
      0 - 30s:    Warmup with 500 users
      30s - 90s:  Sudden spike to 10,000 concurrent users (spawn rate 200/s)
      90s - 210s: Sustained maximum stress load at 10,000 users
      210s - 240s: Cool-down ramp down to 1,000 users
      > 240s:     Test completion
    """

    stages = [
        {"duration": 30, "users": 500, "spawn_rate": 50},
        {"duration": 90, "users": 10000, "spawn_rate": 200},
        {"duration": 210, "users": 10000, "spawn_rate": 200},
        {"duration": 240, "users": 1000, "spawn_rate": 100},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                tick_data = (stage["users"], stage["spawn_rate"])
                return tick_data
        return None


class StepLoadShape10K(LoadTestShape):
    """Step-wise stress test climbing to 10,000 users to locate breaking point.
    
    Stages:
      - 1,000 users (Warmup / Baseline)
      - 3,000 users (Normal Peak)
      - 6,000 users (High Campaign Load)
      - 10,000 users (Extreme Stress Ceiling)
    """

    stages = [
        {"duration": 60, "users": 1000, "spawn_rate": 100},
        {"duration": 120, "users": 3000, "spawn_rate": 150},
        {"duration": 180, "users": 6000, "spawn_rate": 200},
        {"duration": 300, "users": 10000, "spawn_rate": 300},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return (stage["users"], stage["spawn_rate"])
        return None
