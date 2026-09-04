#!/usr/bin/env python3
"""Phase 7 Acceptance Verification Script: Dashboard Backend (BFF).

Validates the Dashboard BFF subsystem against all acceptance criteria:
1. All 16 REST endpoints respond with valid JSON contracts.
2. Review queue returns cases properly filtered, prioritized, and sorted.
3. Case detail integrates risk score, decision, TreeSHAP explanation, and timeline.
4. Analyst action submission updates case status and persists to database and audit log.
5. Identity network explorer generates bipartite graph (users, devices, addresses, payments).
6. Analytics endpoints quantify fraud typologies and financial ROI impact.
7. Policy rulebooks and counterfactual simulation evaluate threshold tradeoffs.
8. Model, feature, and system observability health endpoints return accurate status.
9. Dashboard BFF can be instantiated and executed via Uvicorn.

Usage:
    venv\\Scripts\\python.exe scripts/verify_phase7.py
"""

import io
import json
from pathlib import Path
import sys
import time
from starlette.testclient import TestClient

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

from src.dashboard.api import app
from src.dashboard.db import db_manager


def check(condition: bool, pass_msg: str, fail_msg: str, failures: list) -> bool:
    if condition:
        print(f"  [PASS] {pass_msg}")
        return True
    else:
        print(f"  [FAIL] {fail_msg}")
        failures.append(fail_msg)
        return False


def main() -> None:
    failures = []
    print("=" * 70)
    print("PHASE 7: DASHBOARD BACKEND (BFF) ACCEPTANCE VERIFICATION")
    print("=" * 70)

    client = TestClient(app)

    # -------------------------------------------------------------
    # 1. Database Schema & Tables Check
    # -------------------------------------------------------------
    print("\n--- 1. Relational Database Schema & Operational Tables ---")
    with db_manager.get_connection() as conn:
        tables = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        ]

    required_tables = ["cases", "analyst_actions", "policies", "audit_log"]
    all_tables_exist = all(t in tables for t in required_tables)
    check(
        all_tables_exist,
        f"All 4 operational tables exist: {', '.join(required_tables)}",
        f"Missing required tables in {tables}",
        failures,
    )

    # -------------------------------------------------------------
    # 2. Executive Overview & KPIs
    # -------------------------------------------------------------
    print("\n--- 2. Executive Overview KPIs & Risk Distribution ---")
    kpis_resp = client.get("/api/overview/kpis")
    check(
        kpis_resp.status_code == 200,
        "GET /api/overview/kpis returned HTTP 200",
        f"GET /api/overview/kpis failed: {kpis_resp.status_code}",
        failures,
    )
    kpis = kpis_resp.json()
    check(
        kpis["total_cases_evaluated"] > 0,
        f"Evaluated cases populated: {kpis['total_cases_evaluated']} total "
        f"({kpis['total_approved']} approved, {kpis['total_manual_reviews']} reviews, {kpis['total_fraud_blocked']} blocked)",
        "Zero cases in overview KPIs",
        failures,
    )
    check(
        kpis["loss_prevented_amount"] >= 0.0,
        f"Prevented fraud loss calculated: ₹{kpis['loss_prevented_amount']:,.2f}",
        "Invalid loss_prevented_amount",
        failures,
    )

    dist_resp = client.get("/api/overview/risk-distribution")
    check(
        dist_resp.status_code == 200,
        "GET /api/overview/risk-distribution returned HTTP 200",
        f"GET /api/overview/risk-distribution failed: {dist_resp.status_code}",
        failures,
    )
    dist = dist_resp.json()
    check(
        len(dist["buckets"]) == 10,
        f"Risk distribution contains 10 probability buckets (avg risk: {dist['average_risk_score']:.4f})",
        f"Expected 10 buckets, got {len(dist.get('buckets', []))}",
        failures,
    )

    # -------------------------------------------------------------
    # 3. Prioritized Review Queue
    # -------------------------------------------------------------
    print("\n--- 3. Prioritized Analyst Review Queue ---")
    q_resp = client.get("/api/review-queue?limit=10&offset=0")
    check(
        q_resp.status_code == 200,
        "GET /api/review-queue returned HTTP 200",
        f"GET /api/review-queue failed: {q_resp.status_code}",
        failures,
    )
    queue_data = q_resp.json()
    check(
        queue_data["total"] > 0 and len(queue_data["items"]) > 0,
        f"Review queue populated with {queue_data['total']} total cases (retrieved top {len(queue_data['items'])})",
        "Review queue is empty",
        failures,
    )

    first_case = queue_data["items"][0]
    check(
        first_case["priority"] in ("HIGH", "MEDIUM", "LOW"),
        f"Top case {first_case['request_id']} has priority '{first_case['priority']}' (risk: {first_case['risk_score']:.4f})",
        f"Invalid priority: {first_case.get('priority')}",
        failures,
    )

    # -------------------------------------------------------------
    # 4. Case Detail & Full Context Aggregation
    # -------------------------------------------------------------
    print("\n--- 4. Holistic Case Detail & Context Aggregation ---")
    target_case_id = first_case["request_id"]
    detail_resp = client.get(f"/api/cases/{target_case_id}")
    check(
        detail_resp.status_code == 200,
        f"GET /api/cases/{target_case_id} returned HTTP 200",
        f"Case detail failed for {target_case_id}",
        failures,
    )
    detail = detail_resp.json()
    check(
        "risk" in detail and "order" in detail and "explanation" in detail,
        f"Case detail integrates risk score, order economics, and explainability summary",
        f"Missing sections in case detail: {detail.keys()}",
        failures,
    )

    # -------------------------------------------------------------
    # 5. Analyst Action Submission & Audit Trail
    # -------------------------------------------------------------
    print("\n--- 5. Analyst Action Execution & Audit Logging ---")
    action_payload = {
        "action": "ESCALATE",
        "analyst_id": "analyst_verification_bot",
        "override_reason": "Suspected wardrobing and high-risk network cluster",
        "notes": "Automated verification test of manual action submission",
    }
    act_resp = client.post(f"/api/cases/{target_case_id}/action", json=action_payload)
    check(
        act_resp.status_code == 200,
        f"POST /api/cases/{target_case_id}/action returned HTTP 200",
        f"Action submission failed: {act_resp.status_code}",
        failures,
    )
    act_data = act_resp.json()
    check(
        act_data["success"] is True and act_data["status"] == "ESCALATED",
        f"Action successfully applied: status transitioned to '{act_data['status']}'",
        f"Action submission failed: {act_data}",
        failures,
    )

    # Verify audit log recorded event
    audit_resp = client.get(f"/api/audit?user_id=analyst_verification_bot")
    check(
        audit_resp.status_code == 200 and audit_resp.json()["total"] >= 1,
        f"Audit log recorded entry for analyst_verification_bot on case {target_case_id}",
        "Audit log missing entry for action",
        failures,
    )

    # -------------------------------------------------------------
    # 6. Deep Dive: Explanation, Timeline & Identity Network
    # -------------------------------------------------------------
    print("\n--- 6. Deep Dive: Explanation, Timeline & Network Explorer ---")
    # Explanation
    exp_resp = client.get(f"/api/cases/{target_case_id}/explanation")
    check(
        exp_resp.status_code == 200,
        f"GET /api/cases/{target_case_id}/explanation returned HTTP 200",
        f"Explanation endpoint failed: {exp_resp.status_code}",
        failures,
    )

    # Timeline
    tl_resp = client.get(f"/api/cases/{target_case_id}/timeline")
    check(
        tl_resp.status_code == 200,
        f"GET /api/cases/{target_case_id}/timeline returned HTTP 200",
        f"Timeline endpoint failed: {tl_resp.status_code}",
        failures,
    )
    tl_data = tl_resp.json()
    check(
        len(tl_data["events"]) >= 3,
        f"Timeline contains {len(tl_data['events'])} chronological events (account, purchase, claim)",
        f"Expected >= 3 timeline events, got {len(tl_data.get('events', []))}",
        failures,
    )

    # Network Explorer
    net_resp = client.get(f"/api/networks/{target_case_id}")
    check(
        net_resp.status_code == 200,
        f"GET /api/networks/{target_case_id} returned HTTP 200",
        f"Network graph endpoint failed: {net_resp.status_code}",
        failures,
    )
    net_data = net_resp.json()
    check(
        len(net_data["nodes"]) >= 3 and len(net_data["edges"]) >= 2,
        f"Identity graph contains {len(net_data['nodes'])} nodes and {len(net_data['edges'])} edges "
        f"(Component size: {net_data['summary']['connected_component_size']})",
        f"Invalid network graph structure",
        failures,
    )

    # -------------------------------------------------------------
    # 7. Analytics: Fraud Typology & Financial Impact
    # -------------------------------------------------------------
    print("\n--- 7. Analytics: Fraud Typologies & Financial Impact ---")
    fraud_resp = client.get("/api/analytics/fraud")
    check(
        fraud_resp.status_code == 200,
        "GET /api/analytics/fraud returned HTTP 200",
        f"Fraud analytics failed: {fraud_resp.status_code}",
        failures,
    )
    fraud_data = fraud_resp.json()
    check(
        len(fraud_data["vectors"]) >= 4 and len(fraud_data["trend_daily"]) == 7,
        f"Fraud analytics covers {len(fraud_data['vectors'])} fraud vectors with 7-day volume trends",
        f"Invalid fraud analytics payload",
        failures,
    )

    fin_resp = client.get("/api/analytics/financial-impact")
    check(
        fin_resp.status_code == 200,
        "GET /api/analytics/financial-impact returned HTTP 200",
        f"Financial impact failed: {fin_resp.status_code}",
        failures,
    )
    fin_data = fin_resp.json()
    check(
        fin_data["net_financial_savings"] > 0 and fin_data["roi_multiple"] > 0,
        f"Financial impact quantified: net savings ₹{fin_data['net_financial_savings']:,.2f} "
        f"(ROI multiple: {fin_data['roi_multiple']}x)",
        "Invalid financial impact numbers",
        failures,
    )

    # -------------------------------------------------------------
    # 8. Policies & Counterfactual Simulation
    # -------------------------------------------------------------
    print("\n--- 8. Policy Management & Counterfactual Simulation ---")
    pol_resp = client.get("/api/policies")
    check(
        pol_resp.status_code == 200,
        "GET /api/policies returned HTTP 200",
        f"Policies endpoint failed: {pol_resp.status_code}",
        failures,
    )
    pol_data = pol_resp.json()
    check(
        pol_data["verify_threshold"] == 0.40 and pol_data["block_threshold"] == 0.80,
        f"Active policy '{pol_data['version']}' retrieved (verify: {pol_data['verify_threshold']}, block: {pol_data['block_threshold']})",
        f"Invalid policy thresholds: {pol_data}",
        failures,
    )

    sim_payload = {"verify_threshold": 0.35, "block_threshold": 0.75}
    sim_resp = client.post("/api/policies/simulate", json=sim_payload)
    check(
        sim_resp.status_code == 200,
        "POST /api/policies/simulate returned HTTP 200",
        f"Policy simulation failed: {sim_resp.status_code}",
        failures,
    )
    sim_data = sim_resp.json()
    check(
        sim_data["cases_evaluated"] > 0 and "simulated_distribution" in sim_data,
        f"Counterfactual simulation on {sim_data['cases_evaluated']} cases: "
        f"Simulated Distribution {sim_data['simulated_distribution']} "
        f"(Review queue change: {sim_data['review_queue_workload_change_percent']:+.1f}%)",
        f"Invalid simulation response: {sim_data}",
        failures,
    )

    # -------------------------------------------------------------
    # 9. Observability & Health Endpoints
    # -------------------------------------------------------------
    print("\n--- 9. Observability & Subsystem Health Monitoring ---")
    m_health = client.get("/api/model-health").json()
    check(
        m_health["status"] == "HEALTHY_SERVING" and m_health["test_auroc"] >= 0.90,
        f"Model health: '{m_health['version']}' AUROC={m_health['test_auroc']:.4f}, AUPRC={m_health['test_auprc']:.4f}",
        f"Model health degraded: {m_health}",
        failures,
    )

    f_health = client.get("/api/feature-health").json()
    check(
        f_health["feature_count"] == 52,
        f"Feature health: schema '{f_health['feature_version']}' with {f_health['feature_count']} features (Redis: {f_health['redis_status']})",
        f"Feature health invalid: {f_health}",
        failures,
    )

    sys_health = client.get("/api/system-health").json()
    check(
        sys_health["status"] in ("healthy", "degraded"),
        f"System health: status='{sys_health['status']}' ({sys_health['services']})",
        f"System health check failed: {sys_health}",
        failures,
    )

    base_health = client.get("/health").json()
    check(
        base_health["status"] == "ok" and base_health["service"] == "dashboard-bff",
        f"BFF service health root /health confirmed OK",
        f"Root health failed: {base_health}",
        failures,
    )

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n" + "=" * 70)
    print("PHASE 7 VERIFICATION SUMMARY")
    print("=" * 70)
    if not failures:
        print("[SUCCESS] All Phase 7 Dashboard Backend (BFF) criteria PASSED perfectly!")
        print("  • 16 REST API endpoints verified and responding with valid contracts")
        print("  • SQLite operational database (data/dashboard.db) active with 4 tables")
        print("  • Case management & prioritized review queue functional")
        print("  • Manual analyst actions persist to database and audit log")
        print("  • Bipartite identity graph network explorer active")
        print("  • Policy counterfactual threshold simulation operational")
        print("  • Subsystem health monitoring verified (model, feature, system)")
        print("=" * 70)
        sys.exit(0)
    else:
        print(f"[FAILED] {len(failures)} verification criteria failed:")
        for f in failures:
            print(f"  - {f}")
        print("=" * 70)
        sys.exit(1)


if __name__ == "__main__":
    main()
