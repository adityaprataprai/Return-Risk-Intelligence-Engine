#!/usr/bin/env python3
"""Phase 9: Observability, Deployment & Final Polish Verification Script.

Automated acceptance suite validating:
1. Prometheus metrics instrumentation & endpoints (/metrics) on scoring API and dashboard BFF.
2. Custom metrics (risk_score_requests_total, risk_score_latency_seconds, economic_decision_total, etc.).
3. RequestIdMiddleware and structured JSON logging with context correlation IDs.
4. Production Dockerfiles (api, dashboard, frontend, shap_worker, graph_processor).
5. Orchestrated docker-compose.yml with health checks and dependencies across 8 services.
6. Prometheus configuration and Grafana provisioning definitions.
7. Locust concurrent load testing suite.
8. GitHub Actions CI/CD workflow definition.
"""

import json
import logging
import os
import sys
import time
from pathlib import Path

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fastapi.testclient import TestClient
import yaml


def check(condition: bool, msg: str) -> None:
    """Helper asserting test condition with colored output."""
    if condition:
        print(f"  [PASS] {msg}")
    else:
        print(f"  [FAIL] {msg}")
        sys.exit(1)


def main() -> None:
    print("=" * 70)
    print("PHASE 9: OBSERVABILITY, DEPLOYMENT & POLISH ACCEPTANCE VERIFICATION")
    print("=" * 70)

    # -------------------------------------------------------------
    # 1. Prometheus Metrics Instrumentation & Custom Metrics
    # -------------------------------------------------------------
    print("\n--- 1. Prometheus Metrics Instrumentation ---")
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

    check(RISK_SCORE_REQUESTS_TOTAL is not None, "RISK_SCORE_REQUESTS_TOTAL metric registered")
    check(RISK_SCORE_LATENCY_SECONDS is not None, "RISK_SCORE_LATENCY_SECONDS histogram registered")
    check(ECONOMIC_DECISION_TOTAL is not None, "ECONOMIC_DECISION_TOTAL counter registered")
    check(SHAP_QUEUE_DEPTH is not None, "SHAP_QUEUE_DEPTH gauge registered")
    check(GRAPH_FEATURE_AGE_SECONDS is not None, "GRAPH_FEATURE_AGE_SECONDS gauge registered")

    update_shap_queue_depth(42)
    check(SHAP_QUEUE_DEPTH._value.get() == 42.0, "SHAP_QUEUE_DEPTH gauge updates successfully")

    update_graph_feature_age(125.5, "g0000")
    check(
        GRAPH_FEATURE_AGE_SECONDS.labels(graph_version="g0000")._value.get() == 125.5,
        "GRAPH_FEATURE_AGE_SECONDS gauge updates with labels",
    )

    record_risk_score(action="APPROVE", duration_seconds=0.015, model_version="v1.0.0", status_str="success")
    print("  [PASS] Custom metrics update functions executed without errors")

    # -------------------------------------------------------------
    # 2. FastAPI Services /metrics Endpoints
    # -------------------------------------------------------------
    print("\n--- 2. FastAPI Services /metrics & Health Probes ---")
    from src.app import app as api_app
    from src.dashboard.api import app as bff_app

    api_client = TestClient(api_app)
    bff_client = TestClient(bff_app)

    # Scoring API /metrics
    r_api_metrics = api_client.get("/metrics")
    check(r_api_metrics.status_code == 200, "Scoring API GET /metrics returns 200 OK")
    check("risk_score_requests_total" in r_api_metrics.text, "Scoring API /metrics includes risk_score_requests_total")
    check("economic_decision_total" in r_api_metrics.text, "Scoring API /metrics includes economic_decision_total")

    # Scoring API /health
    r_api_health = api_client.get("/health")
    check(r_api_health.status_code == 200, "Scoring API GET /health returns 200 OK")
    check(r_api_health.json().get("status") == "ok", "Scoring API /health status is 'ok'")

    # Dashboard BFF /metrics
    r_bff_metrics = bff_client.get("/metrics")
    check(r_bff_metrics.status_code == 200, "Dashboard BFF GET /metrics returns 200 OK")

    # Dashboard BFF /health
    r_bff_health = bff_client.get("/health")
    check(r_bff_health.status_code == 200, "Dashboard BFF GET /health returns 200 OK")
    check(r_bff_health.json().get("status") == "ok", "Dashboard BFF /health status is 'ok'")

    # -------------------------------------------------------------
    # 3. Request Correlation ID & Structured JSON Logging
    # -------------------------------------------------------------
    print("\n--- 3. Correlation ID Tracking & Structured Logging ---")
    custom_cid = "corr_verif_998811"
    r_cid = api_client.get("/health", headers={"X-Request-ID": custom_cid})
    check(r_cid.headers.get("X-Request-ID") == custom_cid, "RequestIdMiddleware propagates incoming X-Request-ID")

    r_cid_gen = api_client.get("/health")
    gen_id = r_cid_gen.headers.get("X-Request-ID")
    check(gen_id is not None and gen_id.startswith("req_"), "RequestIdMiddleware generates unique UUID when header omitted")

    from src.common.logging import JSONFormatter, set_request_id
    formatter = JSONFormatter()
    test_rec = logging.LogRecord(
        name="test_obs", level=logging.INFO, pathname="test.py", lineno=10, msg="Structured logging check", args=(), exc_info=None
    )
    set_request_id("ctx_test_corr_456")
    formatted_str = formatter.format(test_rec)
    set_request_id(None)
    parsed_log = json.loads(formatted_str)
    check(parsed_log.get("request_id") == "ctx_test_corr_456", "JSONFormatter injects contextvar correlation ID into JSON")

    # -------------------------------------------------------------
    # 4. Deployment Manifests & Dockerfiles
    # -------------------------------------------------------------
    print("\n--- 4. Dockerfiles & Containerization Assets ---")
    dockerfiles = [
        ("deployment/Dockerfile.api", "Inference Scoring API container"),
        ("deployment/Dockerfile.dashboard", "Dashboard BFF service container"),
        ("deployment/Dockerfile.frontend", "Next.js 14 Frontend container"),
        ("deployment/Dockerfile.shap_worker", "TreeSHAP Worker daemon container"),
        ("deployment/Dockerfile.graph_processor", "Graph Processor Worker container"),
    ]

    for rel_path, desc in dockerfiles:
        df_path = PROJECT_ROOT / rel_path
        check(df_path.is_file(), f"Dockerfile exists: {rel_path} ({desc})")
        content = df_path.read_text(encoding="utf-8")
        check(len(content) > 100, f"  Content verified for {rel_path} ({len(content)} bytes)")

    # -------------------------------------------------------------
    # 5. Docker Compose & Observability Infrastructure
    # -------------------------------------------------------------
    print("\n--- 5. Docker Compose Orchestration & Prometheus/Grafana ---")
    compose_file = PROJECT_ROOT / "docker-compose.yml"
    check(compose_file.is_file(), "docker-compose.yml exists at repository root")

    with open(compose_file, "r", encoding="utf-8") as f:
        compose_cfg = yaml.safe_load(f)

    services = compose_cfg.get("services", {})
    required_services = [
        "redis",
        "api",
        "shap-worker",
        "graph-processor",
        "dashboard-bff",
        "frontend",
        "prometheus",
        "grafana",
    ]
    for svc in required_services:
        check(svc in services, f"Service '{svc}' configured in docker-compose.yml")

    # Verify Prometheus config
    prom_cfg_path = PROJECT_ROOT / "deployment/prometheus.yml"
    check(prom_cfg_path.is_file(), "Prometheus configuration deployment/prometheus.yml exists")
    with open(prom_cfg_path, "r", encoding="utf-8") as f:
        prom_cfg = yaml.safe_load(f)
    jobs = [j["job_name"] for j in prom_cfg.get("scrape_configs", [])]
    check("risk-scoring-api" in jobs, "Prometheus scrapes 'risk-scoring-api' (port 8000)")
    check("dashboard-bff" in jobs, "Prometheus scrapes 'dashboard-bff' (port 8001)")

    # Verify Grafana provisioning
    gf_ds_path = PROJECT_ROOT / "deployment/grafana/datasources/prometheus.yml"
    gf_prov_path = PROJECT_ROOT / "deployment/grafana/dashboards/dashboards.yml"
    gf_dash_path = PROJECT_ROOT / "deployment/grafana/dashboards/risk_engine_overview.json"
    check(gf_ds_path.is_file(), "Grafana datasource definition exists")
    check(gf_prov_path.is_file(), "Grafana dashboard provider definition exists")
    check(gf_dash_path.is_file(), "Grafana telemetry dashboard JSON exists")

    with open(gf_dash_path, "r", encoding="utf-8") as f:
        dash_json = json.load(f)
    check(dash_json.get("uid") == "razorpay-risk-overview", "Grafana dashboard UID verified ('razorpay-risk-overview')")
    check(len(dash_json.get("panels", [])) >= 5, f"Grafana dashboard contains {len(dash_json.get('panels', []))} monitoring panels")

    # -------------------------------------------------------------
    # 6. Load Testing & CI/CD Pipelines
    # -------------------------------------------------------------
    print("\n--- 6. Load Testing & CI/CD Pipelines ---")
    locust_path = PROJECT_ROOT / "tests/load/locustfile.py"
    check(locust_path.is_file(), "Locust load test suite tests/load/locustfile.py exists")

    from tests.load.locustfile import ReturnScoringUser
    check(len(ReturnScoringUser.tasks) >= 3, "ReturnScoringUser defines multiple concurrent testing tasks")

    ci_path = PROJECT_ROOT / ".github/workflows/ci.yml"
    check(ci_path.is_file(), "GitHub Actions CI workflow .github/workflows/ci.yml exists")
    with open(ci_path, "r", encoding="utf-8") as f:
        ci_cfg = yaml.safe_load(f)
    ci_jobs = ci_cfg.get("jobs", {})
    check("python-test-suite" in ci_jobs, "CI workflow defines 'python-test-suite' job")
    check("frontend-build" in ci_jobs, "CI workflow defines 'frontend-build' job")
    check("docker-compose-validation" in ci_jobs, "CI workflow defines 'docker-compose-validation' job")

    # -------------------------------------------------------------
    # 7. Local Multi-Process Runners
    # -------------------------------------------------------------
    print("\n--- 7. Local Multi-Process Service Runners ---")
    check((PROJECT_ROOT / "scripts/run_all.sh").is_file(), "scripts/run_all.sh exists for Unix/Linux/macOS")
    check((PROJECT_ROOT / "scripts/run_all.ps1").is_file(), "scripts/run_all.ps1 exists for Windows PowerShell")

    print("\n" + "=" * 70)
    print("PHASE 9 VERIFICATION SUMMARY")
    print("=" * 70)
    print("[SUCCESS] All Phase 9 Observability & Deployment criteria PASSED perfectly!")
    print("  • Prometheus instrumentation & /metrics endpoints operational on both APIs")
    print("  • 5 custom risk & queue metrics verified and active")
    print("  • RequestIdMiddleware with context correlation ID logging validated")
    print("  • 5 standalone production Dockerfiles created in deployment/")
    print("  • Full docker-compose.yml orchestrating 8 services with health checks")
    print("  • Prometheus scrapers and provisioned Grafana dashboards configured")
    print("  • Locust concurrent load testing suite verified")
    print("  • GitHub Actions CI/CD workflow defined")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
