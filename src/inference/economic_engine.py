"""Economic Decision Engine.

Calculates action-specific financial consequences, evaluates risk thresholds and unit economics,
and prescribes optimal risk actions (APPROVE, VERIFY, BLOCK) with quantified expected losses.
"""

from typing import Any, Dict, Literal, Optional
from .schemas import DecisionResult


class EconomicDecisionEngine:
    """Evaluates economic consequences and policy thresholds to prescribe risk decisions."""

    def __init__(self, policy: Optional[Dict[str, Any]] = None):
        self.policy = policy or {
            "version": "policy-3.0",
            "thresholds": {
                "approve_max_risk": 0.25,
                "verify_max_risk": 0.75,
            },
        }

    def decide(
        self,
        probability: float,
        economic_context: Dict[str, Any],
        policy: Optional[Dict[str, Any]] = None,
    ) -> DecisionResult:
        """Determines risk action (APPROVE, VERIFY, BLOCK) and calculates expected loss.

        Args:
            probability: Calibrated fraud risk probability in [0.0, 1.0].
            economic_context: Merchant and product financial profiles.
            policy: Policy threshold configuration.

        Returns:
            DecisionResult(action, expected_loss, policy_version)
        """
        active_policy = policy or self.policy
        policy_version = active_policy.get("version", "policy-3.0")
        thresholds = active_policy.get("thresholds", {})
        approve_max = thresholds.get("approve_max_risk", 0.25)
        verify_max = thresholds.get("verify_max_risk", 0.75)

        # Extract economics
        refund_amount = float(economic_context.get("refund_amount", 1000.0))
        order_amount = float(economic_context.get("order_amount", refund_amount))
        merchant = economic_context.get("merchant_profile", {})
        product = economic_context.get("product_profile", {})

        cac = float(merchant.get("customer_acquisition_cost", 450.0))
        churn_multiplier = float(merchant.get("churn_cost_multiplier", 2.5))
        return_shipping = float(product.get("return_shipping_cost", 120.0))
        handling = float(product.get("handling_cost", 70.0))
        restocking_rate = float(product.get("restocking_cost_rate", 0.05))
        salvage_pct = float(product.get("salvage_value_percentage", 0.50))
        cogs_rate = float(product.get("cogs_rate", 0.50))

        cogs = order_amount * cogs_rate
        restocking_cost = order_amount * restocking_rate
        salvage_val = cogs * salvage_pct

        # Direct fraud loss if approved
        fraud_loss_approve = max(
            0.0, refund_amount + return_shipping + handling + restocking_cost - salvage_val
        )
        legit_cost_approve = return_shipping + handling

        # Inspection costs if verified
        inspection_cost = 60.0
        friction_cost = 25.0

        # False positive churn cost if blocked
        churn_loss_block = cac * churn_multiplier

        # Action-specific expected loss
        loss_approve = probability * fraud_loss_approve + (1.0 - probability) * legit_cost_approve
        loss_verify = inspection_cost + (1.0 - probability) * (legit_cost_approve + friction_cost)
        loss_block = (1.0 - probability) * churn_loss_block

        # Rule-based threshold decision as per decision_policy.yaml
        if probability <= approve_max:
            action: Literal["APPROVE", "VERIFY", "BLOCK"] = "APPROVE"
            expected_loss = loss_approve
        elif probability <= verify_max:
            action = "VERIFY"
            expected_loss = loss_verify
        else:
            action = "BLOCK"
            expected_loss = loss_block

        return DecisionResult(
            action=action,
            expected_loss=round(float(expected_loss), 2),
            policy_version=policy_version,
        )
