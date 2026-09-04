"""Deterministic reason code engine and data confidence evaluator."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml
from src.common.logging import get_logger
from .evidence_builder import EvidenceBuilder
from .grouping import SemanticGrouper
from .schemas import (
    DataConfidenceInfo,
    FeatureAttribution,
    GroupAttribution,
    ReasonCodeEvidence,
)

logger = get_logger("explainability.reason_codes")

DEFAULT_REASON_CODES = {
    "RC_NETWORK_ABUSE": {
        "title": "Multi-Account Identity Network Abuse",
        "group": "graph_abuse",
        "severity": "HIGH",
        "priority": 1,
        "template": "Customer account is linked to {linked_accounts_1hop} account(s) via shared identity infrastructure (connected component size {connected_component_size}).",
        "features": [
            "linked_accounts_1hop",
            "linked_accounts_2hop",
            "connected_component_size",
            "high_return_neighbor_count",
        ],
    },
    "RC_SHARED_DEVICE_RISK": {
        "title": "High-Risk Shared Device Footprint",
        "group": "graph_abuse",
        "severity": "HIGH",
        "priority": 2,
        "template": "Device footprint is shared across {shared_device_accounts} account(s) with {device_returns_30d} return(s) in the past 30 days.",
        "features": [
            "shared_device_accounts",
            "device_returns_30d",
            "device_return_rate_30d",
        ],
    },
    "RC_HIGH_RETURN_VELOCITY": {
        "title": "Elevated Return Velocity in Short Window",
        "group": "velocity",
        "severity": "HIGH",
        "priority": 3,
        "template": "Customer initiated {returns_24h} return(s) in the last 24 hours ({returns_7d} in prior 7 days).",
        "features": [
            "returns_24h",
            "returns_7d",
            "returns_30d",
        ],
    },
    "RC_RAPID_WARDROBING": {
        "title": "Suspected Wardrobing / Rapid Return",
        "group": "return_behavior",
        "severity": "MEDIUM",
        "priority": 4,
        "template": "Return requested {days_to_return_current:.1f} day(s) post-delivery with elevated wardrobing risk score of {wardrobing_risk_score:.2f}.",
        "features": [
            "wardrobing_risk_score",
            "days_to_return_current",
            "avg_days_to_return_user",
        ],
    },
    "RC_EXCESSIVE_REFUND_RATIO": {
        "title": "Disproportionate Refund Volume",
        "group": "transaction_value",
        "severity": "MEDIUM",
        "priority": 5,
        "template": "30-day refund ratio is {refund_ratio_30d:.1%} (requested refund amount ₹{refund_amount:.2f}).",
        "features": [
            "refund_ratio_30d",
            "refund_amount_30d",
            "refund_amount",
        ],
    },
    "RC_DISPROPORTIONATE_RETURN_LOSS": {
        "title": "Severe Expected Financial Loss",
        "group": "transaction_value",
        "severity": "MEDIUM",
        "priority": 6,
        "template": "Estimated net return loss of ₹{estimated_return_loss:.2f} on order value ₹{order_amount:.2f}.",
        "features": [
            "estimated_return_loss",
            "order_amount",
            "cogs",
            "return_shipping_cost",
        ],
    },
    "RC_CATEGORY_RETURN_ANOMALY": {
        "title": "Abnormal Category Return Rate",
        "group": "return_behavior",
        "severity": "LOW",
        "priority": 7,
        "template": "User return rate for category exceeds baseline by {user_category_return_rate_diff:+.1%} (30-day user rate: {return_rate_30d:.1%}).",
        "features": [
            "user_category_return_rate_diff",
            "return_rate_30d",
            "category_return_rate_baseline",
        ],
    },
    "RC_CHRONIC_RETURN_RATE": {
        "title": "Chronic Lifetime Return Profile",
        "group": "return_behavior",
        "severity": "MEDIUM",
        "priority": 8,
        "template": "Customer has a 30-day return rate of {return_rate_30d:.1%} across {total_returns_all_time} total returns.",
        "features": [
            "return_rate_30d",
            "return_rate_all_time",
            "total_returns_all_time",
        ],
    },
}


class ReasonCodeEngine:
    """Evaluates TreeSHAP attributions to generate deterministic, non-punitive reason codes."""

    def __init__(
        self,
        config_path: Optional[Union[str, Path]] = None,
        grouper: Optional[SemanticGrouper] = None,
    ):
        self.grouper = grouper or SemanticGrouper(config_path)
        self.reason_codes: Dict[str, Dict] = {}
        self._load_config(config_path)

    def _load_config(self, config_path: Optional[Union[str, Path]]) -> None:
        data = None
        if config_path:
            p = Path(config_path)
            if p.exists():
                try:
                    with open(p, "r", encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                except Exception as e:
                    logger.warning(f"Could not load reason code config from {p}: {e}")

        rc_data = (
            data.get("reason_codes")
            if data and "reason_codes" in data
            else DEFAULT_REASON_CODES
        )
        self.reason_codes = {}
        for code, cfg in rc_data.items():
            self.reason_codes[code] = {
                "title": cfg.get("title", code),
                "group": cfg.get("group", "other"),
                "severity": cfg.get("severity", "MEDIUM"),
                "priority": cfg.get("priority", 99),
                "template": cfg.get("template", ""),
                "features": cfg.get("features", []),
            }

    def evaluate_data_confidence(self, feature_vector: Dict[str, float]) -> DataConfidenceInfo:
        """Evaluates evidence quality and cold-start indicators.

        Guarantees that cold-start features (account_age, is_first_purchase) are
        NEVER treated as punitive fraud reasons.
        """
        acct_age = feature_vector.get("account_age_hours", 720.0)
        is_first = feature_vector.get("is_first_purchase", 0.0)
        history_cnt = feature_vector.get("user_history_count", 10.0)

        cold_start_indicators = {
            "account_age_hours": acct_age,
            "is_first_purchase": bool(is_first),
            "user_history_count": int(history_cnt),
            "baseline_support_count": int(feature_vector.get("baseline_support_count", 100)),
            "used_category_fallback": bool(feature_vector.get("used_category_fallback", 0.0)),
        }

        if acct_age < 24.0 or is_first == 1.0 or history_cnt < 1.0:
            level = "LOW_COLD_START"
            summary = (
                f"New account ({acct_age:.1f}h tenure) or initial transaction. "
                "Baseline behavioral priors applied; cold-start telemetry."
            )
        elif history_cnt < 3:
            level = "MEDIUM"
            summary = (
                f"Thin customer transaction history ({int(history_cnt)} orders observed). "
                "Moderate statistical evidence density."
            )
        else:
            level = "HIGH"
            summary = (
                f"Established customer history with {int(history_cnt)} prior interactions. "
                "High statistical confidence."
            )

        return DataConfidenceInfo(
            confidence_level=level,
            history_summary=summary,
            cold_start_indicators=cold_start_indicators,
        )

    def generate_reason_codes(
        self,
        attributions: List[FeatureAttribution],
        feature_vector: Dict[str, float],
        max_reasons: int = 3,
    ) -> List[ReasonCodeEvidence]:
        """Maps top positive (risk-increasing) SHAP features to deterministic reason codes.

        Cold-start and evidence-quality features are strictly excluded from punitive codes.
        """
        # Map feature name to attribution
        attr_map = {a.feature: a for a in attributions}

        # Filter strictly to risk-increasing features that are in punitive groups
        candidate_features = [
            a for a in attributions
            if a.shap_value > 0.001
            and self.grouper.is_punitive_group(self.grouper.get_group_for_feature(a.feature))
        ]

        if not candidate_features:
            # If no positive features exist (e.g. very low risk), check top positive SHAP overall
            candidate_features = [
                a for a in attributions
                if self.grouper.is_punitive_group(self.grouper.get_group_for_feature(a.feature))
            ]

        # Score candidate reason codes
        scored_reasons = []
        for code, cfg in self.reason_codes.items():
            group = cfg["group"]
            # Ensure group is punitive
            if not self.grouper.is_punitive_group(group):
                continue

            target_features = cfg["features"]
            # Check sum of positive SHAP for features in this reason code
            contributing_shap = 0.0
            has_trigger = False
            for feat in target_features:
                if feat in attr_map:
                    fa = attr_map[feat]
                    if fa.shap_value > 0:
                        contributing_shap += fa.shap_value
                        # Check that feature actually has non-zero evidence value
                        if feature_vector.get(feat, 0.0) > 0:
                            has_trigger = True

            if has_trigger and contributing_shap > 0.0:
                scored_reasons.append({
                    "code": code,
                    "cfg": cfg,
                    "score": contributing_shap,
                    "priority": cfg.get("priority", 99),
                })

        # Sort reasons by descending score, then by priority (lower number = higher priority)
        scored_reasons.sort(key=lambda item: (-item["score"], item["priority"]))

        # Build evidence models for top reasons
        selected: List[ReasonCodeEvidence] = []
        seen_groups = set()

        for item in scored_reasons:
            cfg = item["cfg"]
            code = item["code"]
            group = cfg["group"]

            # Diversity heuristic: try not to pick duplicate codes from the same group
            # unless we have fewer than max_reasons
            if group in seen_groups and len(selected) + (len(scored_reasons) - len(selected)) > max_reasons:
                if len(selected) >= max_reasons:
                    break

            text, supporting = EvidenceBuilder.build_evidence(
                code=code,
                template=cfg["template"],
                features=feature_vector,
                relevant_feature_names=cfg["features"],
            )

            evidence_obj = ReasonCodeEvidence(
                code=code,
                title=cfg["title"],
                severity=cfg["severity"],
                group=group,
                evidence_text=text,
                supporting_features=supporting,
            )
            selected.append(evidence_obj)
            seen_groups.add(group)

            if len(selected) >= max_reasons:
                break

        return selected
