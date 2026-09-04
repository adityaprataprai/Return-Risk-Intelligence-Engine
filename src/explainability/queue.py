"""Asynchronous explanation queue backed by Redis with in-memory fallback."""

import json
import time
from typing import Any, Optional
from src.common.logging import get_logger
from .schemas import ExplanationJob

logger = get_logger("explainability.queue")

EXPLANATION_QUEUE_KEY = "risk:queue:explanations"


class ExplanationQueue:
    """FIFO queue for asynchronous TreeSHAP explanation workloads."""

    def __init__(
        self,
        redis_client: Optional[Any] = None,
        queue_key: str = EXPLANATION_QUEUE_KEY,
    ):
        if redis_client is None:
            from src.inference.redis_client import RedisClient
            self.redis = RedisClient()
        else:
            self.redis = redis_client
        self.queue_key = queue_key

    def enqueue(self, job: ExplanationJob) -> bool:
        """Pushes an explanation job to the tail of the queue."""
        try:
            payload = job.model_dump_json()
            self.redis.client.rpush(self.queue_key, payload)
            logger.debug(f"Enqueued explanation job for request_id={job.request_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to enqueue explanation job for {job.request_id}: {e}")
            return False

    def dequeue(self, timeout_seconds: float = 0.5) -> Optional[ExplanationJob]:
        """Pops an explanation job from the head of the queue.

        Uses polling with timeout if blocking pop is not directly available.
        """
        start = time.perf_counter()
        while True:
            try:
                raw = self.redis.client.lpop(self.queue_key)
                if raw is not None:
                    data = json.loads(raw)
                    return ExplanationJob.model_validate(data)
            except Exception as e:
                logger.error(f"Error dequeueing explanation job: {e}")
                return None

            elapsed = time.perf_counter() - start
            if elapsed >= timeout_seconds:
                return None
            time.sleep(0.05)

    def size(self) -> int:
        """Returns the number of queued explanation jobs."""
        try:
            return int(self.redis.client.llen(self.queue_key))
        except Exception:
            return 0

    def clear(self) -> None:
        """Clears all pending jobs in the queue."""
        try:
            self.redis.client.delete(self.queue_key)
        except Exception as e:
            logger.warning(f"Error clearing queue {self.queue_key}: {e}")
