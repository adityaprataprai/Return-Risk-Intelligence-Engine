from dataclasses import dataclass, field
from datetime import datetime, timedelta
import math
import random
from typing import Any, Dict, List, Optional, Tuple

from .entities import Customer, Event, Order, Product, Return, Seller
from .financial_engine import FinancialEngine


@dataclass
class CustomerAgent:
    """Agent representing a customer's purchasing and returning behaviors."""

    customer: Customer
    rng: random.Random

    def generate_browsing_events(
        self, start_time: datetime, count: int = 3
    ) -> List[Event]:
        """Generates browse and add-to-cart events prior to purchasing."""
        events = []
        curr = start_time - timedelta(minutes=self.rng.randint(15, 120))
        for i in range(count):
            curr += timedelta(minutes=self.rng.randint(2, 10))
            events.append(
                Event(
                    event_id=f"evt_br_{self.customer.user_id}_{int(curr.timestamp())}_{i}",
                    timestamp=curr,
                    event_type="BROWSE",
                    actor_id=self.customer.user_id,
                    payload={"page": "product_detail"},
                )
            )
        events.append(
            Event(
                event_id=f"evt_cart_{self.customer.user_id}_{int(curr.timestamp())}",
                timestamp=curr + timedelta(minutes=self.rng.randint(1, 5)),
                event_type="ADD_TO_CART",
                actor_id=self.customer.user_id,
                payload={},
            )
        )
        return events

    def decide_legitimate_return(
        self, order: Order, product: Product, seller: Seller, delivery_time: datetime
    ) -> Optional[Tuple[Return, List[Event]]]:
        """Evaluates whether customer initiates a normal return."""
        # Logistic formula for return probability based on latent propensity, price, and seller quality
        z = (
            -2.5
            + (self.customer.return_propensity * 2.2)
            + (0.3 if product.price > 3000 else 0.0)
            + (0.4 if seller.quality_score < 0.7 else -0.2)
            + (self.customer.price_sensitivity * 0.5)
        )
        prob = 1.0 / (1.0 + math.exp(-z))

        if self.rng.random() > prob:
            return None

        # Return request occurs 1 to 14 days after delivery
        days_after_deliv = self.rng.uniform(1.0, 14.0)
        req_time = delivery_time + timedelta(days=days_after_deliv)
        ret_id = f"ret_legit_{order.transaction_id}"
        econ = FinancialEngine.compute_return_economics(order.price, product)

        reasons = [
            "size_fit_issue",
            "not_as_expected",
            "quality_unsatisfactory",
            "delayed_delivery",
            "changed_mind",
        ]
        chosen_reason = self.rng.choice(reasons)

        ret = Return(
            return_id=ret_id,
            transaction_id=order.transaction_id,
            request_time=req_time,
            reason=chosen_reason,
            condition="original_packaging",
            refund_amount=order.price,
            days_to_return=round(days_after_deliv, 2),
            inspection_result="passed",
            logistics_costs=econ["logistics_costs"],
            salvage_value=econ["salvage_value"],
        )

        events = [
            Event(
                event_id=f"evt_ret_req_{ret_id}",
                timestamp=req_time,
                event_type="RETURN_REQUESTED",
                actor_id=self.customer.user_id,
                entity_ids={"order_id": order.transaction_id, "product_id": order.product_id},
                payload={"refund_amount": order.price, "reason": chosen_reason},
            ),
            Event(
                event_id=f"evt_ret_pick_{ret_id}",
                timestamp=req_time + timedelta(days=self.rng.uniform(1, 2)),
                event_type="RETURN_PICKED_UP",
                actor_id=self.customer.user_id,
                entity_ids={"order_id": order.transaction_id},
                payload={},
            ),
            Event(
                event_id=f"evt_ret_rec_{ret_id}",
                timestamp=req_time + timedelta(days=self.rng.uniform(3, 5)),
                event_type="RETURN_RECEIVED",
                actor_id="warehouse",
                entity_ids={"order_id": order.transaction_id},
                payload={"inspection": "passed"},
            ),
            Event(
                event_id=f"evt_ref_iss_{ret_id}",
                timestamp=req_time + timedelta(days=self.rng.uniform(5, 7)),
                event_type="REFUND_ISSUED",
                actor_id="payment_gateway",
                entity_ids={"order_id": order.transaction_id},
                payload={"amount": order.price},
            ),
        ]

        return ret, events
