"""Integration tests for synchronous scoring endpoint POST /v1/risk/returns/score."""

import sys
import time
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.app import app
from src.inference.economic_engine import EconomicDecisionEngine
from src.inference.schemas import ReturnScoreRequest, ReturnScoreResponse


@pytest.fixture(scope="module")
def client():
    """Provides a TestClient for FastAPI."""
    with TestClient(app) as c:
        yield c


@pytest.fixture
def sample_payload():
    """Standard return request payload."""
    return {
        "request_id": "ret_test_12345",
        "merchant_id": "m_102",
        "user_id": "usr_981",
        "transaction_id": "txn_12891",
        "product_id": "prod_7781",
        "timestamp": "2026-09-02T21:40:11Z",
        "refund_amount": 8420.0,
        "order_amount": 10500.0,
        "product_category": "electronics",
        "device_id": "dev_391",
        "address_id": "addr_120",
        "payment_id": "pay_883",
    }


def test_score_endpoint_success_and_schema(client, sample_payload):
    """Test that POST /v1/risk/returns/score succeeds, matches schema, and produces calibrated probability."""
    response = client.post("/v1/risk/returns/score", json=sample_payload)
    assert response.status_code == 200

    data = response.json()
    validated = ReturnScoreResponse.model_validate(data)

    assert validated.request_id == sample_payload["request_id"]
    assert 0.0 <= validated.risk.probability <= 1.0
    assert validated.risk.model_version.startswith("rr-lgbm-")
    assert validated.risk.calibration_version.startswith("cal-")

    assert validated.decision.action in ["APPROVE", "VERIFY", "BLOCK"]
    assert validated.decision.expected_loss >= 0.0
    assert validated.decision.policy_version == "policy-3.0"

    assert validated.features.feature_version == "fv-2.1"
    assert validated.economics.merchant_profile_version == "merchant-econ-1.7"
    assert validated.economics.product_profile_version == "product-econ-4.2"
    assert validated.explanation.status == "PENDING"


def test_score_endpoint_latency_under_50ms(client, sample_payload):
    """Test that scoring latency is well under 50ms (critical path has no graph traversal or SHAP)."""
    # Warmup request
    client.post("/v1/risk/returns/score", json=sample_payload)

    latencies = []
    for i in range(5):
        payload = sample_payload.copy()
        payload["request_id"] = f"ret_perf_{i}_{int(time.time()*1000)}"
        start = time.perf_counter()
        resp = client.post("/v1/risk/returns/score", json=payload)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies.append(elapsed_ms)
        assert resp.status_code == 200

    avg_latency = sum(latencies) / len(latencies)
    assert avg_latency < 50.0, f"Average latency too high: {avg_latency:.2f}ms"


def test_score_endpoint_idempotency(client, sample_payload):
    """Test that identical duplicate requests return the exact same cached response."""
    payload = sample_payload.copy()
    payload["request_id"] = f"ret_idem_{int(time.time()*1000)}"

    resp1 = client.post("/v1/risk/returns/score", json=payload)
    resp2 = client.post("/v1/risk/returns/score", json=payload)

    assert resp1.status_code == 200
    assert resp2.status_code == 200
    assert resp1.json() == resp2.json()


def test_score_endpoint_cold_start(client):
    """Test scoring an unseen customer/transaction not in the feature store (cold-start fallback)."""
    unseen_payload = {
        "request_id": f"ret_unseen_{int(time.time()*1000)}",
        "merchant_id": "m_unknown_merchant",
        "user_id": "usr_brand_new_customer",
        "transaction_id": "txn_brand_new_transaction",
        "product_id": "prod_brand_new",
        "timestamp": "2026-09-03T10:00:00Z",
        "refund_amount": 1500.0,
        "order_amount": 2000.0,
        "product_category": "fashion",
    }
    response = client.post("/v1/risk/returns/score", json=unseen_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"]["action"] in ["APPROVE", "VERIFY", "BLOCK"]
    assert 0.0 <= data["risk"]["probability"] <= 1.0


def test_economic_decision_engine_unit():
    """Unit test for EconomicDecisionEngine checking thresholds and expected loss logic."""
    engine = EconomicDecisionEngine()
    context = {
        "refund_amount": 2000.0,
        "order_amount": 2500.0,
        "merchant_profile": {"customer_acquisition_cost": 400.0, "churn_cost_multiplier": 2.5},
        "product_profile": {
            "cogs_rate": 0.5,
            "return_shipping_cost": 100.0,
            "handling_cost": 50.0,
            "restocking_cost_rate": 0.05,
            "salvage_value_percentage": 0.5,
        },
    }

    # Low risk -> APPROVE
    decision_low = engine.decide(0.10, context)
    assert decision_low.action == "APPROVE"
    assert decision_low.expected_loss > 0.0

    # Medium risk -> VERIFY
    decision_mid = engine.decide(0.50, context)
    assert decision_mid.action == "VERIFY"
    assert decision_mid.expected_loss > 0.0

    # High risk -> BLOCK
    decision_high = engine.decide(0.90, context)
    assert decision_high.action == "BLOCK"
    assert decision_high.expected_loss > 0.0


def test_score_endpoint_validation_error(client):
    """Test that invalid request payloads return 422 Unprocessable Entity."""
    invalid_payload = {
        "request_id": "ret_invalid",
        "refund_amount": -50.0,  # Invalid negative refund
    }
    response = client.post("/v1/risk/returns/score", json=invalid_payload)
    assert response.status_code == 422
