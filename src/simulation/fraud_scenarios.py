from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import random
from .entities import Customer, Event, HiddenLabel, Order, Product, Return
from .financial_engine import FinancialEngine


class FraudScenario:
    """Base class for fraud scenarios."""

    def __init__(self, rng: random.Random):
        self.rng = rng

    def apply(
        self,
        customer: Customer,
        products: List[Product],
        orders: List[Order],
        difficulty: str = "moderate",
        delivery_times: Optional[Dict[str, datetime]] = None,
    ) -> List[Tuple[Return, HiddenLabel, List[Event]]]:
        raise NotImplementedError


class SerialReturnAbuse(FraudScenario):
    """Generates serial return abuse patterns (burst purchases and high-velocity returns)."""

    def apply(
        self,
        customer: Customer,
        products: List[Product],
        orders: List[Order],
        difficulty: str = "moderate",
        delivery_times: Optional[Dict[str, datetime]] = None,
    ) -> List[Tuple[Return, HiddenLabel, List[Event]]]:
        if not orders:
            return []

        results = []
        product_map = {p.product_id: p for p in products}

        # Velocity and ratio based on difficulty
        if difficulty == "easy":
            target_orders = orders[-min(len(orders), self.rng.randint(4, 7)):]
            return_delay_hours = self.rng.uniform(6, 24)
        elif difficulty == "moderate":
            target_orders = orders[-min(len(orders), self.rng.randint(2, 4)):]
            return_delay_hours = self.rng.uniform(24, 72)
        else:  # stealthy
            high_val_orders = [o for o in orders if o.price > 4000]
            target_orders = (
                high_val_orders[-min(len(high_val_orders), self.rng.randint(1, 2)):]
                if high_val_orders
                else orders[-1:]
            )
            return_delay_hours = self.rng.uniform(48, 120)

        for o in target_orders:
            prod = product_map.get(o.product_id, products[0])
            deliv_time = (
                delivery_times.get(o.transaction_id)
                if delivery_times and o.transaction_id in delivery_times
                else o.timestamp + timedelta(days=4)
            )
            req_time = deliv_time + timedelta(hours=return_delay_hours)
            ret_id = f"ret_s_{o.transaction_id}"
            econ = FinancialEngine.compute_return_economics(o.price, prod)

            ret = Return(
                return_id=ret_id,
                transaction_id=o.transaction_id,
                request_time=req_time,
                reason="item_defective" if difficulty == "stealthy" else "not_as_described",
                condition="unopened" if difficulty == "stealthy" else "damaged",
                refund_amount=o.price,
                days_to_return=round(return_delay_hours / 24.0, 2),
                inspection_result="fraud_detected",
                logistics_costs=econ["logistics_costs"],
                salvage_value=econ["salvage_value"],
            )

            hidden_label = HiddenLabel(
                return_id=ret_id,
                is_fraud=1,
                true_scenario="serial_return_abuse",
                difficulty=difficulty,
            )

            events = [
                Event(
                    event_id=f"evt_ret_req_{ret_id}",
                    timestamp=req_time,
                    event_type="RETURN_REQUESTED",
                    actor_id=customer.user_id,
                    entity_ids={"order_id": o.transaction_id, "product_id": o.product_id},
                    payload={"refund_amount": o.price, "reason": ret.reason},
                ),
                Event(
                    event_id=f"evt_ret_pick_{ret_id}",
                    timestamp=req_time + timedelta(hours=24),
                    event_type="RETURN_PICKED_UP",
                    actor_id=customer.user_id,
                    entity_ids={"order_id": o.transaction_id},
                    payload={},
                ),
                Event(
                    event_id=f"evt_ret_rec_{ret_id}",
                    timestamp=req_time + timedelta(hours=72),
                    event_type="RETURN_RECEIVED",
                    actor_id="warehouse",
                    entity_ids={"order_id": o.transaction_id},
                    payload={"inspection": ret.inspection_result},
                ),
            ]

            results.append((ret, hidden_label, events))

        return results


class MultiAccountAbuse(FraudScenario):
    """Generates multi-account abuse (shared device, address, or payment across accounts)."""

    def apply(
        self,
        customer: Customer,
        products: List[Product],
        orders: List[Order],
        difficulty: str = "moderate",
        delivery_times: Optional[Dict[str, datetime]] = None,
    ) -> List[Tuple[Return, HiddenLabel, List[Event]]]:
        if not orders:
            return []

        results = []
        product_map = {p.product_id: p for p in products}
        sample_order = orders[-1]
        prod = product_map.get(sample_order.product_id, products[0])

        deliv_time = (
            delivery_times.get(sample_order.transaction_id)
            if delivery_times and sample_order.transaction_id in delivery_times
            else sample_order.timestamp + timedelta(days=4)
        )
        return_delay_hours = self.rng.uniform(12, 72)
        req_time = deliv_time + timedelta(hours=return_delay_hours)
        ret_id = f"ret_m_{sample_order.transaction_id}"
        econ = FinancialEngine.compute_return_economics(sample_order.price, prod)

        ret = Return(
            return_id=ret_id,
            transaction_id=sample_order.transaction_id,
            request_time=req_time,
            reason="wrong_item_received",
            condition="poor",
            refund_amount=sample_order.price,
            days_to_return=round(return_delay_hours / 24.0, 2),
            inspection_result="empty_box_or_counterfeit",
            logistics_costs=econ["logistics_costs"],
            salvage_value=0.0,  # no salvage for empty box / counterfeit
        )

        hidden_label = HiddenLabel(
            return_id=ret_id,
            is_fraud=1,
            true_scenario="multi_account_abuse",
            difficulty=difficulty,
        )

        events = [
            Event(
                event_id=f"evt_ret_req_{ret_id}",
                timestamp=req_time,
                event_type="RETURN_REQUESTED",
                actor_id=customer.user_id,
                entity_ids={"order_id": sample_order.transaction_id},
                payload={"refund_amount": sample_order.price},
            ),
            Event(
                event_id=f"evt_ret_rec_{ret_id}",
                timestamp=req_time + timedelta(hours=48),
                event_type="RETURN_RECEIVED",
                actor_id="warehouse",
                entity_ids={"order_id": sample_order.transaction_id},
                payload={"inspection": "missing_item"},
            ),
        ]

        results.append((ret, hidden_label, events))
        return results


class Wardrobing(FraudScenario):
    """Generates wardrobing behavior (buying expensive items, wearing/using shortly, returning)."""

    def apply(
        self,
        customer: Customer,
        products: List[Product],
        orders: List[Order],
        difficulty: str = "moderate",
        delivery_times: Optional[Dict[str, datetime]] = None,
    ) -> List[Tuple[Return, HiddenLabel, List[Event]]]:
        # Filter for fashion or electronics or high value
        candidates = [
            o for o in orders if o.price >= 2000
        ]
        target_orders = candidates if candidates else orders
        if not target_orders:
            return []

        results = []
        product_map = {p.product_id: p for p in products}
        sample_order = target_orders[-1]
        prod = product_map.get(sample_order.product_id, products[0])

        deliv_time = (
            delivery_times.get(sample_order.transaction_id)
            if delivery_times and sample_order.transaction_id in delivery_times
            else sample_order.timestamp + timedelta(days=4)
        )

        if difficulty == "easy":
            days_used = self.rng.uniform(0.5, 1.5)
        elif difficulty == "moderate":
            days_used = self.rng.uniform(2.0, 4.0)
        else:  # stealthy
            days_used = self.rng.uniform(5.0, 9.0)

        req_time = deliv_time + timedelta(days=days_used)
        ret_id = f"ret_w_{sample_order.transaction_id}"
        econ = FinancialEngine.compute_return_economics(sample_order.price, prod)

        ret = Return(
            return_id=ret_id,
            transaction_id=sample_order.transaction_id,
            request_time=req_time,
            reason="does_not_fit_or_need",
            condition="used_with_tags_removed",
            refund_amount=sample_order.price,
            days_to_return=round(days_used, 2),
            inspection_result="worn_item",
            logistics_costs=econ["logistics_costs"],
            salvage_value=econ["salvage_value"] * 0.5,
        )

        hidden_label = HiddenLabel(
            return_id=ret_id,
            is_fraud=1,
            true_scenario="wardrobing",
            difficulty=difficulty,
        )

        events = [
            Event(
                event_id=f"evt_ret_req_{ret_id}",
                timestamp=req_time,
                event_type="RETURN_REQUESTED",
                actor_id=customer.user_id,
                entity_ids={"order_id": sample_order.transaction_id},
                payload={"refund_amount": sample_order.price},
            ),
            Event(
                event_id=f"evt_ret_rec_{ret_id}",
                timestamp=req_time + timedelta(hours=48),
                event_type="RETURN_RECEIVED",
                actor_id="warehouse",
                entity_ids={"order_id": sample_order.transaction_id},
                payload={"inspection": "tags_missing"},
            ),
        ]

        results.append((ret, hidden_label, events))
        return results
