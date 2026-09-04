"""Asynchronous Identity Graph Processor.

Maintains bipartite identity graph structures, computes multi-hop connectivity metrics,
and materializes graph features to Redis under risk:user:{user_id}:graph:v2.
"""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import polars as pl
from src.inference.redis_client import RedisClient


class GraphProcessor:
    """Computes identity network features and writes materialized graph states to Redis."""

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        graph_version: str = "g0000",
    ):
        self.redis = redis_client or RedisClient()
        self.graph_version = graph_version

        # Graph adjacency: entity -> set of users, user -> {entity_type -> set of entities}
        self.entity_users: Dict[str, Set[str]] = defaultdict(set)
        self.user_entities: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self.user_returns_count: Dict[str, int] = defaultdict(int)
        self.last_updated_at: datetime = datetime.now(timezone.utc)

    def add_relationship(
        self,
        user_id: str,
        entity_type: str,
        entity_id: str,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Ingests an identity connection edge."""
        self.entity_users[entity_id].add(user_id)
        self.user_entities[user_id][entity_type].add(entity_id)
        if timestamp:
            self.last_updated_at = max(self.last_updated_at, timestamp)

    def record_user_returns(self, user_id: str, count: int) -> None:
        """Tracks return counts for high-return neighbor detection."""
        self.user_returns_count[user_id] += count

    def compute_user_graph_metrics(self, user_id: str) -> Dict[str, Any]:
        """Computes 1-hop, 2-hop, component size, and neighbor return density for a user."""
        shared_dev: Set[str] = set()
        shared_addr: Set[str] = set()
        shared_pay: Set[str] = set()
        all_1hop: Set[str] = set()

        u_ents = self.user_entities.get(user_id, {})
        for etype, eids in u_ents.items():
            for eid in eids:
                for other_u in self.entity_users.get(eid, set()):
                    if other_u != user_id:
                        if etype == "device":
                            shared_dev.add(other_u)
                        elif etype == "address":
                            shared_addr.add(other_u)
                        elif etype == "payment":
                            shared_pay.add(other_u)
                        all_1hop.add(other_u)

        # 2-Hop neighbors
        all_2hop: Set[str] = set()
        for n1 in all_1hop:
            for etype, eids in self.user_entities.get(n1, {}).items():
                for eid in eids:
                    for n2 in self.entity_users.get(eid, set()):
                        if n2 != user_id and n2 not in all_1hop:
                            all_2hop.add(n2)

        # High return neighbors (>= 2 prior returns)
        high_ret_neighbors = sum(
            1 for n in all_1hop if self.user_returns_count.get(n, 0) >= 2
        )

        connected_size = 1 + len(all_1hop) + len(all_2hop)

        return {
            "linked_accounts_1hop": len(all_1hop),
            "linked_accounts_2hop": len(all_2hop),
            "shared_device_accounts": len(shared_dev),
            "shared_address_accounts": len(shared_addr),
            "shared_payment_accounts": len(shared_pay),
            "high_return_neighbor_count": high_ret_neighbors,
            "connected_component_size": connected_size,
        }

    def materialize_to_redis(
        self,
        user_ids: Optional[List[str]] = None,
        batch_size: int = 500,
    ) -> int:
        """Writes materialized graph metrics into Redis under risk:user:{user_id}:graph:v2."""
        targets = user_ids if user_ids is not None else list(self.user_entities.keys())
        total = 0
        pipe = self.redis.pipeline()
        ts_str = self.last_updated_at.isoformat()

        def _exec():
            nonlocal pipe
            try:
                pipe.execute()
            except Exception:
                pass
            pipe = self.redis.pipeline()

        for u in targets:
            g_feats = self.compute_user_graph_metrics(u)
            key = f"risk:user:{u}:graph:v2"
            val = {
                "feature_values": g_feats,
                "graph_last_updated_at": ts_str,
                "graph_version": self.graph_version,
                "feature_timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "fv-2.1",
            }
            pipe.set(key, str(val).replace("'", '"'))
            total += 1
            if total % batch_size == 0:
                _exec()

        _exec()
        return total

    def load_from_parquet(
        self,
        relationships_path: Union[str, Path] = "data/raw/relationships.parquet",
        returns_path: Optional[Union[str, Path]] = "data/raw/returns.parquet",
    ) -> None:
        """Loads relationships and return counts from Parquet into graph memory."""
        r_path = Path(relationships_path)
        if not r_path.exists():
            return

        df_rels = pl.read_parquet(r_path)
        for row in df_rels.iter_rows(named=True):
            self.add_relationship(
                user_id=row["user_id"],
                entity_type=row["entity_type"],
                entity_id=row["entity_id"],
                timestamp=row.get("first_seen"),
            )

        if returns_path:
            ret_p = Path(returns_path)
            if ret_p.exists():
                df_rets = pl.read_parquet(ret_p)
                # Join with orders to get user_id if needed, or count from returns
                orders_p = ret_p.parent / "orders.parquet"
                if orders_p.exists():
                    df_orders = pl.read_parquet(orders_p)
                    ret_users = df_rets.join(
                        df_orders.select(["transaction_id", "user_id"]),
                        on="transaction_id",
                        how="inner",
                    )
                    user_counts = ret_users.group_by("user_id").len()
                    for row in user_counts.iter_rows(named=True):
                        self.user_returns_count[row["user_id"]] = row["len"]
