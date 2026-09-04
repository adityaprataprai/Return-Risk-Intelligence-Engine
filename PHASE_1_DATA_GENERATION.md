# Phase 1: Synthetic Data Generation

## Objective

Implement the synthetic data generator that creates an e-commerce ecosystem with users, products, sellers, devices, addresses, payments, orders, returns, events, and relationships. The generator must produce realistic behaviour for legitimate customers and inject three fraud families (Serial Return Abuse, Multi-Account Abuse, Wardrobing) with difficulty variants and hard negatives. All data must be timestamped and hidden ground truth stored separately.

## Scope

- Create the `src/simulation` package.
- Implement entity classes, agent state, event scheduler, fraud scenarios, financial engine, graph builder, and top-level generator.
- Generate **World A** (baseline) with 10,000 users, ~100,000 orders, and corresponding returns/events.
- Save raw data as Parquet files in `data/raw/` and hidden truth in `data/ground_truth/`.
- Provide a CLI script `scripts/generate_data.py`.

## Deliverables

```
src/simulation/
├── __init__.py
├── entities.py          # dataclasses for each entity
├── agents.py            # CustomerState and behaviour logic
├── event_scheduler.py   # discrete event simulation clock
├── fraud_scenarios.py   # three fraud scenario policies
├── financial_engine.py  # unit economics calculations
├── graph_builder.py     # relationship graph construction
└── generator.py         # main simulation orchestrator
```

Also:
- `config/simulation/world_a.yaml` – configuration for World A.
- `scripts/generate_data.py` – entrypoint.

## Technical Requirements

### 1. Entity Model

Use Pydantic models or dataclasses with the following fields:

**Customer**
```
user_id: str
account_age_days: float
segment: str
region: str
purchase_propensity: float  # latent
return_propensity: float    # latent
fraud_propensity: float     # latent
price_sensitivity: float
delivery_tolerance: int
category_preferences: dict
trust_state: str
device_ids: list[str]
address_ids: list[str]
payment_ids: list[str]
```

**Product**
```
product_id: str
category: str
price: float
cogs: float
shipping_cost: float
return_shipping_cost: float
handling_cost: float
restocking_cost: float
salvage_value_percentage: float
```

**Seller**
```
seller_id: str
quality_score: float
fulfillment_performance: float
age_days: int
```

**Device**
```
device_id: str
type: str
os: str
first_seen: datetime
```

**Address**
```
address_id: str
region: str
city: str
```

**Payment**
```
payment_id: str
type: str
age_days: int
```

**Order**
```
transaction_id: str
user_id: str
product_id: str
seller_id: str
timestamp: datetime
price: float
payment_id: str
device_id: str
address_id: str
```

**Return**
```
return_id: str
transaction_id: str
request_time: datetime
reason: str
condition: str
refund_amount: float
days_to_return: float
inspection_result: str   # only for evaluation, not available at decision time
logistics_costs: float
salvage_value: float
```

**Event**
```
event_id: str
timestamp: datetime
event_type: str
actor_id: str
entity_ids: dict
payload: dict
```

**Relationship**
```
user_id: str
entity_type: str
entity_id: str
first_seen: datetime
last_seen: datetime
```

### 2. Fraud Scenarios

Implement three classes, each with a method `apply(customer, current_time, context) -> list[Event]` that generates the sequence of events for a fraud instance.

#### Serial Return Abuse
- Purchase bursts followed by clustered returns.
- Easy variant: very high return velocity (e.g., 5 returns per week).
- Moderate: high but overlapping with legitimate high-returners.
- Stealthy: lower volume, high-value returns.

#### Multi-Account Abuse
- Multiple users sharing device/address/payment.
- Creates graph edges between accounts.
- Easy: shared device + shared address.
- Moderate: one shared entity.
- Stealthy: sparse distributed links across several entities.
- Must also create hard negative family sharing (legitimate shared household).

#### Wardrobing
- Purchase → delivery → short usage → return.
- Easy: return within 1 day of delivery for high-value items.
- Moderate: moderate duration + repeat.
- Stealthy: longer duration, high-value, normal purchase profile.

### 3. Agent Lifecycle

Each customer agent transitions through states:
```
observe environment → update internal state → calculate action probabilities → choose action → emit event → update history → advance clock
```
Use stochastic distributions:
- Purchase count per agent: Negative Binomial / Poisson.
- Order values: Lognormal/Gamma.
- Return probability: logistic function of price, delivery delay, customer return propensity, etc.

### 4. Event Vocabulary

Support events:
```
ACCOUNT_CREATED
BROWSE
ADD_TO_CART
PURCHASE
PAYMENT
ORDER_CANCELLED
ORDER_SHIPPED
ORDER_DELIVERED
DELIVERY_DELAY
RETURN_REQUESTED
RETURN_PICKED_UP
RETURN_RECEIVED
RETURN_REJECTED
REFUND_ISSUED
DEVICE_CHANGED
ADDRESS_CHANGED
PAYMENT_METHOD_CHANGED
```

### 5. Financial Engine

Compute per transaction:
```
gross_exposure = refund_amount + return_shipping_cost + handling_cost + restocking_cost
recoverable_amount = item_value * salvage_value_percentage
net_return_cost = gross_exposure - recoverable_amount
```
Return these as part of `Order`/`Return` records; `estimated_*` features will be derived later.

### 6. Graph Builder

Maintain edge lists for:
- User-Device
- User-Address
- User-Payment
- Optionally User-IP (if simulated)

When a purchase/return occurs, add/update relationship with `first_seen` and `last_seen`.

### 7. Configuration (`world_a.yaml`)

```yaml
simulation_version: 0.1.0
world_id: A
random_seed: 42
population:
  num_customers: 10000
  num_products: 500
  num_sellers: 50
  num_devices: 12000
  num_addresses: 8000
  num_payments: 9000
fraud_mix:
  serial_return_abuse: 0.4
  multi_account_abuse: 0.3
  wardrobing: 0.3
difficulty:
  easy: 0.4
  moderate: 0.4
  stealthy: 0.2
hard_negatives:
  high_return_legit: 0.03
  family_shared_household: 0.02
transaction_scale: 100000
```

### 8. Output Data Format

Save as Parquet using `polars` or `pyarrow`:
- `data/raw/users.parquet`
- `data/raw/products.parquet`
- `data/raw/sellers.parquet`
- `data/raw/orders.parquet`
- `data/raw/returns.parquet`
- `data/raw/events.parquet`
- `data/raw/relationships.parquet`
- `data/ground_truth/hidden_labels.parquet` containing `return_id`, `is_fraud`, `true_scenario`, `difficulty`

### 9. CLI Script

`scripts/generate_data.py`:
- Reads config path as argument.
- Generates data and writes to `data/raw/` and `data/ground_truth/`.
- Includes basic validation: no future events, referential integrity.

## Acceptance Criteria

- All Parquet files exist and have correct schemas.
- Total orders ≈ 100k, returns ≈ (baseline return rate ~10–20%) + fraud injected.
- Event timestamps are chronologically sorted per user.
- No return event occurs before its corresponding delivery event.
- Hidden labels are not present in raw feature tables.
- Fraud scenario counts match config mix (±10%).
- Graph relationships include legitimate shared households and fraud rings.
- The generator seeds produce reproducible results when same seed is used.
- Run `scripts/generate_data.py` and verify all output files.
