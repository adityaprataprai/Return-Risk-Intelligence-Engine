from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class Customer:
    user_id: str
    account_age_days: float
    segment: str
    region: str
    purchase_propensity: float
    return_propensity: float
    fraud_propensity: float
    price_sensitivity: float
    delivery_tolerance: int
    category_preferences: Dict[str, float]
    trust_state: str
    device_ids: List[str] = field(default_factory=list)
    address_ids: List[str] = field(default_factory=list)
    payment_ids: List[str] = field(default_factory=list)


@dataclass
class Product:
    product_id: str
    category: str
    price: float
    cogs: float
    shipping_cost: float
    return_shipping_cost: float
    handling_cost: float
    restocking_cost: float
    salvage_value_percentage: float


@dataclass
class Seller:
    seller_id: str
    quality_score: float
    fulfillment_performance: float
    age_days: int


@dataclass
class Device:
    device_id: str
    type: str
    os: str
    first_seen: datetime


@dataclass
class Address:
    address_id: str
    region: str
    city: str


@dataclass
class Payment:
    payment_id: str
    type: str
    age_days: int


@dataclass
class Order:
    transaction_id: str
    user_id: str
    product_id: str
    seller_id: str
    timestamp: datetime
    price: float
    payment_id: str
    device_id: str
    address_id: str


@dataclass
class Return:
    return_id: str
    transaction_id: str
    request_time: datetime
    reason: str
    condition: str
    refund_amount: float
    days_to_return: float
    inspection_result: str
    logistics_costs: float
    salvage_value: float


@dataclass
class Event:
    event_id: str
    timestamp: datetime
    event_type: str
    actor_id: str
    entity_ids: Dict[str, Any] = field(default_factory=dict)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Relationship:
    user_id: str
    entity_type: str
    entity_id: str
    first_seen: datetime
    last_seen: datetime


@dataclass
class HiddenLabel:
    return_id: str
    is_fraud: int
    true_scenario: str
    difficulty: str
