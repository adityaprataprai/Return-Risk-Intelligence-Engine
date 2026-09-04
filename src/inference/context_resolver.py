"""Context Resolver for Phase 5 Online Redis State and Graph Serving.

Fetches user, entity, graph, and economic feature states from Redis in a single O(1) multi-key roundtrip,
computes graph freshness, and provides automatic fallback to local configs when Redis keys are missing.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import yaml

from src.inference.feature_store import InMemoryFeatureStore
from src.inference.redis_client import RedisClient
from src.inference.schemas import ReturnScoreRequest


class ContextResolver:
    """Resolves online features and economic parameters from Redis with graceful fallback."""

    def __init__(
        self,
        redis_client: Optional[RedisClient] = None,
        feature_store: Optional[InMemoryFeatureStore] = None,
        config_dir: Union[str, Path] = "config",
    ):
        self.redis = redis_client or RedisClient()
        self.feature_store = feature_store or InMemoryFeatureStore()
        self.config_dir = Path(config_dir)

        self.merchant_profiles: Dict[str, Any] = {}
        self.product_profiles: Dict[str, Any] = {}
        self.decision_policy: Dict[str, Any] = {}

        self.merchant_version = "merchant-econ-1.7"
        self.product_version = "product-econ-4.2"
        self.policy_version = "policy-3.0"
        self.feature_version = "fv-2.1"
        self.default_graph_version = "g0000"

        self.load_configs()

    def load_configs(self) -> None:
        """Loads fallback economic profiles and decision policies from disk."""
        m_path = self.config_dir / "economics" / "merchant_profiles.yaml"
        if m_path.exists():
            with open(m_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.merchant_version = data.get("version", self.merchant_version)
                self.merchant_profiles = data.get("merchants", {})

        p_path = self.config_dir / "economics" / "product_profiles.yaml"
        if p_path.exists():
            with open(p_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.product_version = data.get("version", self.product_version)
                self.product_profiles = data.get("categories", {})

        pol_path = self.config_dir / "policies" / "decision_policy.yaml"
        if pol_path.exists():
            with open(pol_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
                self.policy_version = data.get("version", self.policy_version)
                self.decision_policy = data

    def resolve(
        self, request: ReturnScoreRequest
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Resolves (ml_features, economic_context, metadata) from Redis with fallback."""
        u_id = request.user_id
        dev_id = request.device_id or "dev_default"
        addr_id = request.address_id or "addr_default"
        pay_id = request.payment_id or "pay_default"
        cat = request.product_category.lower() if request.product_category else "default"
        m_id = request.merchant_id

        # 1. Multi-key O(1) fetch from Redis
        keys = [
            f"risk:user:{u_id}:features:v2",
            f"risk:device:{dev_id}:features:v2",
            f"risk:address:{addr_id}:features:v2",
            f"risk:payment:{pay_id}:features:v2",
            f"risk:user:{u_id}:graph:v2",
            f"risk:merchant:{m_id}:economics:v1",
            f"risk:category:{cat}:economics:v1",
        ]

        u_obj, dev_obj, addr_obj, pay_obj, graph_obj, merch_obj, cat_obj = self.redis.mget_json(keys)

        # 2. Graph Freshness
        graph_version = self.default_graph_version
        graph_age_ms = 0
        if graph_obj and isinstance(graph_obj, dict):
            graph_version = graph_obj.get("graph_version", self.default_graph_version)
            graph_ts_str = graph_obj.get("graph_last_updated_at")
            if graph_ts_str:
                try:
                    # Parse timestamp and compute elapsed ms
                    if graph_ts_str.endswith("Z"):
                        graph_ts_str = graph_ts_str[:-1] + "+00:00"
                    graph_ts = datetime.fromisoformat(graph_ts_str)
                    now_utc = datetime.now(timezone.utc)
                    graph_age_ms = max(0, int((now_utc - graph_ts).total_seconds() * 1000.0))
                except Exception:
                    graph_age_ms = 1800

        # 3. Assemble ML Features
        ml_features: Dict[str, Any] = {}
        if u_obj and isinstance(u_obj, dict) and "feature_values" in u_obj:
            # Reconstruct from Redis features
            ml_features.update(u_obj.get("feature_values", {}))

            if dev_obj and isinstance(dev_obj, dict):
                ml_features.update(dev_obj.get("feature_values", {}))
            else:
                ml_features.update({"device_users_count": 1, "device_returns_30d": 0, "device_return_rate_30d": 0.0})

            if addr_obj and isinstance(addr_obj, dict):
                ml_features.update(addr_obj.get("feature_values", {}))
            else:
                ml_features.update({"address_users_count": 1, "address_returns_30d": 0})

            if pay_obj and isinstance(pay_obj, dict):
                ml_features.update(pay_obj.get("feature_values", {}))
            else:
                ml_features.update({"payment_users_count": 1, "payment_returns_30d": 0})

            if graph_obj and isinstance(graph_obj, dict):
                ml_features.update(graph_obj.get("feature_values", {}))
            else:
                ml_features.update({
                    "linked_accounts_1hop": 0,
                    "linked_accounts_2hop": 0,
                    "shared_device_accounts": 0,
                    "shared_address_accounts": 0,
                    "shared_payment_accounts": 0,
                    "high_return_neighbor_count": 0,
                    "connected_component_size": 1,
                })

            # Add transaction-specific economics & wardrobing
            order_amt = float(request.order_amount)
            refund_amt = float(request.refund_amount)
            ml_features["order_amount"] = order_amt
            ml_features["refund_amount"] = refund_amt
            ml_features["days_to_return_current"] = ml_features.get("avg_days_to_return_user", 1.0)
            ml_features["category_return_rate_baseline"] = 0.15
            ml_features["user_category_return_rate_diff"] = 0.0

            if cat in ["fashion", "electronics"]:
                ml_features["wardrobing_risk_score"] = 0.5
            else:
                ml_features["wardrobing_risk_score"] = 0.0

            # Economic loss estimation
            cogs = order_amt * 0.50
            return_shipping = 120.0
            handling = 70.0
            restocking = order_amt * 0.05
            salvage_val = cogs * 0.50
            ml_features["cogs"] = cogs
            ml_features["shipping_cost"] = 100.0
            ml_features["return_shipping_cost"] = return_shipping
            ml_features["handling_cost"] = handling
            ml_features["restocking_cost"] = restocking
            ml_features["salvage_value_percentage"] = 0.50
            ml_features["estimated_return_loss"] = (
                refund_amt + return_shipping + handling + restocking - salvage_val
            )

            # Price ratio
            avg_p = ml_features.get("user_avg_order_price", order_amt)
            ml_features["item_price_vs_user_avg"] = order_amt / max(avg_p, 1.0)

        else:
            # Fallback to in-memory feature store or cold-start synthesis
            cached_feats, fs_graph_age = self.feature_store.get_features(request)
            ml_features.update(cached_feats)
            if graph_age_ms == 0:
                graph_age_ms = fs_graph_age

        # 4. Resolve Economic Profiles (Redis or local config)
        if merch_obj and isinstance(merch_obj, dict) and "feature_values" in merch_obj:
            m_profile = merch_obj["feature_values"]
        else:
            m_profile = self.merchant_profiles.get(m_id) or self.merchant_profiles.get("m_default", {})

        if cat_obj and isinstance(cat_obj, dict) and "feature_values" in cat_obj:
            p_profile = cat_obj["feature_values"]
        else:
            p_profile = self.product_profiles.get(cat) or self.product_profiles.get("default", {})

        economic_context = {
            "merchant_id": m_id,
            "product_category": cat,
            "refund_amount": float(request.refund_amount),
            "order_amount": float(request.order_amount),
            "merchant_profile": m_profile,
            "product_profile": p_profile,
            "policy": self.decision_policy,
        }

        # 5. Assemble Metadata
        metadata = {
            "feature_version": self.feature_version,
            "graph_version": graph_version,
            "graph_age_ms": graph_age_ms,
            "merchant_profile_version": self.merchant_version,
            "product_profile_version": self.product_version,
            "profile_freshness_ms": 1800,
            "policy_version": self.policy_version,
        }

        return ml_features, economic_context, metadata
