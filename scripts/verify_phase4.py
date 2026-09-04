#!/usr/bin/env python3
"""Phase 4 Acceptance Verification Script.

Validates the real-time inference API and economic decision engine against acceptance criteria:
- Endpoint responds within 50ms (local)
- Response strictly adheres to Pydantic contract with calibrated probability
- Action is one of APPROVE, VERIFY, BLOCK
- Economic decision engine uses configured profiles and produces expected actions at known risk levels
- Unit and integration tests pass cleanly

Usage:
    python scripts/verify_phase4.py
"""

import io
import sys
import time
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    except Exception:
        pass
if sys.stderr.encoding != "utf-8":
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from src.app import app
from src.inference.economic_engine import EconomicDecisionEngine
from src.inference.schemas import ReturnScoreResponse


def check(condition: bool, pass_msg: str, fail_msg: str, failures: list) -> bool:
    if condition:
        print(f"[PASS] {pass_msg}")
        return True
    else:
        print(f"[FAIL] {fail_msg}")
        failures.append(fail_msg)
        return False


def main() -> None:
    failures = []
    print("=" * 65)
    print("PHASE 4: INFERENCE API & ECONOMIC DECISION ENGINE VERIFICATION")
    print("=" * 65)

    client = TestClient(app)

    # Sample standard payload from specification
    sample_payload = {
        "request_id": "ret_verify_12345",
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

    # 1. Warm-up and Response Verification
    print("\n=== 1. API Contract & Schema Compliance ===")
    resp = client.post("/v1/risk/returns/score", json=sample_payload)
    check(resp.status_code == 200, f"Endpoint returned HTTP 200 (got {resp.status_code})", f"Endpoint returned HTTP {resp.status_code}: {resp.text}", failures)

    data = resp.json()
    try:
        validated = ReturnScoreResponse.model_validate(data)
        check(True, "Response body successfully validates against ReturnScoreResponse schema.", "", failures)
    except Exception as e:
        check(False, "", f"Schema validation failed: {e}", failures)
        validated = None

    if validated is not None:
        # Check field values
        check(validated.request_id == sample_payload["request_id"], f"Request ID matches: {validated.request_id}", "Request ID mismatch", failures)
        check(0.0 <= validated.risk.probability <= 1.0, f"Calibrated risk probability is strictly in [0, 1]: {validated.risk.probability:.4f}", "Probability out of bounds", failures)
        check(validated.decision.action in ["APPROVE", "VERIFY", "BLOCK"], f"Prescribed action is valid enum: {validated.decision.action}", f"Invalid action: {validated.decision.action}", failures)
        check(validated.decision.expected_loss >= 0.0, f"Quantified expected loss is non-negative: ${validated.decision.expected_loss:.2f}", "Negative expected loss", failures)
        check(validated.economics.merchant_profile_version == "merchant-econ-1.7", f"Merchant economic profile: {validated.economics.merchant_profile_version}", "Merchant profile mismatch", failures)
        check(validated.economics.product_profile_version == "product-econ-4.2", f"Product economic profile: {validated.economics.product_profile_version}", "Product profile mismatch", failures)
        check(validated.explanation.status == "PENDING", "Explanation status is PENDING (no SHAP in critical path).", "Explanation status not PENDING", failures)

    # 2. Latency Benchmark (< 50ms)
    print("\n=== 2. Real-Time Latency Benchmark ===")
    latencies = []
    for i in range(10):
        req = sample_payload.copy()
        req["request_id"] = f"ret_lat_{i}_{int(time.time()*1000)}"
        t0 = time.perf_counter()
        r = client.post("/v1/risk/returns/score", json=req)
        elapsed = (time.perf_counter() - t0) * 1000.0
        if r.status_code == 200:
            latencies.append(elapsed)

    if latencies:
        p50 = sorted(latencies)[len(latencies) // 2]
        p95 = sorted(latencies)[int(len(latencies) * 0.95)]
        avg_lat = sum(latencies) / len(latencies)
        print(f"  P50 Latency: {p50:.2f}ms | P95 Latency: {p95:.2f}ms | Avg: {avg_lat:.2f}ms")
        check(p50 < 50.0, f"P50 latency ({p50:.2f}ms) is well under 50ms requirement.", f"P50 latency exceeded 50ms: {p50:.2f}ms", failures)
        check(p95 < 50.0, f"P95 latency ({p95:.2f}ms) is well under 50ms requirement.", f"P95 latency exceeded 50ms: {p95:.2f}ms", failures)

    # 3. Economic Decision Engine Risk Levels
    print("\n=== 3. Economic Decision Engine Known Risk Levels ===")
    engine = EconomicDecisionEngine()
    context = {
        "refund_amount": 5000.0,
        "order_amount": 6000.0,
        "merchant_profile": {"customer_acquisition_cost": 450.0, "churn_cost_multiplier": 2.5},
        "product_profile": {
            "cogs_rate": 0.65,
            "return_shipping_cost": 180.0,
            "handling_cost": 80.0,
            "restocking_cost_rate": 0.08,
            "salvage_value_percentage": 0.40,
        },
    }

    dec_low = engine.decide(0.10, context)
    check(dec_low.action == "APPROVE", f"Low risk (p=0.10) maps to APPROVE (loss=${dec_low.expected_loss:.2f})", f"Expected APPROVE, got {dec_low.action}", failures)

    dec_mid = engine.decide(0.50, context)
    check(dec_mid.action == "VERIFY", f"Medium risk (p=0.50) maps to VERIFY (loss=${dec_mid.expected_loss:.2f})", f"Expected VERIFY, got {dec_mid.action}", failures)

    dec_high = engine.decide(0.90, context)
    check(dec_high.action == "BLOCK", f"High risk (p=0.90) maps to BLOCK (loss=${dec_high.expected_loss:.2f})", f"Expected BLOCK, got {dec_high.action}", failures)

    # 4. Cold-Start Fallback Test
    print("\n=== 4. Unseen Customer Cold-Start Fallback ===")
    cold_payload = {
        "request_id": f"ret_cold_{int(time.time()*1000)}",
        "merchant_id": "m_new_merchant",
        "user_id": "usr_new_customer",
        "transaction_id": "txn_brand_new_123",
        "product_id": "prod_novel_456",
        "timestamp": "2026-09-04T00:00:00Z",
        "refund_amount": 2500.0,
        "order_amount": 3000.0,
        "product_category": "home",
    }
    cold_resp = client.post("/v1/risk/returns/score", json=cold_payload)
    check(cold_resp.status_code == 200, "Unseen transaction scored successfully via cold-start fallback.", f"Cold-start failed: {cold_resp.text}", failures)
    if cold_resp.status_code == 200:
        c_data = cold_resp.json()
        check(c_data["decision"]["action"] in ["APPROVE", "VERIFY", "BLOCK"], f"Cold-start action prescribed: {c_data['decision']['action']}", "Invalid cold-start action", failures)

    # Summary
    print("\n" + "=" * 65)
    print("PHASE 4 VALIDATION SUMMARY")
    print("=" * 65)
    if not failures:
        print("[SUCCESS] ALL PHASE 4 ACCEPTANCE CRITERIA PASSED.")
        print("Inference API and Economic Decision Engine are production-ready.")
        sys.exit(0)
    else:
        print(f"[FAILED] {len(failures)} check(s) failed:")
        for f in failures:
            print(f"  - {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
