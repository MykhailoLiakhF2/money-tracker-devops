# =============================================================================
# Money Tracker — Locust Load Test
# =============================================================================
# Install:  pip install locust
# Run:      locust -f scripts/locustfile.py --host=https://money-dev.your-domain.com
# Headless: locust -f scripts/locustfile.py --host=https://money-dev.your-domain.com \
#             --users 50 --spawn-rate 5 --run-time 5m --headless
# =============================================================================

from locust import HttpUser, task, between, events
import time


class MoneyTrackerUser(HttpUser):
    """
    Simulates a real user browsing the Money Tracker app.
    Each task has a weight — higher weight = called more often.
    wait_time = pause between requests (simulates human think time).
    """
    wait_time = between(1, 3)  # 1-3 seconds between requests

    # -- Health check (lightweight, frequent) --
    @task(3)
    def health_check(self):
        self.client.get("/api/health", name="GET /health")

    # -- Categories (cached by Redis — should be fast) --
    @task(5)
    def get_categories(self):
        self.client.get("/api/categories/", name="GET /categories")

    # -- Categories tree --
    @task(3)
    def get_categories_tree(self):
        self.client.get("/api/categories/tree", name="GET /categories/tree")

    # -- Accounts --
    @task(4)
    def get_accounts(self):
        self.client.get("/api/accounts/", name="GET /accounts")

    # -- Transactions (heaviest query — joins + pagination) --
    @task(5)
    def get_transactions(self):
        self.client.get("/api/transactions/", name="GET /transactions")


# =============================================================================
# Event hooks — print summary after test
# =============================================================================
@events.quitting.add_listener
def print_summary(environment, **kwargs):
    """Print key metrics when test finishes."""
    stats = environment.stats.total

    print("\n" + "=" * 50)
    print("  MONEY TRACKER LOAD TEST RESULTS")
    print("=" * 50)
    print(f"  Total requests:    {stats.num_requests}")
    print(f"  Failed requests:   {stats.num_failures}")
    print(f"  Error rate:        {stats.fail_ratio * 100:.2f}%")
    print(f"  RPS (avg):         {stats.total_rps:.1f} req/s")
    print(f"  Latency p50:       {stats.get_response_time_percentile(0.5):.0f}ms")
    print(f"  Latency p95:       {stats.get_response_time_percentile(0.95):.0f}ms")
    print(f"  Latency p99:       {stats.get_response_time_percentile(0.99):.0f}ms")
    print("=" * 50 + "\n")
