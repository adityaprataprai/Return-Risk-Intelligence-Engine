"""Unit and integration tests for Phase 9 Observability and Deployment deliverables."""

import json
import logging
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from src.app import app as api_app
from src.dashboard.api import app as bff_app
from src.common.logging import JSONFormatter, set_request_id, get_request_id
from src.common.metrics import (
    ECONOMIC_DECISION_TOTAL,
    GRAPH_FEATURE_AGE_SECONDS,
    RISK_SCORE_LATENCY_SECONDS,
    RISK_SCORE_REQUESTS_TOTAL,
    SHAP_QUEUE_DEPTH,
    record_risk_score,
    update_graph_feature_age,
    update_shap_queue_depth,
)


def test_prometheus_custom_metrics():
    """Verify that all Phase 9 custom Prometheus metrics exist and update properly."""
    initial_queue = SHAP_QUEUE_DEPTH._value.get()
    update_shap_queue_depth(15)
    assert SHAP_QUEUE_DEPTH._value.get() == 15.0

    update_graph_feature_age(350.0, "g0000")
    assert GRAPH_FEATURE_AGE_SECONDS.labels(graph_version="g0000")._value.get() == 350.0

    record_risk_score(
        action="APPROVE",
        duration_seconds=0.012,
        model_version="v1.0.0",
        status_str="success",
    )


def test_api_metrics_endpoint():
    """Test that the scoring API exposes a valid Prometheus /metrics endpoint."""
    client = TestClient(api_app)
    response = client.get("/metrics")
    assert response.status_code == 200
    content = response.text
    assert "risk_score_requests_total" in content
    assert "economic_decision_total" in content
    assert "shap_queue_depth" in content


def test_dashboard_bff_metrics_endpoint():
    """Test that the Dashboard BFF exposes a valid Prometheus /metrics endpoint."""
    client = TestClient(bff_app)
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http_requests_total" in response.text or "process_cpu_seconds_total" in response.text


def test_request_id_middleware_propagation():
    """Test that RequestIdMiddleware propagates incoming correlation IDs and sets response header."""
    client = TestClient(api_app)
    custom_id = "test-corr-id-998877"

    response = client.get("/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id

    # Test automatic UUID generation when header not provided
    response2 = client.get("/health")
    assert response2.status_code == 200
    generated_id = response2.headers.get("X-Request-ID")
    assert generated_id is not None
    assert generated_id.startswith("req_")


def test_structured_json_logging_with_request_id():
    """Test that JSONFormatter injects the active context request_id."""
    formatter = JSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Test risk scoring event",
        args=(),
        exc_info=None,
    )

    set_request_id("ctx_req_12345")
    try:
        formatted = formatter.format(record)
        parsed = json.loads(formatted)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test risk scoring event"
        assert parsed["request_id"] == "ctx_req_12345"
    finally:
        set_request_id(None)


def test_scoring_updates_prometheus_metrics():
    """Verify that scoring endpoint records request count and decision metrics."""
    client = TestClient(api_app)
    req_payload = {
        "request_id": "req_obs_test_001",
        "merchant_id": "m_fashion_01",
        "user_id": "u_test_obs",
        "transaction_id": "txn_obs_001",
        "product_id": "prod_obs_001",
        "timestamp": "2026-09-02T21:40:11Z",
        "order_amount": 2500.0,
        "refund_amount": 2500.0,
        "product_category": "electronics",
        "device_id": "dev_obs_01",
        "address_id": "addr_obs_01",
        "payment_id": "pay_obs_01",
    }

    response = client.post("/v1/risk/returns/score", json=req_payload)
    assert response.status_code == 200
    data = response.json()
    action = data["decision"]["action"]

    metrics_res = client.get("/metrics")
    assert metrics_res.status_code == 200
    assert f'action="{action}"' in metrics_res.text


def test_deployment_and_docker_files_exist():
    """Ensure all Phase 9 deployment manifests and Dockerfiles exist."""
    base_dir = Path(__file__).resolve().parent.parent

    # Dockerfiles
    assert (base_dir / "deployment" / "Dockerfile.api").is_file()
    assert (base_dir / "deployment" / "Dockerfile.dashboard").is_file()
    assert (base_dir / "deployment" / "Dockerfile.frontend").is_file()
    assert (base_dir / "deployment" / "Dockerfile.shap_worker").is_file()
    assert (base_dir / "deployment" / "Dockerfile.graph_processor").is_file()

    # Orchestration and monitoring configs
    assert (base_dir / "docker-compose.yml").is_file()
    assert (base_dir / "deployment" / "prometheus.yml").is_file()
    assert (base_dir / "deployment" / "grafana" / "datasources" / "prometheus.yml").is_file()
    assert (base_dir / "deployment" / "grafana" / "dashboards" / "dashboards.yml").is_file()
    assert (base_dir / "deployment" / "grafana" / "dashboards" / "risk_engine_overview.json").is_file()

    # Load test & scripts
    assert (base_dir / "tests" / "load" / "locustfile.py").is_file()
    assert (base_dir / "scripts" / "run_all.sh").is_file()
    assert (base_dir / ".github" / "workflows" / "ci.yml").is_file()


def test_locustfile_task_structure():
    """Verify Locust load test tasks and schema."""
    from tests.load.locustfile import ReturnScoringUser
    tasks = ReturnScoringUser.tasks
    assert len(tasks) > 0
