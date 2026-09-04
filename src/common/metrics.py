"""Prometheus metrics definitions and instrumentation for Razorpay Return-Risk Intelligence Engine."""

from typing import Optional
from fastapi import FastAPI
from prometheus_client import (
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
)
from prometheus_fastapi_instrumentator import Instrumentator

from src.common.logging import get_logger

logger = get_logger("common.metrics")


def _get_or_create_metric(metric_cls, name, documentation, *args, **kwargs):
    """Retrieves an existing metric from the Prometheus REGISTRY or registers a new one."""
    if name in REGISTRY._names_to_collectors:
        collector = REGISTRY._names_to_collectors[name]
        return collector
    return metric_cls(name, documentation, *args, **kwargs)


# 1. Core Risk Score Request Counter
RISK_SCORE_REQUESTS_TOTAL = _get_or_create_metric(
    Counter,
    "risk_score_requests_total",
    "Total number of return scoring requests processed",
    ["status", "action", "model_version"],
)

# 2. Return Scoring Latency Histogram (fine-grained sub-second buckets for sub-50ms SLA)
RISK_SCORE_LATENCY_SECONDS = _get_or_create_metric(
    Histogram,
    "risk_score_latency_seconds",
    "Latency of return scoring execution in seconds",
    ["action"],
    buckets=[0.005, 0.01, 0.02, 0.03, 0.05, 0.075, 0.1, 0.25, 0.5, 1.0, 2.5],
)

# 3. Economic Decision Counter Partitioned by Action (APPROVE, VERIFY, BLOCK)
ECONOMIC_DECISION_TOTAL = _get_or_create_metric(
    Counter,
    "economic_decision_total",
    "Total economic decisions partitioned by action",
    ["action"],
)

# 4. Asynchronous TreeSHAP Queue Depth Gauge
SHAP_QUEUE_DEPTH = _get_or_create_metric(
    Gauge,
    "shap_queue_depth",
    "Current number of pending TreeSHAP explanation jobs in queue",
)

# 5. Graph Feature Age Gauge (tracks graph staleness in seconds)
GRAPH_FEATURE_AGE_SECONDS = _get_or_create_metric(
    Gauge,
    "graph_feature_age_seconds",
    "Age of online identity graph features in seconds",
    ["graph_version"],
)


def record_risk_score(
    action: str,
    duration_seconds: float,
    model_version: str = "v1.0.0",
    status_str: str = "success",
) -> None:
    """Convenience helper to update scoring metrics atomically."""
    try:
        RISK_SCORE_REQUESTS_TOTAL.labels(
            status=status_str, action=action, model_version=model_version
        ).inc()
        RISK_SCORE_LATENCY_SECONDS.labels(action=action).observe(duration_seconds)
        ECONOMIC_DECISION_TOTAL.labels(action=action).inc()
    except Exception as e:
        logger.warning(f"Error recording risk score metrics: {e}")


def update_shap_queue_depth(depth: int) -> None:
    """Updates the TreeSHAP queue depth gauge."""
    try:
        SHAP_QUEUE_DEPTH.set(float(depth))
    except Exception as e:
        logger.warning(f"Error updating SHAP queue depth metric: {e}")


def update_graph_feature_age(age_seconds: float, graph_version: str = "g0000") -> None:
    """Updates the online graph feature age gauge."""
    try:
        GRAPH_FEATURE_AGE_SECONDS.labels(graph_version=graph_version).set(float(age_seconds))
    except Exception as e:
        logger.warning(f"Error updating graph feature age metric: {e}")


def setup_metrics(app: FastAPI, app_name: str = "risk-engine-api") -> Instrumentator:
    """Instruments a FastAPI application with Prometheus metrics and exposes /metrics endpoint."""
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        excluded_handlers=["/metrics", "/health"],
        env_var_name="ENABLE_METRICS",
    )

    # Instrument app
    instrumentator.instrument(app)

    # Expose /metrics endpoint
    instrumentator.expose(app, endpoint="/metrics", include_in_schema=True, tags=["Observability"])

    logger.info(f"Prometheus metrics initialized on {app_name} at /metrics")
    return instrumentator
