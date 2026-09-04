from typing import Any, Dict, Optional
import logging

logger = logging.getLogger("observability")

# In-memory metrics storage for testing and dev telemetry
_METRICS_STORE: Dict[str, Any] = {
    "counters": {},
    "gauges": {},
    "latencies": {},
}


def increment_counter(name: str, value: float = 1.0, tags: Optional[Dict[str, str]] = None) -> None:
    """Increments a counter metric (placeholder for Prometheus)."""
    current = _METRICS_STORE["counters"].get(name, 0.0)
    _METRICS_STORE["counters"][name] = current + value
    logger.debug(f"[Metric] Counter {name} += {value} (tags={tags})")


def record_latency(name: str, seconds: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Records a latency observation (placeholder for Prometheus histogram/summary)."""
    if name not in _METRICS_STORE["latencies"]:
        _METRICS_STORE["latencies"][name] = []
    _METRICS_STORE["latencies"][name].append(seconds)
    logger.debug(f"[Metric] Latency {name} = {seconds:.4f}s (tags={tags})")


def set_gauge(name: str, value: float, tags: Optional[Dict[str, str]] = None) -> None:
    """Sets a gauge metric value."""
    _METRICS_STORE["gauges"][name] = value
    logger.debug(f"[Metric] Gauge {name} = {value} (tags={tags})")


def get_metrics_snapshot() -> Dict[str, Any]:
    """Returns a snapshot of in-memory metrics (useful for testing)."""
    return {
        "counters": dict(_METRICS_STORE["counters"]),
        "gauges": dict(_METRICS_STORE["gauges"]),
        "latencies": {k: list(v) for k, v in _METRICS_STORE["latencies"].items()},
    }


def reset_metrics() -> None:
    """Resets in-memory metrics."""
    _METRICS_STORE["counters"].clear()
    _METRICS_STORE["gauges"].clear()
    _METRICS_STORE["latencies"].clear()
