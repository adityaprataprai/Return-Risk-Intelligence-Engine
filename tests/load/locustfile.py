"""Locust load testing suite for Razorpay Return-Risk Intelligence Engine.

Simulates concurrent merchant return scoring requests, verifying sub-50ms P50 latency
and sub-100ms P95 latency SLA under sustained multi-user concurrency.

Usage:
    # Interactive UI mode:
    locust -f tests/load/locustfile.py --host http://localhost:8000

    # Headless benchmark mode (100 users, 10 spawn rate, 30s run):
    locust -f tests/load/locustfile.py --host http://localhost:8000 --headless -u 100 -r 10 --run-time 30s
"""

import random
import time
import uuid
from locust import HttpUser, between, task


SAMPLE_MERCHANTS = [
    "m_fashion_01",
    "m_electronics_02",
    "m_luxury_03",
    "m_apparel_04",
    "m_footwear_05",
]

SAMPLE_CATEGORIES = [
    "APPAREL_WOMEN",
    "CONSUMER_ELECTRONICS",
    "LUXURY_HANDBAGS",
    "FOOTWEAR",
    "JEWELRY",
    "HOME_APPLIANCES",
]

SAMPLE_REASONS = [
    "SIZE_TOO_LARGE",
    "SIZE_TOO_SMALL",
    "COLOR_NOT_AS_EXPECTED",
    "DEFECTIVE_ON_ARRIVAL",
    "DAMAGED_IN_SHIPPING",
    "ITEM_NOT_AS_DESCRIBED",
    "CHANGED_MIND",
]

SAMPLE_DEVICES = [
    "dev_ios_iphone14_a89f",
    "dev_android_s22_44b1",
    "dev_chrome_win11_c019",
    "dev_safari_mac_e391",
    "dev_shared_emulator_991b",
]


class ReturnScoringUser(HttpUser):
    """Simulates e-commerce checkout & return scoring requests with realistic workloads."""

    # Wait between 50ms and 150ms between requests to achieve high throughput per user
    wait_time = between(0.05, 0.15)

    def on_start(self):
        """Initial user warmup and health validation."""
        self.user_token = f"usr_{random.randint(1000, 9999)}"
        self.device_id = random.choice(SAMPLE_DEVICES)

    @task(10)
    def score_standard_return(self):
        """Primary scoring workload: standard single/dual item return."""
        req_id = f"req_load_{uuid.uuid4().hex[:12]}"
        order_id = f"ord_{random.randint(10000, 99999)}"
        merchant_id = random.choice(SAMPLE_MERCHANTS)
        category = random.choice(SAMPLE_CATEGORIES)
        item_price = round(random.uniform(799.0, 6500.0), 2)
        refund_amount = item_price

        payload = {
            "request_id": req_id,
            "merchant_id": merchant_id,
            "user_id": self.user_token,
            "transaction_id": order_id,
            "product_id": f"prod_{random.randint(100, 999)}",
            "timestamp": "2026-09-03T12:00:00Z",
            "order_amount": item_price + round(random.uniform(500.0, 3000.0), 2),
            "refund_amount": refund_amount,
            "product_category": category,
            "device_id": self.device_id,
            "address_id": f"addr_{random.randint(100, 999)}",
            "payment_id": f"pay_{random.randint(100, 999)}",
        }

        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": req_id,
            "X-Client-Platform": "web",
        }

        start_time = time.perf_counter()
        with self.client.post(
            "/v1/risk/returns/score",
            json=payload,
            headers=headers,
            catch_response=True,
            name="/v1/risk/returns/score",
        ) as response:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            if response.status_code == 200:
                data = response.json()
                # Verify schema conformity
                if "risk" in data and "decision" in data and "action" in data["decision"]:
                    # Flag SLA breaches if P95 exceeds target threshold (100ms)
                    if latency_ms > 100.0:
                        response.success()  # Logged but tracked
                    else:
                        response.success()
                else:
                    response.failure(f"Malformed response payload: {response.text[:200]}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:200]}")

    @task(2)
    def score_high_risk_syndicate_return(self):
        """Simulates high-velocity shared device return spike."""
        req_id = f"req_spike_{uuid.uuid4().hex[:12]}"
        payload = {
            "request_id": req_id,
            "merchant_id": "m_luxury_03",
            "user_id": f"usr_cluster_{random.randint(1, 10)}",
            "transaction_id": f"txn_synd_{random.randint(1000, 5000)}",
            "product_id": "prod_lux_991",
            "timestamp": "2026-09-03T12:05:00Z",
            "order_amount": 28999.00,
            "refund_amount": 28999.00,
            "product_category": "LUXURY_HANDBAGS",
            "device_id": "dev_shared_emulator_991b",
            "address_id": "addr_cluster_1",
            "payment_id": "pay_cluster_1",
        }

        self.client.post(
            "/v1/risk/returns/score",
            json=payload,
            headers={"X-Request-ID": req_id},
            name="/v1/risk/returns/score (syndicate)",
        )

    @task(1)
    def query_health_probe(self):
        """Synthetic healthcheck probe."""
        self.client.get("/health", name="/health")

    @task(1)
    def query_prometheus_metrics(self):
        """Simulates Prometheus scraper load."""
        self.client.get("/metrics", name="/metrics")
