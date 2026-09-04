"""Integration tests for Phase 7 Dashboard Backend (BFF)."""

import pytest
from starlette.testclient import TestClient
from src.dashboard.api import app
from src.dashboard.db import db_manager


@pytest.fixture
def client():
    return TestClient(app)


def test_health_check(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
    assert resp.json()["service"] == "dashboard-bff"


def test_overview_kpis(client):
    resp = client.get("/api/overview/kpis")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_cases_evaluated"] > 0
    assert "loss_prevented_amount" in data
    assert "approval_rate" in data
    assert "review_rate" in data
    assert "block_rate" in data
    assert data["avg_decision_latency_ms"] > 0


def test_risk_distribution(client):
    resp = client.get("/api/overview/risk-distribution")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["buckets"]) == 10
    assert "APPROVE" in data["decision_breakdown"]
    assert "VERIFY" in data["decision_breakdown"]
    assert "BLOCK" in data["decision_breakdown"]
    assert 0.0 <= data["average_risk_score"] <= 1.0


def test_review_queue(client):
    resp = client.get("/api/review-queue?limit=10&offset=0")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] >= 0
    assert len(data["items"]) <= 10
    if len(data["items"]) > 0:
        item = data["items"][0]
        assert "request_id" in item
        assert "risk_score" in item
        assert "priority" in item
        assert item["priority"] in ("HIGH", "MEDIUM", "LOW")


def test_case_detail_and_action_flow(client):
    # 1. Get first case from review queue
    q_resp = client.get("/api/review-queue?limit=1")
    assert q_resp.status_code == 200
    q_data = q_resp.json()
    assert len(q_data["items"]) > 0
    case_id = q_data["items"][0]["request_id"]

    # 2. Fetch case detail
    detail_resp = client.get(f"/api/cases/{case_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["request_id"] == case_id
    assert "risk" in detail
    assert "order" in detail
    assert "explanation" in detail

    # 3. Submit analyst action
    action_payload = {
        "action": "ESCALATE",
        "analyst_id": "analyst_test_01",
        "override_reason": "Suspicious multi-device pattern detected",
        "notes": "Escalating to fraud lead for manual physical verification",
    }
    act_resp = client.post(f"/api/cases/{case_id}/action", json=action_payload)
    assert act_resp.status_code == 200
    act_data = act_resp.json()
    assert act_data["success"] is True
    assert act_data["status"] == "ESCALATED"

    # 4. Verify case detail updated with action
    updated_detail = client.get(f"/api/cases/{case_id}").json()
    assert updated_detail["status"] == "ESCALATED"
    assert len(updated_detail["analyst_actions"]) >= 1
    assert updated_detail["analyst_actions"][0]["analyst_id"] == "analyst_test_01"


def test_case_explanation(client):
    q_resp = client.get("/api/review-queue?limit=1")
    case_id = q_resp.json()["items"][0]["request_id"]

    exp_resp = client.get(f"/api/cases/{case_id}/explanation")
    assert exp_resp.status_code == 200
    exp_data = exp_resp.json()
    assert "reason_codes" in exp_data or "status" in exp_data


def test_case_timeline(client):
    q_resp = client.get("/api/review-queue?limit=1")
    case_id = q_resp.json()["items"][0]["request_id"]

    time_resp = client.get(f"/api/cases/{case_id}/timeline")
    assert time_resp.status_code == 200
    t_data = time_resp.json()
    assert t_data["request_id"] == case_id
    assert len(t_data["events"]) >= 3
    event_types = [e["event_type"] for e in t_data["events"]]
    assert "ACCOUNT_CREATED" in event_types
    assert "PURCHASE" in event_types
    assert "RETURN_REQUESTED" in event_types


def test_network_graph(client):
    q_resp = client.get("/api/review-queue?limit=1")
    case_id = q_resp.json()["items"][0]["request_id"]

    net_resp = client.get(f"/api/networks/{case_id}")
    assert net_resp.status_code == 200
    net_data = net_resp.json()
    assert net_data["request_id"] == case_id
    assert len(net_data["nodes"]) >= 3
    assert len(net_data["edges"]) >= 2
    assert "connected_component_size" in net_data["summary"]


def test_analytics_endpoints(client):
    # Fraud analytics
    f_resp = client.get("/api/analytics/fraud")
    assert f_resp.status_code == 200
    f_data = f_resp.json()
    assert len(f_data["vectors"]) >= 4
    assert len(f_data["trend_daily"]) == 7

    # Financial impact
    fi_resp = client.get("/api/analytics/financial-impact")
    assert fi_resp.status_code == 200
    fi_data = fi_resp.json()
    assert fi_data["gross_merchandise_value"] > 0
    assert fi_data["fraud_loss_prevented"] > 0
    assert fi_data["net_financial_savings"] > 0
    assert fi_data["roi_multiple"] > 0


def test_policies_and_simulation(client):
    # Get active policies
    p_resp = client.get("/api/policies")
    assert p_resp.status_code == 200
    p_data = p_resp.json()
    assert p_data["verify_threshold"] == 0.40
    assert p_data["block_threshold"] == 0.80
    assert len(p_data["rules"]) == 3

    # Simulate policy
    sim_payload = {
        "verify_threshold": 0.35,
        "block_threshold": 0.75,
    }
    sim_resp = client.post("/api/policies/simulate", json=sim_payload)
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["cases_evaluated"] > 0
    assert "simulated_distribution" in sim_data
    assert "loss_saved_difference" in sim_data
    assert "review_queue_workload_change_percent" in sim_data


def test_health_and_audit(client):
    # Model health
    m_resp = client.get("/api/model-health")
    assert m_resp.status_code == 200
    assert m_resp.json()["test_auroc"] >= 0.90

    # Feature health
    f_resp = client.get("/api/feature-health")
    assert f_resp.status_code == 200
    assert f_resp.json()["feature_count"] == 52

    # System health
    s_resp = client.get("/api/system-health")
    assert s_resp.status_code == 200
    assert s_resp.json()["status"] in ("healthy", "degraded")

    # Audit log
    a_resp = client.get("/api/audit")
    assert a_resp.status_code == 200
    assert a_resp.json()["total"] >= 1
