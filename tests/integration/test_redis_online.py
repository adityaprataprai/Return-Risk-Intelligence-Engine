"""Integration tests for Phase 5 Redis Online State and Graph Processor."""

import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.app import app
from src.features.graph_processor import GraphProcessor
from src.features.online_builder import OnlineFeatureBuilder
from src.inference.context_resolver import ContextResolver
from src.inference.redis_client import RedisClient
from src.inference.schemas import ReturnScoreRequest


@pytest.fixture(scope="module")
def redis_client():
    """Provides a RedisClient instance."""
    client = RedisClient()
    return client


def test_redis_client_basic_ops(redis_client):
    """Test basic JSON get, set, mget, and health operations."""
    health = redis_client.health_check()
    assert health["connected"] is True

    # Single key
    redis_client.set_json("test:user:1", {"score": 0.85})
    data = redis_client.get_json("test:user:1")
    assert data == {"score": 0.85}

    # Multi key MGET
    redis_client.set_json("test:user:2", {"score": 0.15})
    m_data = redis_client.mget_json(["test:user:1", "test:user:2", "test:user:missing"])
    assert len(m_data) == 3
    assert m_data[0] == {"score": 0.85}
    assert m_data[1] == {"score": 0.15}
    assert m_data[2] is None


def test_online_builder_and_redis_materialization(redis_client):
    """Test OnlineFeatureBuilder recording events and flushing to Redis."""
    builder = OnlineFeatureBuilder(redis_client=redis_client)
    builder.populate_economics()

    # Economic keys should exist
    m_econ = redis_client.get_json("risk:merchant:m_default:economics:v1")
    assert m_econ is not None
    assert "feature_values" in m_econ

    # Record user events
    u = "usr_test_redis_001"
    now = datetime.now(timezone.utc)
    builder.record_account_created(u, now)
    builder.record_order(u, now, price=2500.0, category="electronics", device_id="dev_test_01")
    builder.record_return(u, now, refund_amount=2500.0, category="electronics", device_id="dev_test_01")

    # Flush
    builder.flush_to_redis(user_ids=[u], device_ids=["dev_test_01"])

    # Verify keys in Redis
    u_data = redis_client.get_json(f"risk:user:{u}:features:v2")
    assert u_data is not None
    assert u_data["feature_values"]["returns_24h"] == 1
    assert u_data["feature_values"]["orders_24h"] == 1

    d_data = redis_client.get_json("risk:device:dev_test_01:features:v2")
    assert d_data is not None
    assert d_data["feature_values"]["device_users_count"] >= 1


def test_graph_processor_metrics_and_materialization(redis_client):
    """Test GraphProcessor computing multi-hop metrics and writing to Redis."""
    gp = GraphProcessor(redis_client=redis_client, graph_version="g0001")

    # User 1 and User 2 share device D1
    gp.add_relationship("usr_graph_1", "device", "dev_shared_100")
    gp.add_relationship("usr_graph_2", "device", "dev_shared_100")

    # User 2 and User 3 share address A1
    gp.add_relationship("usr_graph_2", "address", "addr_shared_200")
    gp.add_relationship("usr_graph_3", "address", "addr_shared_200")

    # User 2 has 2 prior returns (high return neighbor)
    gp.record_user_returns("usr_graph_2", 2)

    # Compute for usr_graph_1:
    # 1-hop: usr_graph_2
    # 2-hop: usr_graph_3
    metrics = gp.compute_user_graph_metrics("usr_graph_1")
    assert metrics["linked_accounts_1hop"] == 1
    assert metrics["linked_accounts_2hop"] == 1
    assert metrics["shared_device_accounts"] == 1
    assert metrics["shared_address_accounts"] == 0
    assert metrics["high_return_neighbor_count"] == 1
    assert metrics["connected_component_size"] == 3

    # Materialize to Redis
    gp.materialize_to_redis(user_ids=["usr_graph_1"])

    g_data = redis_client.get_json("risk:user:usr_graph_1:graph:v2")
    assert g_data is not None
    assert g_data["feature_values"]["connected_component_size"] == 3
    assert g_data["graph_version"] == "g0001"


def test_context_resolver_redis_retrieval(redis_client):
    """Test ContextResolver reading online state from Redis."""
    cr = ContextResolver(redis_client=redis_client)
    req = ReturnScoreRequest(
        request_id="ret_cr_test",
        merchant_id="m_default",
        user_id="usr_graph_1",
        transaction_id="txn_cr_001",
        product_id="prod_cr_001",
        timestamp="2026-09-04T00:00:00Z",
        refund_amount=1500.0,
        order_amount=2000.0,
        product_category="electronics",
    )

    ml_features, econ_context, meta = cr.resolve(req)
    assert meta["graph_version"] == "g0001"
    assert "graph_age_ms" in meta
    assert econ_context["merchant_profile"]["margin_rate"] == 0.15


def test_score_endpoint_e2e_with_redis():
    """Test POST /v1/risk/returns/score with Redis state and verify latency < 50ms."""
    client = TestClient(app)
    req_payload = {
        "request_id": f"ret_e2e_{int(time.time()*1000)}",
        "merchant_id": "m_default",
        "user_id": "usr_graph_1",
        "transaction_id": "txn_e2e_001",
        "product_id": "prod_e2e_001",
        "timestamp": "2026-09-04T00:00:00Z",
        "refund_amount": 1200.0,
        "order_amount": 1500.0,
        "product_category": "electronics",
    }

    # Warmup request
    client.post("/v1/risk/returns/score", json=req_payload)

    # Measure scored request latency
    req_payload["request_id"] = f"ret_e2e_timed_{int(time.time()*1000)}"
    t0 = time.perf_counter()
    resp = client.post("/v1/risk/returns/score", json=req_payload)
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert resp.status_code == 200
    data = resp.json()

    assert data["decision"]["action"] in ["APPROVE", "VERIFY", "BLOCK"]
    assert data["features"]["graph_version"] == "g0001"
    assert data["features"]["graph_age_ms"] >= 0
    assert elapsed_ms < 50.0, f"Latency {elapsed_ms:.2f}ms exceeded 50ms threshold"
