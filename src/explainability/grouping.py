"""Semantic feature grouping for TreeSHAP attributions."""

from pathlib import Path
from typing import Dict, List, Optional, Union
import yaml
from src.common.logging import get_logger
from .schemas import FeatureAttribution, GroupAttribution

logger = get_logger("explainability.grouping")

DEFAULT_GROUPS = {
    "graph_abuse": {
        "display_name": "Network & Identity Graph Abuse",
        "description": "Multi-account linkage across shared devices, addresses, or payment instruments.",
        "is_punitive": True,
        "features": [
            "linked_accounts_1hop",
            "linked_accounts_2hop",
            "shared_device_accounts",
            "shared_address_accounts",
            "shared_payment_accounts",
            "high_return_neighbor_count",
            "connected_component_size",
        ],
    },
    "velocity": {
        "display_name": "Order & Return Velocity",
        "description": "Rapid burst of returns or orders across short temporal windows (24h/7d/30d).",
        "is_punitive": True,
        "features": [
            "returns_24h",
            "returns_7d",
            "returns_30d",
            "orders_24h",
            "orders_7d",
            "orders_30d",
            "device_returns_30d",
            "address_returns_30d",
            "payment_returns_30d",
        ],
    },
    "return_behavior": {
        "display_name": "Return Behavioral Patterns",
        "description": "Historical return rates, wardrobing risk, rapid return turnaround, or category skew.",
        "is_punitive": True,
        "features": [
            "return_rate_30d",
            "return_rate_all_time",
            "total_returns_all_time",
            "days_to_return_current",
            "avg_days_to_return_user",
            "wardrobing_risk_score",
            "category_return_rate_baseline",
            "user_category_return_rate_diff",
            "device_return_rate_30d",
        ],
    },
    "transaction_value": {
        "display_name": "Transaction & Return Economics",
        "description": "Excessive financial exposure, refund-to-order ratio, or negative unit margin.",
        "is_punitive": True,
        "features": [
            "order_amount",
            "refund_amount",
            "cogs",
            "shipping_cost",
            "return_shipping_cost",
            "handling_cost",
            "restocking_cost",
            "salvage_value_percentage",
            "estimated_return_loss",
            "total_spend_30d",
            "refund_amount_30d",
            "refund_ratio_30d",
            "item_price_vs_user_avg",
        ],
    },
    "sequence": {
        "display_name": "Temporal Order-Return Sequence",
        "description": "Inter-event timing between purchase, prior returns, and current claim.",
        "is_punitive": True,
        "features": [
            "days_since_last_order",
            "days_since_last_return",
            "total_orders_all_time",
        ],
    },
    "evidence_quality": {
        "display_name": "Evidence Quality & Account Maturity",
        "description": "Cold-start indicators and data density. Strictly informational, never punitive.",
        "is_punitive": False,
        "features": [
            "is_first_purchase",
            "account_age_hours",
            "account_age_under_24h",
            "has_prior_orders",
            "has_prior_returns",
            "user_history_count",
            "baseline_support_count",
            "used_category_fallback",
            "device_users_count",
            "address_users_count",
            "payment_users_count",
        ],
    },
}


class SemanticGrouper:
    """Aggregates feature-level SHAP attributions into higher-level semantic domains."""

    def __init__(self, config_path: Optional[Union[str, Path]] = None):
        self.groups: Dict[str, Dict] = {}
        self.feature_to_group: Dict[str, str] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[Union[str, Path]]) -> None:
        """Loads semantic groups from YAML or uses built-in defaults."""
        data = None
        if config_path:
            p = Path(config_path)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"Could not load reason_codes config from {p}: {e}")

        groups_data = data.get("groups") if data and "groups" in data else DEFAULT_GROUPS

        self.groups = {}
        self.feature_to_group = {}
        for group_id, cfg in groups_data.items():
            self.groups[group_id] = {
                "display_name": cfg.get("display_name", group_id.title()),
                "description": cfg.get("description", ""),
                "is_punitive": cfg.get("is_punitive", True),
                "features": cfg.get("features", []),
            }
            for feat in cfg.get("features", []):
                self.feature_to_group[feat] = group_id

    def get_group_for_feature(self, feature_name: str) -> str:
        """Returns the semantic group for a feature, or 'other' if unassigned."""
        return self.feature_to_group.get(feature_name, "other")

    def is_punitive_group(self, group_name: str) -> bool:
        """Returns False if group is strictly informational/cold-start."""
        grp = self.groups.get(group_name)
        if grp is not None:
            return bool(grp.get("is_punitive", True))
        return True

    def group_attributions(
        self, attributions: List[FeatureAttribution]
    ) -> List[GroupAttribution]:
        """Aggregates a list of FeatureAttribution objects into ranked GroupAttribution list.

        Ranks punitive groups with positive SHAP (risk drivers) highest.
        """
        # Bucket features by group
        attr_by_group: Dict[str, List[FeatureAttribution]] = {
            gid: [] for gid in self.groups.keys()
        }
        attr_by_group["other"] = []

        for attr in attributions:
            gid = self.get_group_for_feature(attr.feature)
            if gid in attr_by_group:
                attr_by_group[gid].append(attr)
            else:
                attr_by_group["other"].append(attr)

        result: List[GroupAttribution] = []
        for gid, grp_def in self.groups.items():
            feats = attr_by_group.get(gid, [])
            total_shap = sum(f.shap_value for f in feats)
            abs_total_shap = sum(f.abs_shap for f in feats)
            # Sort top features by positive SHAP contribution (or absolute value if negative)
            sorted_feats = sorted(feats, key=lambda f: f.shap_value, reverse=True)

            result.append(
                GroupAttribution(
                    group_name=gid,
                    display_name=grp_def["display_name"],
                    description=grp_def["description"],
                    total_shap=round(total_shap, 4),
                    abs_total_shap=round(abs_total_shap, 4),
                    rank=0,  # assigned after sorting
                    top_features=sorted_feats,
                )
            )

        # Sort groups: punitive groups with highest positive total_shap first,
        # then non-punitive (evidence_quality) at the bottom
        def sort_key(g: GroupAttribution):
            is_punitive = self.is_punitive_group(g.group_name)
            # Put non-punitive groups last, and within punitive sort by descending total_shap
            return (1 if is_punitive else 0, g.total_shap)

        sorted_groups = sorted(result, key=sort_key, reverse=True)
        for i, grp in enumerate(sorted_groups, start=1):
            grp.rank = i

        return sorted_groups
