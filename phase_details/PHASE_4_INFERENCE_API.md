# Phase 4: Inference API & Economic Decision Engine

## Objective

Build the synchronous scoring service using FastAPI. It must accept a return request, retrieve pre-computed features (via an online feature store, initially in-memory), run model inference, calibrate probability, and return an economic action (`APPROVE`/`VERIFY`/`BLOCK`).

## Scope

- Implement request/response schemas (Pydantic).
- Create online feature store interface (initially in-memory from Parquet).
- Implement context resolver to fetch features and economic profiles.
- Implement economic decision engine.
- Build FastAPI endpoint `POST /v1/risk/returns/score`.
- Ensure no SHAP or graph traversal in critical path.

## Deliverables

- `src/inference/__init__.py`
- `src/inference/schemas.py`
- `src/inference/model_loader.py`
- `src/inference/redis_client.py` (placeholder, not used yet)
- `src/inference/context_resolver.py`
- `src/inference/economic_engine.py`
- `src/inference/api.py`
- `src/inference/feature_store.py` (in-memory Parquet loader)
- `tests/integration/test_score_endpoint.py`

## Technical Requirements

### 1. API Contract

**Endpoint**: `POST /v1/risk/returns/score`

Request body (as defined in architecture doc):
```json
{
  "request_id": "ret_12345",
  "merchant_id": "m_102",
  "user_id": "usr_981",
  "transaction_id": "txn_12891",
  "product_id": "prod_7781",
  "timestamp": "2026-09-02T21:40:11Z",
  "refund_amount": 8420,
  "order_amount": 10500,
  "product_category": "electronics",
  "device_id": "dev_391",
  "address_id": "addr_120",
  "payment_id": "pay_883"
}
```

Response:
```json
{
  "request_id": "ret_12345",
  "risk": {
    "probability": 0.874,
    "model_version": "rr-lgbm-1.0.0",
    "calibration_version": "cal-1.0",
    "raw_margin": 1.93
  },
  "decision": {
    "action": "VERIFY",
    "expected_loss": 812.40,
    "policy_version": "policy-3.0"
  },
  "features": {
    "feature_version": "fv-2.1",
    "graph_version": "g0000",
    "graph_age_ms": 0
  },
  "economics": {
    "merchant_profile_version": "merchant-econ-1.7",
    "product_profile_version": "product-econ-4.2",
    "profile_freshness_ms": 1800
  },
  "explanation": {
    "status": "PENDING"
  }
}
```

### 2. Online Feature Store (In-Memory)

- Load the feature Parquet file (`data/features/train_features.parquet` and others) into a dictionary keyed by `return_id` or `transaction_id`.
- At scoring time, look up the feature row for the given `transaction_id` from the feature store.  
  If not found (e.g., new return not in dataset), return a cold-start feature vector based on request fields and defaults.

### 3. Context Resolver

`ContextResolver` class:
- Inputs: request object.
- Outputs: `ml_features: dict`, `economic_context: dict`, `metadata: dict`.
- Steps:
  1. Validate request.
  2. Fetch features from `FeatureStore`.
  3. Fetch economic profiles from a local config file (`config/economics/*.yaml`) or Redis (Phase 5).
  4. Validate freshness and versions.

### 4. Economic Engine

Implement `EconomicDecisionEngine` class with method `decide(probability, economic_context, policy) -> Decision`.
- Action-specific expected cost formula as given.
- Economic profiles loaded from server config.
- Example policy version `policy-3.0`.

### 5. Model Loader

- Load LightGBM model and calibration object at startup.
- Validate feature order matches `feature_schema.json`.

### 6. FastAPI App

- Add `/v1/risk/returns/score` endpoint.
- Include request validation, idempotency check, structured logging.
- Return response without SHAP.

## Acceptance Criteria

- Endpoint responds within 50ms (local) for a sample request.
- Response matches schema; probability is calibrated.
- Action is one of `APPROVE`, `VERIFY`, `BLOCK`.
- Economic decision uses configured profiles; testing with known risk levels yields expected actions.
- Unit test for economic engine passes with known inputs/outputs.
- `pytest tests/integration/test_score_endpoint.py` passes.
