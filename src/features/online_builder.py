"""Online Feature Builder.

Processes incoming transaction and return events to maintain near-real-time feature states
in Redis across user and entity keys (device, address, payment) using pipeline batching.
"""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import numpy as np
import yaml

from src.inference.redis_client import RedisClient


class OnlineFeatureBuilder:
    """Consumes real-time stream or replayed historical events and writes materialized features to Redis."""

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        feature_version: str = "fv-2.1",
        config_dir: Union[str, Path] = "config",
    ):
        self.redis = redis_client or RedisClient()
        self.feature_version = feature_version
        self.config_dir = Path(config_dir)

        # In-memory accumulator maps for stream replay/updates
        self.user_creation_time: Dict[str, datetime] = {}
        self.user_orders: Dict[str, List[Tuple[datetime, float, str]]] = defaultdict(list)  # (ts, price, cat)
        self.user_returns: Dict[str, List[Tuple[datetime, float, float, str]]] = defaultdict(list)  # (ts, refund, days, cat)

        self.device_users: Dict[str, Set[str]] = defaultdict(set)
        self.device_orders: Dict[str, List[datetime]] = defaultdict(list)
        self.device_returns: Dict[str, List[datetime]] = defaultdict(list)

        self.address_users: Dict[str, Set[str]] = defaultdict(set)
        self.address_orders: Dict[str, List[datetime]] = defaultdict(list)
        self.address_returns: Dict[str, List[datetime]] = defaultdict(list)

        self.payment_users: Dict[str, Set[str]] = defaultdict(set)
        self.payment_orders: Dict[str, List[datetime]] = defaultdict(list)
        self.payment_returns: Dict[str, List[datetime]] = defaultdict(list)

    def populate_economics(self) -> None:
        """Populates merchant, product, and category economic parameters into Redis."""
        m_path = self.config_dir / "economics" / "merchant_profiles.yaml"
        if m_path.exists():
            with open(m_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                ver = data.get("version", "merchant-econ-1.7")
                for m_id, prof in data.get("merchants", {}).items():
                    key = f"risk:merchant:{m_id}:economics:v1"
                    self.redis.set_json(
                        key,
                        {
                            "feature_values": prof,
                            "feature_timestamp": datetime.now(timezone.utc).isoformat(),
                            "version": ver,
                            "ttl_ms": 86400000,
                        },
                    )

        p_path = self.config_dir / "economics" / "product_profiles.yaml"
        if p_path.exists():
            with open(p_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                ver = data.get("version", "product-econ-4.2")
                for cat, prof in data.get("categories", {}).items():
                    key = f"risk:category:{cat}:economics:v1"
                    self.redis.set_json(
                        key,
                        {
                            "feature_values": prof,
                            "feature_timestamp": datetime.now(timezone.utc).isoformat(),
                            "version": ver,
                            "ttl_ms": 86400000,
                        },
                    )

    def record_account_created(self, user_id: str, timestamp: datetime) -> None:
        """Records account creation event."""
        self.user_creation_time[user_id] = timestamp

    def record_order(
        self,
        user_id: str,
        timestamp: datetime,
        price: float,
        category: str = "default",
        device_id: Optional[str] = None,
        address_id: Optional[str] = None,
        payment_id: Optional[str] = None,
    ) -> None:
        """Records purchase order event."""
        self.user_orders[user_id].append((timestamp, price, category))

        if device_id:
            self.device_users[device_id].add(user_id)
            self.device_orders[device_id].append(timestamp)
        if address_id:
            self.address_users[address_id].add(user_id)
            self.address_orders[address_id].append(timestamp)
        if payment_id:
            self.payment_users[payment_id].add(user_id)
            self.payment_orders[payment_id].append(timestamp)

    def record_return(
        self,
        user_id: str,
        timestamp: datetime,
        refund_amount: float,
        days_to_return: float = 1.0,
        category: str = "default",
        device_id: Optional[str] = None,
        address_id: Optional[str] = None,
        payment_id: Optional[str] = None,
    ) -> None:
        """Records return request event."""
        self.user_returns[user_id].append((timestamp, refund_amount, days_to_return, category))

        if device_id:
            self.device_returns[device_id].append(timestamp)
        if address_id:
            self.address_returns[address_id].append(timestamp)
        if payment_id:
            self.payment_returns[payment_id].append(timestamp)

    def compute_user_features(self, user_id: str, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Computes current rolling user feature values as of specified time."""
        t = as_of_time or datetime.now(timezone.utc)
        orders = [o for o in self.user_orders.get(user_id, []) if o[0] <= t]
        returns = [r for r in self.user_returns.get(user_id, []) if r[0] <= t]

        t_24h = t - np.timedelta64(24, "h")
        t_7d = t - np.timedelta64(7, "D")
        t_30d = t - np.timedelta64(30, "D")

        orders_24h = sum(1 for o in orders if o[0] >= t_24h)
        orders_7d = sum(1 for o in orders if o[0] >= t_7d)
        orders_30d = sum(1 for o in orders if o[0] >= t_30d)
        total_orders = len(orders)
        total_spend_30d = sum(o[1] for o in orders if o[0] >= t_30d)

        returns_24h = sum(1 for r in returns if r[0] >= t_24h)
        returns_7d = sum(1 for r in returns if r[0] >= t_7d)
        returns_30d = sum(1 for r in returns if r[0] >= t_30d)
        total_returns = len(returns)
        refund_amount_30d = sum(r[1] for r in returns if r[0] >= t_30d)

        return_rate_30d = min(1.0, returns_30d / max(orders_30d, 1))
        return_rate_all_time = min(1.0, total_returns / max(total_orders, 1))
        refund_ratio_30d = min(1.0, refund_amount_30d / max(total_spend_30d, 1.0)) if total_spend_30d > 0 else 0.0

        created = self.user_creation_time.get(user_id, t)
        account_age_hours = max(0.0, (t - created).total_seconds() / 3600.0)
        account_age_under_24h = 1 if account_age_hours < 24.0 else 0
        is_first_purchase = 1 if total_orders <= 1 else 0
        has_prior_orders = 1 if total_orders > 0 else 0
        has_prior_returns = 1 if total_returns > 0 else 0

        user_history_count = total_orders
        used_category_fallback = 0 if user_history_count >= 5 else 1
        baseline_support = user_history_count if user_history_count >= 5 else 100

        if returns:
            days_since_last_ret = max(0.0, (t - returns[-1][0]).total_seconds() / 86400.0)
            avg_days_to_return = float(np.mean([r[2] for r in returns]))
        else:
            days_since_last_ret = 999.0
            avg_days_to_return = 1.0

        if orders:
            days_since_last_ord = max(0.0, (t - orders[-1][0]).total_seconds() / 86400.0)
            user_avg_price = float(np.mean([o[1] for o in orders]))
        else:
            days_since_last_ord = 0.0
            user_avg_price = 1000.0

        return {
            "returns_24h": returns_24h,
            "returns_7d": returns_7d,
            "returns_30d": returns_30d,
            "orders_24h": orders_24h,
            "orders_7d": orders_7d,
            "orders_30d": orders_30d,
            "total_orders_all_time": total_orders,
            "total_returns_all_time": total_returns,
            "return_rate_30d": round(return_rate_30d, 4),
            "return_rate_all_time": round(return_rate_all_time, 4),
            "total_spend_30d": round(total_spend_30d, 2),
            "refund_amount_30d": round(refund_amount_30d, 2),
            "refund_ratio_30d": round(refund_ratio_30d, 4),
            "days_since_last_order": round(days_since_last_ord, 2),
            "days_since_last_return": round(days_since_last_ret, 2),
            "account_age_hours": round(account_age_hours, 2),
            "account_age_under_24h": account_age_under_24h,
            "is_first_purchase": is_first_purchase,
            "has_prior_orders": has_prior_orders,
            "has_prior_returns": has_prior_returns,
            "user_history_count": user_history_count,
            "baseline_support_count": baseline_support,
            "used_category_fallback": used_category_fallback,
            "avg_days_to_return_user": round(avg_days_to_return, 2),
            "user_avg_order_price": round(user_avg_price, 2),
        }

    def compute_device_features(self, device_id: str, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Computes device aggregates."""
        t = as_of_time or datetime.now(timezone.utc)
        t_30d = t - np.timedelta64(30, "D")
        users_count = len(self.device_users.get(device_id, set()))
        orders_30d = sum(1 for ts in self.device_orders.get(device_id, []) if ts >= t_30d)
        returns_30d = sum(1 for ts in self.device_returns.get(device_id, []) if ts >= t_30d)
        rate_30d = min(1.0, returns_30d / max(orders_30d, 1))

        return {
            "device_users_count": max(1, users_count),
            "device_returns_30d": returns_30d,
            "device_return_rate_30d": round(rate_30d, 4),
        }

    def compute_address_features(self, address_id: str, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Computes address aggregates."""
        t = as_of_time or datetime.now(timezone.utc)
        t_30d = t - np.timedelta64(30, "D")
        users_count = len(self.address_users.get(address_id, set()))
        returns_30d = sum(1 for ts in self.address_returns.get(address_id, []) if ts >= t_30d)

        return {
            "address_users_count": max(1, users_count),
            "address_returns_30d": returns_30d,
        }

    def compute_payment_features(self, payment_id: str, as_of_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Computes payment method aggregates."""
        t = as_of_time or datetime.now(timezone.utc)
        t_30d = t - np.timedelta64(30, "D")
        users_count = len(self.payment_users.get(payment_id, set()))
        returns_30d = sum(1 for ts in self.payment_returns.get(payment_id, []) if ts >= t_30d)

        return {
            "payment_users_count": max(1, users_count),
            "payment_returns_30d": returns_30d,
        }

    def flush_to_redis(
        self,
        user_ids: Optional[List[str]] = None,
        device_ids: Optional[List[str]] = None,
        address_ids: Optional[List[str]] = None,
        payment_ids: Optional[List[str]] = None,
        batch_size: int = 500,
    ) -> int:
        """Writes materialized feature states to Redis using pipelines."""
        u_list = user_ids if user_ids is not None else list(self.user_orders.keys())
        d_list = device_ids if device_ids is not None else list(self.device_users.keys())
        a_list = address_ids if address_ids is not None else list(self.address_users.keys())
        p_list = payment_ids if payment_ids is not None else list(self.payment_users.keys())

        now_str = datetime.now(timezone.utc).isoformat()
        total_keys = 0
        pipe = self.redis.pipeline()

        def _execute_pipeline():
            nonlocal pipe
            try:
                pipe.execute()
            except Exception:
                pass
            pipe = self.redis.pipeline()

        # Flush User Keys
        for u in u_list:
            feats = self.compute_user_features(u)
            key = f"risk:user:{u}:features:v2"
            val = {
                "feature_values": feats,
                "feature_timestamp": now_str,
                "version": self.feature_version,
                "ttl_ms": 60000,
            }
            pipe.set(key, yaml.dump(val) if False else str(val).replace("'", '"'))
            total_keys += 1
            if total_keys % batch_size == 0:
                _execute_pipeline()

        # Flush Device Keys
        for d in d_list:
            feats = self.compute_device_features(d)
            key = f"risk:device:{d}:features:v2"
            val = {
                "feature_values": feats,
                "feature_timestamp": now_str,
                "version": self.feature_version,
                "ttl_ms": 60000,
            }
            pipe.set(key, str(val).replace("'", '"'))
            total_keys += 1
            if total_keys % batch_size == 0:
                _execute_pipeline()

        # Flush Address Keys
        for a in a_list:
            feats = self.compute_address_features(a)
            key = f"risk:address:{a}:features:v2"
            val = {
                "feature_values": feats,
                "feature_timestamp": now_str,
                "version": self.feature_version,
                "ttl_ms": 60000,
            }
            pipe.set(key, str(val).replace("'", '"'))
            total_keys += 1
            if total_keys % batch_size == 0:
                _execute_pipeline()

        # Flush Payment Keys
        for p in p_list:
            feats = self.compute_payment_features(p)
            key = f"risk:payment:{p}:features:v2"
            val = {
                "feature_values": feats,
                "feature_timestamp": now_str,
                "version": self.feature_version,
                "ttl_ms": 60000,
            }
            pipe.set(key, str(val).replace("'", '"'))
            total_keys += 1
            if total_keys % batch_size == 0:
                _execute_pipeline()

        _execute_pipeline()
        return total_keys
