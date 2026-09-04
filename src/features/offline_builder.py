"""Offline Feature Builder.

Computes point-in-time features for each return request using Polars,
ensuring strict temporal correctness, cold-start handling, behavioral deviations,
and graph metrics from relationship snapshots.
"""

from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import bisect
import numpy as np
import polars as pl

from .registry import FeatureRegistry


class OfflineFeatureBuilder:
    """Computes point-in-time features from raw event and entity data."""

    def __init__(
        self,
        raw_data_dir: Union[str, Path] = "data/raw",
        gt_data_dir: Union[str, Path] = "data/ground_truth",
        registry_path: Union[str, Path] = "config/features/registry.yaml",
    ):
        self.raw_dir = Path(raw_data_dir)
        self.gt_dir = Path(gt_data_dir)
        self.registry = FeatureRegistry.load_from_yaml(registry_path)

        # Raw DataFrames
        self.users_df: Optional[pl.DataFrame] = None
        self.products_df: Optional[pl.DataFrame] = None
        self.orders_df: Optional[pl.DataFrame] = None
        self.returns_df: Optional[pl.DataFrame] = None
        self.events_df: Optional[pl.DataFrame] = None
        self.relationships_df: Optional[pl.DataFrame] = None
        self.hidden_labels_df: Optional[pl.DataFrame] = None

        # Precomputed lookup structures
        self.user_account_creation: Dict[str, datetime] = {}
        self.category_baseline_return_rates: Dict[str, float] = {}
        self.category_order_counts: Dict[str, int] = {}
        self.user_orders: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.user_returns: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.device_orders: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.device_returns: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.address_orders: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.address_returns: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.payment_orders: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.payment_returns: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)

        # Graph structures: entity -> list of (first_seen, user_id)
        self.entity_users: Dict[str, List[Tuple[datetime, str]]] = defaultdict(list)
        self.user_entities: Dict[str, Dict[str, List[Tuple[datetime, str]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.all_graph_timestamps: List[datetime] = []

    def load_data(self) -> None:
        """Loads all raw datasets and ground truth into memory."""
        print("Loading raw datasets...")
        self.users_df = pl.read_parquet(self.raw_dir / "users.parquet")
        self.products_df = pl.read_parquet(self.raw_dir / "products.parquet")
        self.orders_df = pl.read_parquet(self.raw_dir / "orders.parquet")
        self.returns_df = pl.read_parquet(self.raw_dir / "returns.parquet")
        self.events_df = pl.read_parquet(self.raw_dir / "events.parquet")
        self.relationships_df = pl.read_parquet(self.raw_dir / "relationships.parquet")

        gt_path = self.gt_dir / "hidden_labels.parquet"
        if gt_path.exists():
            self.hidden_labels_df = pl.read_parquet(gt_path)

        self._index_data()

    def _index_data(self) -> None:
        """Builds indexed chronological lookup dictionaries for sub-millisecond point-in-time queries."""
        print("Indexing events, orders, returns, and relationships...")

        # 1. User account creation timestamps
        acct_events = self.events_df.filter(pl.col("event_type") == "ACCOUNT_CREATED")
        for row in acct_events.iter_rows(named=True):
            self.user_account_creation[row["actor_id"]] = row["timestamp"]

        # 2. Product financials and category mappings
        prod_map = {}
        for p in self.products_df.iter_rows(named=True):
            prod_map[p["product_id"]] = p

        # 3. Category return rate baselines
        cat_orders_count = defaultdict(int)
        cat_returns_count = defaultdict(int)

        # 4. Chronological indexing of orders
        sorted_orders = self.orders_df.sort("timestamp")
        for row in sorted_orders.iter_rows(named=True):
            u = row["user_id"]
            ts = row["timestamp"]
            p_info = prod_map.get(row["product_id"], {})
            cat = p_info.get("category", "unknown")
            cat_orders_count[cat] += 1

            order_item = {
                "timestamp": ts,
                "transaction_id": row["transaction_id"],
                "price": float(row["price"]),
                "product_id": row["product_id"],
                "category": cat,
                "device_id": row.get("device_id"),
                "address_id": row.get("address_id"),
                "payment_id": row.get("payment_id"),
            }
            self.user_orders[u].append(order_item)

            if row.get("device_id"):
                self.device_orders[row["device_id"]].append((ts, u))
            if row.get("address_id"):
                self.address_orders[row["address_id"]].append((ts, u))
            if row.get("payment_id"):
                self.payment_orders[row["payment_id"]].append((ts, u))

        # 5. Chronological indexing of returns joined with order metadata
        order_meta_map = {}
        for row in self.orders_df.iter_rows(named=True):
            order_meta_map[row["transaction_id"]] = row

        sorted_returns = self.returns_df.sort("request_time")
        for row in sorted_returns.iter_rows(named=True):
            txn_id = row["transaction_id"]
            o_info = order_meta_map.get(txn_id, {})
            u = o_info.get("user_id")
            if not u:
                continue

            ts = row["request_time"]
            p_info = prod_map.get(o_info.get("product_id"), {})
            cat = p_info.get("category", "unknown")
            cat_returns_count[cat] += 1

            ret_item = {
                "request_time": ts,
                "return_id": row["return_id"],
                "transaction_id": txn_id,
                "refund_amount": float(row["refund_amount"]),
                "days_to_return": float(row["days_to_return"]),
                "category": cat,
                "order_time": o_info.get("timestamp"),
                "price": float(o_info.get("price", 0.0)),
                "device_id": o_info.get("device_id"),
                "address_id": o_info.get("address_id"),
                "payment_id": o_info.get("payment_id"),
            }
            self.user_returns[u].append(ret_item)

            if o_info.get("device_id"):
                self.device_returns[o_info["device_id"]].append((ts, u))
            if o_info.get("address_id"):
                self.address_returns[o_info["address_id"]].append((ts, u))
            if o_info.get("payment_id"):
                self.payment_returns[o_info["payment_id"]].append((ts, u))

        # Compute category baseline return rates
        for cat, o_cnt in cat_orders_count.items():
            self.category_order_counts[cat] = o_cnt
            r_cnt = cat_returns_count.get(cat, 0)
            self.category_baseline_return_rates[cat] = r_cnt / max(o_cnt, 1)

        # 6. Graph indexing from relationships.parquet
        sorted_rels = self.relationships_df.sort("first_seen")
        all_graph_ts = []
        for row in sorted_rels.iter_rows(named=True):
            u = row["user_id"]
            etype = row["entity_type"]
            eid = row["entity_id"]
            ts = row["first_seen"]
            all_graph_ts.append(ts)
            self.entity_users[eid].append((ts, u))
            self.user_entities[u][etype].append((ts, eid))

        self.all_graph_timestamps = sorted(all_graph_ts)
        print("Indexing completed.")

    def compute_features_for_return(
        self,
        return_row: Dict[str, Any],
        order_row: Dict[str, Any],
        product_row: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Computes all 53 point-in-time features strictly as of return request_time."""
        t = return_row["request_time"]
        u = order_row["user_id"]
        txn_id = return_row["transaction_id"]
        curr_order_time = order_row["timestamp"]
        curr_price = float(order_row["price"])
        curr_refund = float(return_row["refund_amount"])
        curr_days_to_return = float(return_row["days_to_return"])
        curr_category = product_row.get("category", "unknown")

        dev_id = order_row.get("device_id")
        addr_id = order_row.get("address_id")
        pay_id = order_row.get("payment_id")

        # ---------------------------------------------------------------------
        # 1. User Order & Velocity History (Point-in-Time <= t)
        # ---------------------------------------------------------------------
        u_orders = self.user_orders.get(u, [])
        # Find orders before or at t
        prior_orders = [o for o in u_orders if o["timestamp"] <= t]
        # Prior orders strictly before this transaction order
        prior_orders_before_txn = [o for o in u_orders if o["timestamp"] < curr_order_time]

        t_24h_ago = t - np.timedelta64(24, "h")
        t_7d_ago = t - np.timedelta64(7, "D")
        t_30d_ago = t - np.timedelta64(30, "D")

        orders_24h = sum(1 for o in prior_orders if o["timestamp"] >= t_24h_ago)
        orders_7d = sum(1 for o in prior_orders if o["timestamp"] >= t_7d_ago)
        orders_30d = sum(1 for o in prior_orders if o["timestamp"] >= t_30d_ago)
        total_orders_all_time = len(prior_orders)
        total_spend_30d = sum(o["price"] for o in prior_orders if o["timestamp"] >= t_30d_ago)

        # Days since last order before the current order
        if prior_orders_before_txn:
            last_order_ts = prior_orders_before_txn[-1]["timestamp"]
            days_since_last_order = max(
                0.0, (curr_order_time - last_order_ts).total_seconds() / 86400.0
            )
        else:
            days_since_last_order = 0.0

        # ---------------------------------------------------------------------
        # 2. User Return History (STRICT POINT-IN-TIME: returns strictly < t)
        # Current return must NEVER be counted as prior return!
        # ---------------------------------------------------------------------
        u_returns = self.user_returns.get(u, [])
        prior_returns = [r for r in u_returns if r["request_time"] < t]

        returns_24h = sum(1 for r in prior_returns if r["request_time"] >= t_24h_ago)
        returns_7d = sum(1 for r in prior_returns if r["request_time"] >= t_7d_ago)
        returns_30d = sum(1 for r in prior_returns if r["request_time"] >= t_30d_ago)
        total_returns_all_time = len(prior_returns)
        refund_amount_30d = sum(
            r["refund_amount"] for r in prior_returns if r["request_time"] >= t_30d_ago
        )

        return_rate_30d = min(1.0, returns_30d / max(orders_30d, 1))
        return_rate_all_time = min(1.0, total_returns_all_time / max(total_orders_all_time, 1))
        refund_ratio_30d = (
            min(1.0, refund_amount_30d / max(total_spend_30d, 1.0))
            if total_spend_30d > 0
            else 0.0
        )

        if prior_returns:
            last_ret_ts = prior_returns[-1]["request_time"]
            days_since_last_return = max(0.0, (t - last_ret_ts).total_seconds() / 86400.0)
            avg_days_to_return_user = float(
                np.mean([r["days_to_return"] for r in prior_returns])
            )
        else:
            days_since_last_return = 999.0
            avg_days_to_return_user = curr_days_to_return

        # ---------------------------------------------------------------------
        # 3. Wardrobing & Behavioral Deviation Features
        # ---------------------------------------------------------------------
        days_to_return_current = curr_days_to_return
        cat_baseline_rate = self.category_baseline_return_rates.get(curr_category, 0.15)

        # User return rate in this category prior to t
        user_cat_orders = sum(1 for o in prior_orders if o["category"] == curr_category)
        user_cat_returns = sum(1 for r in prior_returns if r["category"] == curr_category)
        if user_cat_orders >= 2:
            user_cat_rate = user_cat_returns / user_cat_orders
            user_category_return_rate_diff = user_cat_rate - cat_baseline_rate
        else:
            user_category_return_rate_diff = 0.0

        # Wardrobing risk score (combining rapid return, category, and weekend/deviation)
        if curr_category in ["fashion", "electronics"] and days_to_return_current <= 3.0:
            wardrobing_risk_score = min(1.0, max(0.0, 1.0 - (days_to_return_current / 5.0)))
        else:
            wardrobing_risk_score = 0.0

        # Item price vs user average order price
        if prior_orders_before_txn:
            user_avg_price = float(np.mean([o["price"] for o in prior_orders_before_txn]))
            item_price_vs_user_avg = curr_price / max(user_avg_price, 1.0)
        else:
            item_price_vs_user_avg = 1.0

        # ---------------------------------------------------------------------
        # 4. Entity-Level Aggregates (Device, Address, Payment)
        # ---------------------------------------------------------------------
        # Device
        dev_users = {
            user for (ts_o, user) in self.device_orders.get(dev_id, []) if ts_o <= t
        }
        device_users_count = len(dev_users) if dev_id else 1
        dev_ret_30d = sum(
            1 for (ts_r, _) in self.device_returns.get(dev_id, []) if t_30d_ago <= ts_r < t
        )
        dev_ord_30d = sum(
            1 for (ts_o, _) in self.device_orders.get(dev_id, []) if t_30d_ago <= ts_o <= t
        )
        device_return_rate_30d = min(1.0, dev_ret_30d / max(dev_ord_30d, 1))

        # Address
        addr_users = {
            user for (ts_o, user) in self.address_orders.get(addr_id, []) if ts_o <= t
        }
        address_users_count = len(addr_users) if addr_id else 1
        address_returns_30d = sum(
            1 for (ts_r, _) in self.address_returns.get(addr_id, []) if t_30d_ago <= ts_r < t
        )

        # Payment
        pay_users = {
            user for (ts_o, user) in self.payment_orders.get(pay_id, []) if ts_o <= t
        }
        payment_users_count = len(pay_users) if pay_id else 1
        payment_returns_30d = sum(
            1 for (ts_r, _) in self.payment_returns.get(pay_id, []) if t_30d_ago <= ts_r < t
        )

        # ---------------------------------------------------------------------
        # 5. Graph Metrics (Active Edges as of t)
        # ---------------------------------------------------------------------
        shared_device_users: Set[str] = set()
        shared_address_users: Set[str] = set()
        shared_payment_users: Set[str] = set()
        all_1hop_users: Set[str] = set()

        u_ents = self.user_entities.get(u, {})
        for etype, elist in u_ents.items():
            for e_ts, eid in elist:
                if e_ts <= t:
                    for u_ts, other_u in self.entity_users.get(eid, []):
                        if u_ts <= t and other_u != u:
                            if etype == "device":
                                shared_device_users.add(other_u)
                            elif etype == "address":
                                shared_address_users.add(other_u)
                            elif etype == "payment":
                                shared_payment_users.add(other_u)
                            all_1hop_users.add(other_u)

        # 2-hop neighbors
        all_2hop_users: Set[str] = set()
        for n1 in all_1hop_users:
            for etype, elist in self.user_entities.get(n1, {}).items():
                for e_ts, eid in elist:
                    if e_ts <= t:
                        for u_ts, n2 in self.entity_users.get(eid, []):
                            if u_ts <= t and n2 != u and n2 not in all_1hop_users:
                                all_2hop_users.add(n2)

        # High return neighbor count: 1-hop neighbors with >= 2 prior returns as of t
        high_return_neighbor_count = 0
        for n1 in all_1hop_users:
            n1_rets = sum(
                1 for r in self.user_returns.get(n1, []) if r["request_time"] < t
            )
            if n1_rets >= 2:
                high_return_neighbor_count += 1

        connected_component_size = 1 + len(all_1hop_users) + len(all_2hop_users)

        # Graph last updated at: latest relationship first_seen <= t
        idx = bisect.bisect_right(self.all_graph_timestamps, t)
        if idx > 0:
            graph_last_updated_at = self.all_graph_timestamps[idx - 1]
        else:
            graph_last_updated_at = t

        # ---------------------------------------------------------------------
        # 6. Economic Features
        # ---------------------------------------------------------------------
        order_amount = curr_price
        refund_amount = curr_refund
        cogs = float(product_row.get("cogs", 0.0))
        shipping_cost = float(product_row.get("shipping_cost", 0.0))
        return_shipping_cost = float(product_row.get("return_shipping_cost", 0.0))
        handling_cost = float(product_row.get("handling_cost", 0.0))
        restocking_cost = float(product_row.get("restocking_cost", 0.0))
        salvage_value_percentage = float(product_row.get("salvage_value_percentage", 0.5))

        # Loss = Refund + Return Shipping + Handling + Restocking - Salvage Value
        salvage_val = cogs * salvage_value_percentage
        estimated_return_loss = (
            refund_amount
            + return_shipping_cost
            + handling_cost
            + restocking_cost
            - salvage_val
        )

        # ---------------------------------------------------------------------
        # 7. Cold-Start Features (Section 4)
        # ---------------------------------------------------------------------
        user_history_count = len(prior_orders_before_txn)
        is_first_purchase = 1 if user_history_count == 0 else 0
        has_prior_orders = 1 if user_history_count > 0 else 0
        has_prior_returns = 1 if total_returns_all_time > 0 else 0

        acct_created = self.user_account_creation.get(u, curr_order_time)
        account_age_hours = max(
            0.0, (t - acct_created).total_seconds() / 3600.0
        )
        account_age_under_24h = 1 if account_age_hours < 24.0 else 0

        # Fallback hierarchy:
        # 1. User baseline if user_history_count >= 5
        # 2. Category/merchant baseline if user insufficient
        if user_history_count >= 5:
            used_category_fallback = 0
            baseline_support_count = user_history_count
        else:
            used_category_fallback = 1
            baseline_support_count = self.category_order_counts.get(curr_category, 100)

        # Assemble the full 53 features dictionary
        features = {
            # Metadata identifiers (preserved for joins / models)
            "return_id": return_row["return_id"],
            "transaction_id": txn_id,
            "user_id": u,
            "request_time": t,
            # 1. User Velocity & Serial Return Abuse
            "returns_24h": int(returns_24h),
            "returns_7d": int(returns_7d),
            "returns_30d": int(returns_30d),
            "orders_24h": int(orders_24h),
            "orders_7d": int(orders_7d),
            "orders_30d": int(orders_30d),
            "total_orders_all_time": int(total_orders_all_time),
            "total_returns_all_time": int(total_returns_all_time),
            "return_rate_30d": float(return_rate_30d),
            "return_rate_all_time": float(return_rate_all_time),
            "total_spend_30d": float(total_spend_30d),
            "refund_amount_30d": float(refund_amount_30d),
            "refund_ratio_30d": float(refund_ratio_30d),
            "days_since_last_order": float(days_since_last_order),
            "days_since_last_return": float(days_since_last_return),
            # 2. Wardrobing & Behavioral Timing
            "days_to_return_current": float(days_to_return_current),
            "avg_days_to_return_user": float(avg_days_to_return_user),
            "wardrobing_risk_score": float(wardrobing_risk_score),
            "item_price_vs_user_avg": float(item_price_vs_user_avg),
            "category_return_rate_baseline": float(cat_baseline_rate),
            "user_category_return_rate_diff": float(user_category_return_rate_diff),
            # 3. Entity-Level Aggregates
            "device_users_count": int(device_users_count),
            "device_returns_30d": int(dev_ret_30d),
            "device_return_rate_30d": float(device_return_rate_30d),
            "address_users_count": int(address_users_count),
            "address_returns_30d": int(address_returns_30d),
            "payment_users_count": int(payment_users_count),
            "payment_returns_30d": int(payment_returns_30d),
            # 4. Graph & Network Metrics
            "linked_accounts_1hop": int(len(all_1hop_users)),
            "linked_accounts_2hop": int(len(all_2hop_users)),
            "shared_device_accounts": int(len(shared_device_users)),
            "shared_address_accounts": int(len(shared_address_users)),
            "shared_payment_accounts": int(len(shared_payment_users)),
            "high_return_neighbor_count": int(high_return_neighbor_count),
            "connected_component_size": int(connected_component_size),
            "graph_last_updated_at": graph_last_updated_at,
            # 5. Economic & Transaction Financials
            "order_amount": float(order_amount),
            "refund_amount": float(refund_amount),
            "cogs": float(cogs),
            "shipping_cost": float(shipping_cost),
            "return_shipping_cost": float(return_shipping_cost),
            "handling_cost": float(handling_cost),
            "restocking_cost": float(restocking_cost),
            "salvage_value_percentage": float(salvage_value_percentage),
            "estimated_return_loss": float(estimated_return_loss),
            # 6. Cold-Start Features
            "is_first_purchase": int(is_first_purchase),
            "account_age_hours": float(account_age_hours),
            "account_age_under_24h": int(account_age_under_24h),
            "has_prior_orders": int(has_prior_orders),
            "has_prior_returns": int(has_prior_returns),
            "user_history_count": int(user_history_count),
            "baseline_support_count": int(baseline_support_count),
            "used_category_fallback": int(used_category_fallback),
        }
        return features

    def build_all_features(self) -> pl.DataFrame:
        """Computes all features for every return request in the dataset."""
        if self.returns_df is None:
            self.load_data()

        print(f"Building features for {len(self.returns_df)} return requests...")

        # Join order metadata and product metadata onto returns
        order_meta_map = {row["transaction_id"]: row for row in self.orders_df.iter_rows(named=True)}
        prod_map = {row["product_id"]: row for row in self.products_df.iter_rows(named=True)}

        feature_rows = []
        for r_row in self.returns_df.iter_rows(named=True):
            txn_id = r_row["transaction_id"]
            o_row = order_meta_map.get(txn_id, {})
            p_row = prod_map.get(o_row.get("product_id"), {})
            feats = self.compute_features_for_return(r_row, o_row, p_row)
            feature_rows.append(feats)

        df = pl.DataFrame(feature_rows)

        # Join ground truth labels if available (target label only; scenario/difficulty are segregated ground truth)
        if self.hidden_labels_df is not None:
            df = df.join(
                self.hidden_labels_df.select(["return_id", "is_fraud"]),
                on="return_id",
                how="left",
            )

        print(f"Feature dataset successfully built with shape: {df.shape}")
        return df

    def split_and_save(
        self,
        features_df: pl.DataFrame,
        output_dir: Union[str, Path] = "data/features",
    ) -> Dict[str, Path]:
        """Saves features partitioned strictly according to Phase 2 temporal requirements:

        - train_features.parquet (World A most recent 70% temporally)
        - validation_features.parquet (World A next 15%)
        - test_features.parquet (World A oldest 15%)
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Sort descending by request_time to get most recent first
        df_sorted = features_df.sort("request_time", descending=True)
        total_rows = len(df_sorted)

        train_cutoff = int(0.70 * total_rows)
        val_cutoff = int(0.85 * total_rows)

        train_df = df_sorted.slice(0, train_cutoff)
        val_df = df_sorted.slice(train_cutoff, val_cutoff - train_cutoff)
        test_df = df_sorted.slice(val_cutoff, total_rows - val_cutoff)

        train_path = out_dir / "train_features.parquet"
        val_path = out_dir / "validation_features.parquet"
        test_path = out_dir / "test_features.parquet"

        print(f"Writing train features ({len(train_df)} rows) to {train_path}...")
        train_df.write_parquet(train_path)

        print(f"Writing validation features ({len(val_df)} rows) to {val_path}...")
        val_df.write_parquet(val_path)

        print(f"Writing test features ({len(test_df)} rows) to {test_path}...")
        test_df.write_parquet(test_path)

        return {
            "train": train_path,
            "validation": val_path,
            "test": test_path,
        }
