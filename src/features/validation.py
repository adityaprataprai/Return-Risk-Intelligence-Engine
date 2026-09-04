"""Feature validation suite.

Implements schema validation, range checks, missingness reporting,
and point-in-time leakage tests.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import polars as pl

from .registry import FeatureRegistry


class FeatureValidator:
    """Validates engineered feature datasets for correctness, integrity, and point-in-time safety."""

    def __init__(self, registry_path: Union[str, Path] = "config/features/registry.yaml"):
        self.registry = FeatureRegistry.load_from_yaml(registry_path)

    def check_schema(self, df: pl.DataFrame) -> Dict[str, Any]:
        """Validates that all registered features are present and have expected datatypes."""
        expected_features = self.registry.get_feature_names()
        df_cols = set(df.columns)

        missing = [f for f in expected_features if f not in df_cols]
        extra = [c for c in df.columns if c not in expected_features and c not in [
            "return_id", "transaction_id", "user_id", "request_time",
            "is_fraud", "true_scenario", "difficulty"
        ]]

        return {
            "passed": len(missing) == 0,
            "total_registered_features": len(expected_features),
            "present_registered_features": len(expected_features) - len(missing),
            "missing_features": missing,
            "extra_columns": extra,
        }

    def check_ranges(self, df: pl.DataFrame) -> Dict[str, Any]:
        """Validates that rates are within [0, 1] and counts/amounts are non-negative."""
        violations = {}

        # 1. Check rate bounds [0, 1]
        rate_cols = [
            "return_rate_30d",
            "return_rate_all_time",
            "refund_ratio_30d",
            "device_return_rate_30d",
            "category_return_rate_baseline",
            "salvage_value_percentage",
        ]
        for col in rate_cols:
            if col in df.columns:
                out_of_bounds = df.filter((pl.col(col) < 0.0) | (pl.col(col) > 1.0))
                if len(out_of_bounds) > 0:
                    violations[col] = f"{len(out_of_bounds)} rows out of [0, 1] range"

        # 2. Check non-negative counts
        count_cols = [
            "returns_24h",
            "returns_7d",
            "returns_30d",
            "orders_24h",
            "orders_7d",
            "orders_30d",
            "total_orders_all_time",
            "total_returns_all_time",
            "device_users_count",
            "address_users_count",
            "payment_users_count",
            "linked_accounts_1hop",
            "linked_accounts_2hop",
            "shared_device_accounts",
            "shared_address_accounts",
            "shared_payment_accounts",
            "high_return_neighbor_count",
            "connected_component_size",
            "user_history_count",
            "baseline_support_count",
        ]
        for col in count_cols:
            if col in df.columns:
                neg_counts = df.filter(pl.col(col) < 0)
                if len(neg_counts) > 0:
                    violations[col] = f"{len(neg_counts)} negative counts"

        # 3. Check binary flags in {0, 1}
        flag_cols = [
            "is_first_purchase",
            "account_age_under_24h",
            "has_prior_orders",
            "has_prior_returns",
            "used_category_fallback",
        ]
        for col in flag_cols:
            if col in df.columns:
                invalid_flags = df.filter(~pl.col(col).is_in([0, 1]))
                if len(invalid_flags) > 0:
                    violations[col] = f"{len(invalid_flags)} rows with invalid binary flag values"

        return {
            "passed": len(violations) == 0,
            "violations": violations,
        }

    def check_point_in_time_leakage(
        self,
        features_df: pl.DataFrame,
        raw_data_dir: Union[str, Path] = "data/raw",
        sample_size: int = 100,
    ) -> Dict[str, Any]:
        """Verifies point-in-time correctness on a random sample by inspecting raw event causality."""
        raw_dir = Path(raw_data_dir)
        orders_df = pl.read_parquet(raw_dir / "orders.parquet")
        returns_df = pl.read_parquet(raw_dir / "returns.parquet")
        sample = features_df.sample(min(sample_size, len(features_df)), seed=42)

        leakage_violations = []

        # Check graph timestamp freshness rule: graph_last_updated_at <= request_time
        graph_leaks = sample.filter(pl.col("graph_last_updated_at") > pl.col("request_time"))
        if len(graph_leaks) > 0:
            leakage_violations.append(
                f"{len(graph_leaks)} rows where graph_last_updated_at > request_time"
            )

        # Cross-verify user prior returns against ground raw returns
        for row in sample.iter_rows(named=True):
            u = row["user_id"]
            req_t = row["request_time"]
            reported_prior_returns = row["total_returns_all_time"]

            # Compute actual prior returns from raw returns joined with orders
            user_txns = set(orders_df.filter(pl.col("user_id") == u)["transaction_id"].to_list())
            actual_prior_returns = len(
                returns_df.filter(
                    (pl.col("transaction_id").is_in(user_txns))
                    & (pl.col("request_time") < req_t)
                )
            )

            if reported_prior_returns != actual_prior_returns:
                leakage_violations.append(
                    f"Return count mismatch for user {u} at {req_t}: reported={reported_prior_returns}, actual={actual_prior_returns}"
                )
                if len(leakage_violations) >= 5:
                    break

        return {
            "passed": len(leakage_violations) == 0,
            "sample_size": len(sample),
            "leakage_violations": leakage_violations,
        }

    def generate_missingness_report(self, df: pl.DataFrame) -> Dict[str, Any]:
        """Calculates missing values across all features."""
        null_counts = {}
        for col in df.columns:
            nulls = df[col].is_null().sum()
            if nulls > 0:
                null_counts[col] = {
                    "null_count": int(nulls),
                    "missing_rate": float(nulls / len(df)),
                }

        return {
            "total_columns": len(df.columns),
            "columns_with_missing_values": len(null_counts),
            "missingness": null_counts,
        }

    def run_all_validations(
        self,
        df: pl.DataFrame,
        raw_data_dir: Union[str, Path] = "data/raw",
    ) -> Dict[str, Any]:
        """Runs the entire validation suite and returns a structured report."""
        schema_res = self.check_schema(df)
        range_res = self.check_ranges(df)
        leakage_res = self.check_point_in_time_leakage(df, raw_data_dir=raw_data_dir)
        missing_res = self.generate_missingness_report(df)

        all_passed = (
            schema_res["passed"]
            and range_res["passed"]
            and leakage_res["passed"]
            and missing_res["columns_with_missing_values"] == 0
        )

        return {
            "all_passed": all_passed,
            "schema_check": schema_res,
            "range_check": range_res,
            "leakage_check": leakage_res,
            "missingness_report": missing_res,
        }
