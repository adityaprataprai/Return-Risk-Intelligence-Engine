from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import random
from typing import Any, Dict, List, Optional, Tuple
import polars as pl
import pyarrow as pa
import pyarrow.parquet as pq

from .agents import CustomerAgent
from .entities import (
    Address,
    Customer,
    Device,
    Event,
    HiddenLabel,
    Order,
    Payment,
    Product,
    Relationship,
    Return,
    Seller,
)
from .event_scheduler import EventScheduler
from .financial_engine import FinancialEngine
from .fraud_scenarios import MultiAccountAbuse, SerialReturnAbuse, Wardrobing
from .graph_builder import GraphBuilder


class SimulationGenerator:
    """Orchestrates population generation, discrete event simulation, and dataset export."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.seed = config.get("random_seed", 42)
        self.rng = random.Random(self.seed)

        self.pop_cfg = config.get("population", {})
        self.num_customers = self.pop_cfg.get("num_customers", 10000)
        self.num_products = self.pop_cfg.get("num_products", 500)
        self.num_sellers = self.pop_cfg.get("num_sellers", 50)
        self.num_devices = self.pop_cfg.get("num_devices", 12000)
        self.num_addresses = self.pop_cfg.get("num_addresses", 8000)
        self.num_payments = self.pop_cfg.get("num_payments", 9000)
        self.target_orders = config.get("transaction_scale", 100000)

        self.fraud_mix = config.get(
            "fraud_mix",
            {"serial_return_abuse": 0.4, "multi_account_abuse": 0.3, "wardrobing": 0.3},
        )
        self.difficulty_mix = config.get(
            "difficulty", {"easy": 0.4, "moderate": 0.4, "stealthy": 0.2}
        )
        self.hard_neg_cfg = config.get(
            "hard_negatives",
            {"high_return_legit": 0.03, "family_shared_household": 0.02},
        )

        start_str = config.get("start_date", "2026-03-01T00:00:00Z")
        self.start_date = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
        self.sim_days = config.get("simulation_days", 180)

        self.scheduler = EventScheduler()
        self.graph_builder = GraphBuilder()

        # In-memory stores
        self.customers: List[Customer] = []
        self.products: List[Product] = []
        self.sellers: List[Seller] = []
        self.devices: List[Device] = []
        self.addresses: List[Address] = []
        self.payments: List[Payment] = []
        self.orders: List[Order] = []
        self.returns: List[Return] = []
        self.hidden_labels: List[HiddenLabel] = []

    def _sample_difficulty(self) -> str:
        r = self.rng.random()
        if r < self.difficulty_mix["easy"]:
            return "easy"
        elif r < self.difficulty_mix["easy"] + self.difficulty_mix["moderate"]:
            return "moderate"
        return "stealthy"

    def generate_entities(self) -> None:
        """Generates background entities (devices, addresses, payments, sellers, products, customers)."""
        print(f"Generating {self.num_devices} devices...")
        device_types = ["mobile_ios", "mobile_android", "desktop_chrome", "desktop_safari"]
        os_types = ["iOS 17", "Android 14", "Windows 11", "macOS Sonoma"]
        for i in range(self.num_devices):
            self.devices.append(
                Device(
                    device_id=f"dev_{i:06d}",
                    type=self.rng.choice(device_types),
                    os=self.rng.choice(os_types),
                    first_seen=self.start_date
                    - timedelta(days=self.rng.randint(30, 365)),
                )
            )

        print(f"Generating {self.num_addresses} addresses...")
        regions = ["North", "South", "East", "West", "Central"]
        cities = ["Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata", "Pune"]
        for i in range(self.num_addresses):
            self.addresses.append(
                Address(
                    address_id=f"addr_{i:06d}",
                    region=self.rng.choice(regions),
                    city=self.rng.choice(cities),
                )
            )

        print(f"Generating {self.num_payments} payment instruments...")
        pay_types = ["upi", "credit_card", "debit_card", "net_banking", "cod"]
        for i in range(self.num_payments):
            self.payments.append(
                Payment(
                    payment_id=f"pay_{i:06d}",
                    type=self.rng.choice(pay_types),
                    age_days=self.rng.randint(10, 730),
                )
            )

        print(f"Generating {self.num_sellers} sellers...")
        for i in range(self.num_sellers):
            self.sellers.append(
                Seller(
                    seller_id=f"sel_{i:04d}",
                    quality_score=round(self.rng.betavariate(8, 2), 2),
                    fulfillment_performance=round(self.rng.betavariate(9, 1), 2),
                    age_days=self.rng.randint(60, 1500),
                )
            )

        print(f"Generating {self.num_products} products...")
        categories = ["electronics", "fashion", "home_kitchen", "beauty", "footwear", "books"]
        for i in range(self.num_products):
            cat = self.rng.choice(categories)
            if cat == "electronics":
                price = round(self.rng.lognormvariate(8.5, 0.6), 2)  # ~1500 - 25000
                salvage = 0.40
            elif cat == "fashion":
                price = round(self.rng.lognormvariate(7.2, 0.5), 2)  # ~500 - 5000
                salvage = 0.60
            else:
                price = round(self.rng.lognormvariate(6.8, 0.5), 2)
                salvage = 0.50

            cogs = round(price * 0.60, 2)
            shipping = round(self.rng.uniform(40, 120), 2)
            ret_shipping = round(shipping * 1.1, 2)
            handling = round(self.rng.uniform(20, 50), 2)
            restocking = round(self.rng.uniform(10, 30), 2)

            self.products.append(
                Product(
                    product_id=f"prod_{i:05d}",
                    category=cat,
                    price=price,
                    cogs=cogs,
                    shipping_cost=shipping,
                    return_shipping_cost=ret_shipping,
                    handling_cost=handling,
                    restocking_cost=restocking,
                    salvage_value_percentage=salvage,
                )
            )

        print(f"Generating {self.num_customers} customers...")
        segments = ["premium", "regular", "bargain_hunter", "infrequent"]
        for i in range(self.num_customers):
            # Assign linked devices, addresses, and payments
            cust_devs = [self.devices[self.rng.randint(0, len(self.devices) - 1)].device_id]
            if self.rng.random() < 0.25:
                cust_devs.append(self.devices[self.rng.randint(0, len(self.devices) - 1)].device_id)

            cust_addrs = [self.addresses[self.rng.randint(0, len(self.addresses) - 1)].address_id]
            if self.rng.random() < 0.20:
                cust_addrs.append(self.addresses[self.rng.randint(0, len(self.addresses) - 1)].address_id)

            cust_pays = [self.payments[self.rng.randint(0, len(self.payments) - 1)].payment_id]
            if self.rng.random() < 0.35:
                cust_pays.append(self.payments[self.rng.randint(0, len(self.payments) - 1)].payment_id)

            self.customers.append(
                Customer(
                    user_id=f"usr_{i:06d}",
                    account_age_days=float(self.rng.randint(1, 1000)),
                    segment=self.rng.choice(segments),
                    region=self.rng.choice(regions),
                    purchase_propensity=round(self.rng.betavariate(2, 5), 3),
                    return_propensity=round(self.rng.betavariate(2, 8), 3),
                    fraud_propensity=0.0,
                    price_sensitivity=round(self.rng.uniform(0.1, 0.9), 2),
                    delivery_tolerance=self.rng.randint(2, 7),
                    category_preferences={c: round(self.rng.random(), 2) for c in categories},
                    trust_state="trusted" if self.rng.random() > 0.1 else "new",
                    device_ids=cust_devs,
                    address_ids=cust_addrs,
                    payment_ids=cust_pays,
                )
            )

    def _inject_shared_household_hard_negatives(self) -> None:
        """Creates legitimate shared devices/addresses across family members."""
        num_families = int(self.num_customers * self.hard_neg_cfg["family_shared_household"])
        for _ in range(num_families):
            c1, c2 = self.rng.sample(self.customers, 2)
            shared_addr = c1.address_ids[0]
            if shared_addr not in c2.address_ids:
                c2.address_ids.append(shared_addr)
            if self.rng.random() < 0.5:
                shared_dev = c1.device_ids[0]
                if shared_dev not in c2.device_ids:
                    c2.device_ids.append(shared_dev)

    def _inject_fraud_rings(self) -> List[Tuple[Customer, str, str]]:
        """Selects fraud ring clusters and injects multi-account links."""
        # Total fraud customers ~ 5% of customer base
        fraud_targets = []
        num_fraudsters = int(self.num_customers * 0.05)
        candidates = self.rng.sample(self.customers, num_fraudsters)

        p_serial = self.fraud_mix["serial_return_abuse"]
        p_multi = self.fraud_mix["multi_account_abuse"]

        # 1. Multi-account fraud rings
        num_multi = int(num_fraudsters * p_multi)
        multi_candidates = candidates[:num_multi]
        # Form clusters of 3-5 users sharing same device/card
        for i in range(0, len(multi_candidates), 4):
            cluster = multi_candidates[i : i + 4]
            if len(cluster) > 1:
                shared_device = f"dev_fraud_ring_{i}"
                shared_card = f"pay_fraud_ring_{i}"
                shared_address = f"addr_fraud_ring_{i}"
                for member in cluster:
                    member.device_ids.append(shared_device)
                    member.payment_ids.append(shared_card)
                    if self.rng.random() < 0.7:
                        member.address_ids.append(shared_address)
                    fraud_targets.append((member, "multi_account_abuse", self._sample_difficulty()))

        # 2. Serial return abusers
        num_serial = int(num_fraudsters * p_serial)
        serial_candidates = candidates[num_multi : num_multi + num_serial]
        for c in serial_candidates:
            c.return_propensity = 0.95
            fraud_targets.append((c, "serial_return_abuse", self._sample_difficulty()))

        # 3. Wardrobers
        wardrobe_candidates = candidates[num_multi + num_serial :]
        for c in wardrobe_candidates:
            fraud_targets.append((c, "wardrobing", self._sample_difficulty()))

        return fraud_targets

    def simulate_traffic(self) -> None:
        """Simulates all user orders, deliveries, legit returns, and fraud injections."""
        print("Simulating e-commerce transactions and events...")
        self._inject_shared_household_hard_negatives()
        fraud_targets = self._inject_fraud_rings()
        fraud_map = {c.user_id: (scen, diff) for c, scen, diff in fraud_targets}

        # Initialize fraud scenario handlers
        serial_handler = SerialReturnAbuse(self.rng)
        multi_handler = MultiAccountAbuse(self.rng)
        wardrobe_handler = Wardrobing(self.rng)

        # Baseline orders per customer (Negative Binomial / Poisson distribution)
        avg_orders_per_cust = max(1, self.target_orders // self.num_customers)
        txn_counter = 0
        order_delivery_times: Dict[str, datetime] = {}

        for customer in self.customers:
            agent = CustomerAgent(customer=customer, rng=self.rng)
            # Create account creation event
            acct_time = self.start_date - timedelta(days=customer.account_age_days)
            self.scheduler.schedule_event(
                timestamp=acct_time,
                event_type="ACCOUNT_CREATED",
                actor_id=customer.user_id,
                payload={"region": customer.region, "segment": customer.segment},
            )

            # Order count for this customer
            n_orders = max(1, int(self.rng.gauss(avg_orders_per_cust, avg_orders_per_cust * 0.5)))
            # If serial abuser, increase order count
            if customer.user_id in fraud_map and fraud_map[customer.user_id][0] == "serial_return_abuse":
                n_orders = max(n_orders, self.rng.randint(10, 25))

            cust_orders: List[Order] = []

            for _ in range(n_orders):
                txn_counter += 1
                order_time = self.start_date + timedelta(
                    days=self.rng.uniform(1, self.sim_days - 20)
                )
                prod = self.rng.choice(self.products)
                seller = self.rng.choice(self.sellers)
                dev_id = self.rng.choice(customer.device_ids)
                addr_id = self.rng.choice(customer.address_ids)
                pay_id = self.rng.choice(customer.payment_ids)
                txn_id = f"txn_{txn_counter:08d}"

                order = Order(
                    transaction_id=txn_id,
                    user_id=customer.user_id,
                    product_id=prod.product_id,
                    seller_id=seller.seller_id,
                    timestamp=order_time,
                    price=prod.price,
                    payment_id=pay_id,
                    device_id=dev_id,
                    address_id=addr_id,
                )
                cust_orders.append(order)
                self.orders.append(order)

                # Record relationships in graph builder
                self.graph_builder.record_interaction(customer.user_id, "device", dev_id, order_time)
                self.graph_builder.record_interaction(customer.user_id, "address", addr_id, order_time)
                self.graph_builder.record_interaction(customer.user_id, "payment", pay_id, order_time)

                # Emitting browse -> add to cart -> purchase events
                for br_evt in agent.generate_browsing_events(order_time):
                    self.scheduler.schedule_event(
                        timestamp=br_evt.timestamp,
                        event_type=br_evt.event_type,
                        actor_id=br_evt.actor_id,
                        payload=br_evt.payload,
                    )

                self.scheduler.schedule_event(
                    timestamp=order_time,
                    event_type="PURCHASE",
                    actor_id=customer.user_id,
                    entity_ids={
                        "order_id": txn_id,
                        "product_id": prod.product_id,
                        "seller_id": seller.seller_id,
                        "device_id": dev_id,
                        "address_id": addr_id,
                        "payment_id": pay_id,
                    },
                    payload={"price": prod.price},
                )

                # Shipping & Delivery
                ship_time = order_time + timedelta(hours=self.rng.uniform(12, 36))
                self.scheduler.schedule_event(
                    timestamp=ship_time,
                    event_type="ORDER_SHIPPED",
                    actor_id="logistics",
                    entity_ids={"order_id": txn_id},
                    payload={},
                )

                deliv_days = self.rng.uniform(2.0, 5.0)
                deliv_time = ship_time + timedelta(days=deliv_days)
                order_delivery_times[txn_id] = deliv_time
                self.scheduler.schedule_event(
                    timestamp=deliv_time,
                    event_type="ORDER_DELIVERED",
                    actor_id="logistics",
                    entity_ids={"order_id": txn_id},
                    payload={},
                )

                # Legitimate return decision
                if customer.user_id not in fraud_map:
                    legit_res = agent.decide_legitimate_return(order, prod, seller, deliv_time)
                    if legit_res is not None:
                        ret_obj, ret_events = legit_res
                        self.returns.append(ret_obj)
                        self.hidden_labels.append(
                            HiddenLabel(
                                return_id=ret_obj.return_id,
                                is_fraud=0,
                                true_scenario="legitimate",
                                difficulty="none",
                            )
                        )
                        for ev in ret_events:
                            self.scheduler.schedule_event(
                                timestamp=ev.timestamp,
                                event_type=ev.event_type,
                                actor_id=ev.actor_id,
                                entity_ids=ev.entity_ids,
                                payload=ev.payload,
                            )

            # Inject fraud scenarios if customer is flagged
            if customer.user_id in fraud_map:
                scen, diff = fraud_map[customer.user_id]
                if scen == "serial_return_abuse":
                    fraud_results = serial_handler.apply(customer, self.products, cust_orders, diff, order_delivery_times)
                elif scen == "multi_account_abuse":
                    fraud_results = multi_handler.apply(customer, self.products, cust_orders, diff, order_delivery_times)
                else:
                    fraud_results = wardrobe_handler.apply(customer, self.products, cust_orders, diff, order_delivery_times)

                for ret_obj, h_label, ret_events in fraud_results:
                    self.returns.append(ret_obj)
                    self.hidden_labels.append(h_label)
                    for ev in ret_events:
                        self.scheduler.schedule_event(
                            timestamp=ev.timestamp,
                            event_type=ev.event_type,
                            actor_id=ev.actor_id,
                            entity_ids=ev.entity_ids,
                            payload=ev.payload,
                        )

    def export_data(self, output_dir: str = "data") -> Dict[str, int]:
        """Saves all generated datasets to Parquet format with strict schemas."""
        raw_dir = Path(output_dir) / "raw"
        gt_dir = Path(output_dir) / "ground_truth"
        raw_dir.mkdir(parents=True, exist_ok=True)
        gt_dir.mkdir(parents=True, exist_ok=True)

        print(f"Exporting raw tables to {raw_dir}...")

        # 1. Users
        users_df = pl.DataFrame([asdict(c) for c in self.customers])
        users_df.write_parquet(raw_dir / "users.parquet")

        # 2. Products
        products_df = pl.DataFrame([asdict(p) for p in self.products])
        products_df.write_parquet(raw_dir / "products.parquet")

        # 3. Sellers
        sellers_df = pl.DataFrame([asdict(s) for s in self.sellers])
        sellers_df.write_parquet(raw_dir / "sellers.parquet")

        # 4. Orders
        orders_df = pl.DataFrame([asdict(o) for o in self.orders])
        orders_df.write_parquet(raw_dir / "orders.parquet")

        # 5. Returns
        returns_df = pl.DataFrame([asdict(r) for r in self.returns])
        returns_df.write_parquet(raw_dir / "returns.parquet")

        # 6. Events (sorted chronologically)
        all_events = self.scheduler.get_all_events()
        events_dicts = []
        for e in all_events:
            events_dicts.append(
                {
                    "event_id": e.event_id,
                    "timestamp": e.timestamp,
                    "event_type": e.event_type,
                    "actor_id": e.actor_id,
                    "entity_ids": str(e.entity_ids),
                    "payload": str(e.payload),
                }
            )
        events_df = pl.DataFrame(events_dicts)
        events_df.write_parquet(raw_dir / "events.parquet")

        # 7. Relationships
        rels = self.graph_builder.get_relationships()
        rels_df = pl.DataFrame([asdict(r) for r in rels])
        rels_df.write_parquet(raw_dir / "relationships.parquet")

        # 8. Hidden Ground Truth Labels
        print(f"Exporting hidden labels to {gt_dir}...")
        gt_df = pl.DataFrame([asdict(h) for h in self.hidden_labels])
        gt_df.write_parquet(gt_dir / "hidden_labels.parquet")

        # 9. Simulation Metadata
        meta_file = Path(output_dir) / "simulation_metadata.json"
        meta_data = {
            "simulation_version": str(self.config.get("simulation_version", "0.1.0")),
            "config_version": str(self.config.get("config_version", "1.0.0")),
            "world_id": str(self.config.get("world_id", "A")),
            "random_seed": int(self.config.get("random_seed", 42)),
            "generator_timestamp": datetime.now().isoformat(),
        }
        with open(meta_file, "w") as f:
            json.dump(meta_data, f, indent=2)

        stats = {
            "users": len(self.customers),
            "products": len(self.products),
            "sellers": len(self.sellers),
            "orders": len(self.orders),
            "returns": len(self.returns),
            "events": len(all_events),
            "relationships": len(rels),
            "hidden_labels": len(self.hidden_labels),
        }
        print("Data generation summary:", stats)
        return stats
