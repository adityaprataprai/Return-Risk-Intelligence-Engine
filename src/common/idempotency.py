import hashlib
import json
from typing import Any, Dict, Union


def hash_dict_or_str(data: Union[Dict[str, Any], str, bytes]) -> str:
    """Computes SHA-256 hash of a dictionary, string, or bytes payload."""
    if isinstance(data, dict):
        # Deterministic JSON string representation sorted by keys
        serialized = json.dumps(data, sort_keys=True, default=str).encode("utf-8")
    elif isinstance(data, str):
        serialized = data.encode("utf-8")
    else:
        serialized = data
    return hashlib.sha256(serialized).hexdigest()


def generate_idempotency_key(request_id: str, payload_hash: str) -> str:
    """Generates an idempotency key combining request_id and payload_hash."""
    return hashlib.sha256(f"{request_id}:{payload_hash}".encode()).hexdigest()
