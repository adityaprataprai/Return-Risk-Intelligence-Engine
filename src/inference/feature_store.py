"""In-memory Online Feature Store.

Pre-loads offline feature datasets from Parquet files into high-speed memory maps
keyed by transaction_id and return_id, with robust cold-start feature synthesis for unseen requests.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import polars as pl
from .schemas import ReturnScoreRequest


class InMemoryFeatureStore:
    """Fast in-memory feature store for synchronous online scoring."""

    def __init__(
        self,
        features_dir: Union[str, Path] = "data/features",
        feature_schema: Optional[List[str]] = None,
    ):
        self.features_dir = Path(features_dir)
        self.feature_schema = feature_schema or []
        self.features_by_txn: Dict[str, Dict[str, Any]] = {}
        self.features_by_ret: Dict[str, Dict[str, Any]] = {}
        self.feature_version = "fv-2.1"
        self._is_loaded = False

    def load(self) -> None:
        """Loads train, validation, and test parquets into memory."""
        if self._is_loaded:
            return

        parquet_files = [
            self.features_dir / "train_features.parquet",
            self.features_dir / "validation_features.parquet",
            self.features_dir / "test_features.parquet",
        ]

        for p in parquet_files:
            if not p.exists():
                continue
            df = pl.read_parquet(p)
            for row in df.iter_rows(named=True):
                txn_id = row.get("transaction_id")
                ret_id = row.get("return_id")
                if txn_id:
                    self.features_by_txn[str(txn_id)] = row
                if ret_id:
                    self.features_by_ret[str(ret_id)] = row

        self._is_loaded = True

    def get_features(self, request: ReturnScoreRequest) -> Tuple[Dict[str, Any], int]:
        """Retrieves feature vector for the given request.

        If transaction/return ID is found in the store, returns cached features.
        Otherwise, synthesizes a cold-start feature vector using request fields and default fallback baselines.
        Returns (features_dict, graph_age_ms).
        """
        if not self._is_loaded:
            self.load()

        txn_id = str(request.transaction_id)
        ret_id = str(request.request_id)

        # Check lookup by transaction_id first, then return_id
        cached_row = self.features_by_txn.get(txn_id) or self.features_by_ret.get(ret_id)

        if cached_row is not None:
            # Extract features matching schema or all available
            feat_dict = dict(cached_row)
            graph_age_ms = 0
            return feat_dict, graph_age_ms

        # Cold-Start / Fallback Synthesis
        return self._build_cold_start_features(request), 0

    def _build_cold_start_features(self, request: ReturnScoreRequest) -> Dict[str, Any]:
        """Synthesizes a causally correct cold-start feature vector for an unseen return request."""
        # 52 predictive numeric features with fallback values
        features: Dict[str, Any] = {
            # User Velocity
            "returns_24h": 0,
            "returns_7d": 0,
            "returns_30d": 0,
            "orders_24h": 1,
            "orders_7d": 1,
            "orders_30d": 1,
            "total_orders_all_time": 1,
            "total_returns_all_time": 0,
            "return_rate_30d": 0.0,
            "return_rate_all_time": 0.0,
            "total_spend_30d": float(request.order_amount),
            "refund_amount_30d": 0.0,
            "refund_ratio_30d": 0.0,
            "days_since_last_order": 0.0,
            "days_since_last_return": 999.0,
            # Wardrobing & Behavioral Timing
            "days_to_return_current": 1.0,
            "avg_days_to_return_user": 1.0,
            "wardrobing_risk_score": 0.5 if request.product_category in ["fashion", "electronics"] else 0.0,
            "item_price_vs_user_avg": 1.0,
            "category_return_rate_baseline": 0.15,
            "user_category_return_rate_diff": 0.0,
            # Entity-Level Aggregates
            "device_users_count": 1,
            "device_returns_30d": 0,
            "device_return_rate_30d": 0.0,
            "address_users_count": 1,
            "address_returns_30d": 0,
            "payment_users_count": 1,
            "payment_returns_30d": 0,
            # Graph & Network Metrics
            "linked_accounts_1hop": 0,
            "linked_accounts_2hop": 0,
            "shared_device_accounts": 0,
            "shared_address_accounts": 0,
            "shared_payment_accounts": 0,
            "high_return_neighbor_count": 0,
            "connected_component_size": 1,
            # Economic & Unit Loss
            "order_amount": float(request.order_amount),
            "refund_amount": float(request.refund_amount),
            "cogs": float(request.order_amount) * 0.5,
            "shipping_cost": 100.0,
            "return_shipping_cost": 120.0,
            "handling_cost": 70.0,
            "restocking_cost": float(request.order_amount) * 0.05,
            "salvage_value_percentage": 0.5,
            "estimated_return_loss": float(request.refund_amount) + 120.0 + 70.0 + (float(request.order_amount) * 0.05) - (float(request.order_amount) * 0.25),
            # Cold-Start Features
            "is_first_purchase": 1,
            "account_age_hours": 2.0,
            "account_age_under_24h": 1,
            "has_prior_orders": 0,
            "has_prior_returns": 0,
            "user_history_count": 0,
            "baseline_support_count": 100,
            "used_category_fallback": 1,
        }
        return features
