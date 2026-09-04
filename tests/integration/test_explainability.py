"""Integration tests for Phase 6 Asynchronous TreeSHAP Explainability."""

from pathlib import Path
import pytest
from starlette.testclient import TestClient
from src.app import app
from src.explainability import (
    EvidenceBuilder,
    ExplanationJob,
    ExplanationQueue,
    ExplanationRecord,
    ExplanationStore,
    FeatureAttribution,
    ReasonCodeEngine,
    SemanticGrouper,
    ShapWorker,
)


@pytest.fixture
def test_client():
    return TestClient(app)


@pytest.fixture
def mock_feature_vector():
    """Returns a realistic high-risk feature vector matching the 52 features."""
    return {
        "returns_24h": 4.0,
        "returns_7d": 7.0,
        "returns_30d": 12.0,
        "orders_24h": 5.0,
        "orders_7d": 8.0,
        "orders_30d": 15.0,
        "total_orders_all_time": 20.0,
        "total_returns_all_time": 15.0,
        "return_rate_30d": 0.80,
        "return_rate_all_time": 0.75,
        "total_spend_30d": 25000.0,
        "refund_amount_30d": 20000.0,
        "refund_ratio_30d": 0.80,
        "days_since_last_order": 0.5,
        "days_since_last_return": 0.2,
        "days_to_return_current": 1.0,
        "avg_days_to_return_user": 1.2,
        "wardrobing_risk_score": 0.92,
        "item_price_vs_user_avg": 2.5,
        "category_return_rate_baseline": 0.12,
        "user_category_return_rate_diff": 0.68,
        "device_users_count": 5.0,
        "device_returns_30d": 8.0,
        "device_return_rate_30d": 0.75,
        "address_users_count": 3.0,
        "address_returns_30d": 5.0,
        "payment_users_count": 2.0,
        "payment_returns_30d": 4.0,
        "linked_accounts_1hop": 4.0,
        "linked_accounts_2hop": 8.0,
        "shared_device_accounts": 4.0,
        "shared_address_accounts": 2.0,
        "shared_payment_accounts": 1.0,
        "high_return_neighbor_count": 3.0,
        "connected_component_size": 7.0,
        "order_amount": 12000.0,
        "refund_amount": 12000.0,
        "cogs": 7200.0,
        "shipping_cost": 250.0,
        "return_shipping_cost": 300.0,
        "handling_cost": 150.0,
        "restocking_cost": 200.0,
        "salvage_value_percentage": 0.30,
        "estimated_return_loss": 5800.0,
        "is_first_purchase": 0.0,
        "account_age_hours": 120.0,
        "account_age_under_24h": 0.0,
        "has_prior_orders": 1.0,
        "has_prior_returns": 1.0,
        "user_history_count": 20.0,
        "baseline_support_count": 500.0,
        "used_category_fallback": 0.0,
    }


def test_semantic_grouper_and_ranking():
    """Validates semantic grouping and ranking behavior."""
    grouper = SemanticGrouper()

    # Check mapping
    assert grouper.get_group_for_feature("returns_24h") == "velocity"
    assert grouper.get_group_for_feature("linked_accounts_1hop") == "graph_abuse"
    assert grouper.get_group_for_feature("wardrobing_risk_score") == "return_behavior"
    assert grouper.get_group_for_feature("estimated_return_loss") == "transaction_value"
    assert grouper.get_group_for_feature("days_since_last_order") == "sequence"
    assert grouper.get_group_for_feature("account_age_hours") == "evidence_quality"

    # Verify evidence_quality is non-punitive
    assert not grouper.is_punitive_group("evidence_quality")
    assert grouper.is_punitive_group("velocity")
    assert grouper.is_punitive_group("graph_abuse")

    # Group attribution ranking
    attrs = [
        FeatureAttribution(
            feature="returns_24h",
            value=4.0,
            shap_value=1.5,
            abs_shap=1.5,
            direction="RISK_INCREASING",
        ),
        FeatureAttribution(
            feature="linked_accounts_1hop",
            value=3.0,
            shap_value=2.0,
            abs_shap=2.0,
            direction="RISK_INCREASING",
        ),
        FeatureAttribution(
            feature="account_age_hours",
            value=12.0,
            shap_value=0.8,
            abs_shap=0.8,
            direction="RISK_INCREASING",
        ),
    ]

    grouped = grouper.group_attributions(attrs)
    assert len(grouped) == 6
    # Top ranked punitive group should be graph_abuse (shap=2.0)
    assert grouped[0].group_name == "graph_abuse"
    assert grouped[0].rank == 1
    # evidence_quality should be at the bottom since is_punitive is False
    assert grouped[-1].group_name == "evidence_quality"


def test_cold_start_isolation(mock_feature_vector):
    """Ensures cold-start / evidence-quality features are never punitive reason codes."""
    engine = ReasonCodeEngine()

    # Case A: Brand new account with zero history
    cold_vector = dict(mock_feature_vector)
    cold_vector["account_age_hours"] = 2.5
    cold_vector["is_first_purchase"] = 1.0
    cold_vector["user_history_count"] = 0.0

    conf = engine.evaluate_data_confidence(cold_vector)
    assert conf.confidence_level == "LOW_COLD_START"
    assert conf.cold_start_indicators["account_age_hours"] == 2.5
    assert conf.cold_start_indicators["is_first_purchase"] is True

    # Case B: High SHAP on account_age_hours must NOT generate a punitive reason code
    attrs = [
        FeatureAttribution(
            feature="account_age_hours",
            value=2.5,
            shap_value=3.5,
            abs_shap=3.5,
            direction="RISK_INCREASING",
        ),
        FeatureAttribution(
            feature="is_first_purchase",
            value=1.0,
            shap_value=2.1,
            abs_shap=2.1,
            direction="RISK_INCREASING",
        ),
        FeatureAttribution(
            feature="returns_24h",
            value=3.0,
            shap_value=1.2,
            abs_shap=1.2,
            direction="RISK_INCREASING",
        ),
    ]

    reasons = engine.generate_reason_codes(attrs, cold_vector)
    reason_codes = [r.code for r in reasons]

    # Must contain velocity reason, but MUST NOT contain any cold-start reason
    assert "RC_HIGH_RETURN_VELOCITY" in reason_codes
    for r in reasons:
        assert r.group != "evidence_quality"
        assert "account_age" not in r.code.lower()


def test_evidence_builder_formatting():
    """Validates evidence text generation with formatting."""
    features = {
        "returns_24h": 4.0,
        "returns_7d": 9.0,
        "refund_ratio_30d": 0.852,
        "refund_amount": 14250.50,
        "linked_accounts_1hop": 3.0,
        "connected_component_size": 5.0,
    }

    tmpl = "Customer initiated {returns_24h:d} return(s) in the last 24 hours ({returns_7d:d} in prior 7 days)."
    text, supp = EvidenceBuilder.build_evidence(
        code="RC_HIGH_RETURN_VELOCITY",
        template=tmpl,
        features=features,
        relevant_feature_names=["returns_24h", "returns_7d"],
    )

    assert "4 return(s) in the last 24 hours" in text
    assert "9 in prior 7 days" in text
    assert supp["returns_24h"] == 4.0
    assert supp["returns_7d"] == 9.0


def test_tree_shap_worker_raw_margin_additivity(mock_feature_vector):
    """Verifies that TreeSHAP satisfies exact additivity in raw margin space."""
    worker = ShapWorker()
    worker.initialize()

    shap_vals, base_val = worker.compute_shap(mock_feature_vector)
    assert len(shap_vals) == len(worker.feature_names)

    # Compute raw margin directly from booster
    import pandas as pd
    row = [mock_feature_vector[f] for f in worker.feature_names]
    X = pd.DataFrame([row], columns=worker.feature_names)
    raw_margin = float(worker.model.predict(X, raw_score=True)[0])

    reconstructed = base_val + float(shap_vals.sum())
    delta = abs(reconstructed - raw_margin)

    # Must reconstruct model output within 1e-4 tolerance
    assert delta < 1e-4, f"Additivity error delta={delta} exceeds 1e-4 tolerance"


def test_e2e_scoring_and_async_explanation(test_client):
    """E2E test: scoring enqueues job, endpoint returns PENDING then READY after worker."""
    req_id = "test_ret_phase6_e2e_999"
    payload = {
        "request_id": req_id,
        "merchant_id": "m_102",
        "user_id": "usr_981",
        "transaction_id": "txn_88219",
        "product_id": "prod_4421",
        "timestamp": "2026-09-04T03:00:00Z",
        "refund_amount": 9500.0,
        "order_amount": 10500.0,
        "product_category": "electronics",
        "device_id": "dev_391",
        "address_id": "addr_120",
        "payment_id": "pay_883",
    }

    # 1. Post score
    score_resp = test_client.post("/v1/risk/returns/score", json=payload)
    assert score_resp.status_code == 200
    score_data = score_resp.json()
    assert score_data["explanation"]["status"] == "PENDING"

    # 2. Query explanation endpoint immediately (should be PENDING)
    exp_resp1 = test_client.get(f"/v1/risk/returns/{req_id}/explanation")
    assert exp_resp1.status_code == 200
    exp_data1 = exp_resp1.json()
    assert exp_data1["status"] == "PENDING"

    # 3. Run worker to process queued job
    worker = ShapWorker()
    worker.initialize()
    record = worker.process_next(timeout_seconds=1.0)
    assert record is not None
    assert record.request_id == req_id
    assert record.status == "READY"
    assert record.margin_reconstruction_error < 1e-4
    assert len(record.group_attributions) == 6
    assert len(record.reason_codes) >= 1

    # 4. Query explanation endpoint again (should now be READY)
    exp_resp2 = test_client.get(f"/v1/risk/returns/{req_id}/explanation")
    assert exp_resp2.status_code == 200
    exp_data2 = exp_resp2.json()
    assert exp_data2["status"] == "READY"
    assert exp_data2["raw_margin"] == score_data["risk"]["raw_margin"]
    assert len(exp_data2["reason_codes"]) >= 1
    assert "data_confidence" in exp_data2

    # 5. Check persistent disk file
    disk_file = Path("data/explanations") / f"{req_id}.json"
    assert disk_file.exists()

    # 6. Idempotency: re-running process_job should return existing record without recomputing
    job = ExplanationJob(
        request_id=req_id,
        feature_vector={"returns_24h": 4.0},
        raw_margin=record.raw_margin,
        calibrated_probability=record.calibrated_probability,
        decision_action="BLOCK",
        model_version="rr-lgbm-1.0.0",
        calibration_version="cal-1.0",
    )
    cached_record = worker.process_job(job)
    assert cached_record.status == "READY"
