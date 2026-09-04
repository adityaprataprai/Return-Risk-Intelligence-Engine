"""Redis client implementation for Phase 5 online feature state and graph metrics.

Connects to a live Redis server when available, or transparently provisions a high-speed in-process
FakeRedis instance when an external Redis server daemon is not running.
"""

import json
import os
import socket
from typing import Any, Dict, List, Optional
import redis
from src.common.logging import get_logger

logger = get_logger("inference.redis")

# Shared in-process fake server instance across the application lifetime when real Redis is offline
_shared_fake_server = None


class RedisClient:
    """Production Redis interface with automatic failover and pipeline support."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 6379,
        db: int = 0,
        socket_timeout: float = 0.2,
        force_mock: Optional[bool] = None,
    ):
        global _shared_fake_server
        self.host = host
        self.port = port
        self.db = db
        self.socket_timeout = socket_timeout

        if force_mock is not None:
            self.force_mock = force_mock
        else:
            # Check environment flag or probe host:port
            env_val = os.getenv("USE_MOCK_REDIS", "").lower()
            if env_val in ("1", "true", "yes"):
                self.force_mock = True
            else:
                self.force_mock = not self._is_port_open(host, port)

        self.is_mock = False
        self.client: Optional[redis.Redis] = None
        self._init_client()

    @staticmethod
    def _is_port_open(host: str, port: int) -> bool:
        """Fast non-blocking probe to verify if port is open before attempting blocking connection."""
        try:
            target_host = "127.0.0.1" if host == "localhost" else host
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.05)
            res = s.connect_ex((target_host, port))
            s.close()
            return res == 0
        except Exception:
            return False

    def _init_client(self) -> None:
        """Initializes client with live Redis or in-process fake Redis."""
        global _shared_fake_server
        if not self.force_mock:
            try:
                real_client = redis.Redis(
                    host=self.host,
                    port=self.port,
                    db=self.db,
                    socket_timeout=self.socket_timeout,
                    decode_responses=True,
                )
                real_client.ping()
                self.client = real_client
                self.is_mock = False
                logger.info(f"Connected to live Redis at {self.host}:{self.port}/{self.db}")
                return
            except Exception as e:
                logger.warning(
                    f"Live Redis probe passed but connection failed ({e}). Falling back to embedded FakeRedis."
                )

        # Embedded FakeRedis
        import fakeredis
        if _shared_fake_server is None:
            _shared_fake_server = fakeredis.FakeServer()
        self.client = fakeredis.FakeRedis(
            server=_shared_fake_server,
            decode_responses=True,
        )
        self.is_mock = True
        logger.info("Embedded Redis storage activated successfully.")

    def ping(self) -> bool:
        """Pings Redis."""
        try:
            return bool(self.client.ping())
        except Exception:
            return False

    def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        """Retrieves and deserializes a JSON object from Redis."""
        try:
            val = self.client.get(key)
            if val is None:
                return None
            return json.loads(val)
        except Exception as e:
            logger.error(f"Error reading JSON from Redis key '{key}': {e}")
            return None

    def set_json(
        self,
        key: str,
        value: Dict[str, Any],
        ttl_seconds: Optional[int] = None,
    ) -> bool:
        """Serializes and stores a JSON object in Redis with optional TTL."""
        try:
            payload = json.dumps(value, default=str)
            if ttl_seconds:
                return bool(self.client.set(key, payload, ex=ttl_seconds))
            else:
                return bool(self.client.set(key, payload))
        except Exception as e:
            logger.error(f"Error writing JSON to Redis key '{key}': {e}")
            return False

    def mget_json(self, keys: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Performs multi-key GET and deserializes all JSON values in O(1) roundtrip."""
        if not keys:
            return []
        try:
            raw_vals = self.client.mget(keys)
            results: List[Optional[Dict[str, Any]]] = []
            for val in raw_vals:
                if val is not None:
                    try:
                        results.append(json.loads(val))
                    except Exception:
                        results.append(None)
                else:
                    results.append(None)
            return results
        except Exception as e:
            logger.error(f"Error in mget_json: {e}")
            return [None] * len(keys)

    def pipeline(self):
        """Returns a Redis pipeline for batch operations."""
        return self.client.pipeline()

    def keys(self, pattern: str = "*") -> List[str]:
        """Lists keys matching pattern."""
        try:
            return self.client.keys(pattern)
        except Exception:
            return []

    def flushdb(self) -> bool:
        """Clears current database."""
        try:
            return bool(self.client.flushdb())
        except Exception:
            return False

    def health_check(self) -> Dict[str, Any]:
        """Returns health diagnostics."""
        connected = self.ping()
        return {
            "status": "healthy" if connected else "unhealthy",
            "connected": connected,
            "backend": "mock_in_memory" if self.is_mock else "live_redis",
            "host": self.host,
            "port": self.port,
        }
