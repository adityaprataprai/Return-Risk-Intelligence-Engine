import sys
from pathlib import Path

# Ensure project root and src are in sys.path when running script directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pytest
from fastapi.testclient import TestClient

try:
    from src.app import app
    from src.common.config import Config
    from src.common.idempotency import generate_idempotency_key
    from src.common.observability import increment_counter, get_metrics_snapshot, reset_metrics
    from src.common.utils import utc_now, hash_payload
except ModuleNotFoundError:
    from app import app  # type: ignore
    from common.config import Config  # type: ignore
    from common.idempotency import generate_idempotency_key  # type: ignore
    from common.observability import increment_counter, get_metrics_snapshot, reset_metrics  # type: ignore
    from common.utils import utc_now, hash_payload  # type: ignore


client = TestClient(app)


def test_health_endpoint():
    """Test that the /health endpoint returns 200 and expected payload."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.1.0"


def test_config_loader():
    """Test that Config can load default simulation settings."""
    cfg = Config("simulation/default")
    assert cfg.get("simulation_version") == "0.1.0"
    assert cfg.get("population.num_customers") == 10000
    assert cfg.get("nonexistent.key", default="fallback") == "fallback"


def test_idempotency_key_generation():
    """Test deterministic generation of idempotency keys."""
    key1 = generate_idempotency_key("req_1", "hash_abc")
    key2 = generate_idempotency_key("req_1", "hash_abc")
    key3 = generate_idempotency_key("req_2", "hash_abc")
    assert key1 == key2
    assert key1 != key3


def test_observability_stubs():
    """Test that observability helpers record metric events."""
    reset_metrics()
    increment_counter("test_counter", 2.0)
    snapshot = get_metrics_snapshot()
    assert snapshot["counters"]["test_counter"] == 2.0


def test_utils_hashing_and_time():
    """Test time and hashing utilities."""
    now = utc_now()
    assert now.tzinfo is not None
    payload_hash = hash_payload({"user_id": "usr_123", "amount": 100})
    assert len(payload_hash) == 64


if __name__ == "__main__":
    print("Running tests in test_health.py directly...")
    test_health_endpoint()
    print("  [PASSED] test_health_endpoint")
    test_config_loader()
    print("  [PASSED] test_config_loader")
    test_idempotency_key_generation()
    print("  [PASSED] test_idempotency_key_generation")
    test_observability_stubs()
    print("  [PASSED] test_observability_stubs")
    test_utils_hashing_and_time()
    print("  [PASSED] test_utils_hashing_and_time")
    print("\nAll 5 tests passed successfully!")

