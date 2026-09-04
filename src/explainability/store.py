"""Explanation persistence: Dual-layer storage (Redis cache + immutable disk JSON)."""

import json
from pathlib import Path
from typing import Any, Optional, Union
from src.common.logging import get_logger
from .schemas import ExplanationRecord

logger = get_logger("explainability.store")

EXPLANATION_KEY_PREFIX = "risk:explanation:"
DEFAULT_DATA_DIR = Path("data/explanations")


class ExplanationStore:
    """Provides atomic, immutable persistence and low-latency retrieval for explanation records."""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        data_dir: Union[str, Path] = DEFAULT_DATA_DIR,
        ttl_seconds: int = 86400 * 7,  # 7 days in Redis
    ):
        if redis_client is None:
            from src.inference.redis_client import RedisClient
            self.redis = RedisClient()
        else:
            self.redis = redis_client
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds

    def _redis_key(self, request_id: str) -> str:
        return f"{EXPLANATION_KEY_PREFIX}{request_id}"

    def _file_path(self, request_id: str) -> Path:
        # Sanitize filename
        safe_id = "".join(c for c in request_id if c.isalnum() or c in ("-", "_"))
        return self.data_dir / f"{safe_id}.json"

    def record_pending(self, request_id: str) -> bool:
        """Writes initial PENDING record to Redis so retrieval endpoint can confirm in-progress state."""
        try:
            pending_record = {
                "request_id": request_id,
                "status": "PENDING",
            }
            return self.redis.set_json(self._redis_key(request_id), pending_record, ttl_seconds=self.ttl_seconds)
        except Exception as e:
            logger.warning(f"Failed to record pending explanation state for {request_id}: {e}")
            return False

    def save_explanation(self, record: ExplanationRecord) -> bool:
        """Saves completed explanation record to disk and Redis cache."""
        try:
            data = record.model_dump(mode="json")

            # 1. Write to immutable JSON file
            filepath = self._file_path(record.request_id)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            # 2. Write to Redis cache
            self.redis.set_json(self._redis_key(record.request_id), data, ttl_seconds=self.ttl_seconds)

            logger.info(f"Successfully persisted explanation for request_id={record.request_id} to disk and Redis.")
            return True
        except Exception as e:
            logger.error(f"Failed to save explanation record for {record.request_id}: {e}", exc_info=True)
            return False

    def get_explanation(self, request_id: str) -> Optional[ExplanationRecord]:
        """Retrieves explanation record from Redis or falls back to disk file."""
        # 1. Try Redis cache first (sub-millisecond)
        try:
            cached = self.redis.get_json(self._redis_key(request_id))
            if cached is not None:
                # If cached is just a pending stub
                if cached.get("status") == "PENDING" and "group_attributions" not in cached:
                    return ExplanationRecord(
                        request_id=request_id,
                        status="PENDING",
                    )
                return ExplanationRecord.model_validate(cached)
        except Exception as e:
            logger.debug(f"Redis cache lookup failed for explanation {request_id}: {e}")

        # 2. Fall back to disk file
        filepath = self._file_path(request_id)
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    disk_data = json.load(f)
                record = ExplanationRecord.model_validate(disk_data)
                # Repopulate Redis cache
                self.redis.set_json(self._redis_key(request_id), disk_data, ttl_seconds=self.ttl_seconds)
                return record
            except Exception as e:
                logger.error(f"Failed to read explanation file {filepath}: {e}")

        return None

    def exists(self, request_id: str) -> bool:
        """Checks if an explanation record exists on disk or in Redis."""
        return self._file_path(request_id).exists() or bool(self.redis.client.exists(self._redis_key(request_id)))
