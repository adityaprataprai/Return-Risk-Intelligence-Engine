# Phase 4: Inference API & Economic Decision Engine - Summary Report

## Overview
Phase 4 focused on designing, building, and benchmarking the synchronous real-time scoring service for return risk and economic decisioning using FastAPI. The objective was to expose a production-grade endpoint (`POST /v1/risk/returns/score`) capable of ingesting return requests, fetching precomputed features in-memory, running calibrated LightGBM model inference, evaluating merchant and product unit economics, and returning automated risk decisions (`APPROVE`, `VERIFY`, `BLOCK`) with quantified expected losses—strictly under 50ms latency.

To guarantee high throughput and sub-50ms response times, complex graph traversals and heavy SHAP calculations were strictly excluded from the critical synchronous scoring path (explanation status set to `"PENDING"` for asynchronous downstream workers). The resulting service achieves a **P50 latency of ~9.36ms** and **P95 latency of ~10.20ms**, with full schema compliance and built-in idempotency caching.

---

## Files Created and Their Purpose

### Core Inference Engine (`src/inference/`)
* **`__init__.py`**: Exposes public inference interfaces: `router`, `score_return`, `ContextResolver`, `EconomicDecisionEngine`, `InMemoryFeatureStore`, `ModelLoader`, `RedisClient`, and Pydantic schemas.
* **`schemas.py`**: Pydantic v2 data models defining the strict contract for `ReturnScoreRequest` and `ReturnScoreResponse` (including `RiskResult`, `DecisionResult`, `FeaturesMetadata`, `EconomicsMetadata`, and `ExplanationMetadata`).
* **`feature_store.py`**: High-speed `InMemoryFeatureStore` that loads feature Parquets into hash maps indexed by `transaction_id` and `return_id`, and provides automated cold-start fallback synthesis for novel transactions.
* **`model_loader.py`**: Loads the registered champion LightGBM model weights and isotonic calibrator from `model_registry/return-risk/1.0.0/`. Aligns incoming feature vectors with `feature_schema.json` and outputs calibrated probabilities and raw margin scores.
* **`context_resolver.py`**: Coordinates retrieval of feature vectors, merchant economic profiles, product category profiles, and decision policies.
* **`economic_engine.py`**: Computes financial payoffs and expected losses (direct fraud loss, salvage value, customer acquisition cost, and churn multipliers), mapping calibrated risk to optimal actions (`APPROVE`, `VERIFY`, `BLOCK`).
* **`redis_client.py`**: Modular Redis interface stub designed for seamless activation in Phase 5 online graph serving.
* **`api.py`**: FastAPI router defining `POST /v1/risk/returns/score`, featuring SHA-256 idempotency caching, structured latency tracking, and error handling.

### Application Integration & Configuration
* **`src/app.py`**: Mounted the inference router and wired component warmup into FastAPI's asynchronous lifespan.
* **`config/economics/product_profiles.yaml`**: Product category financial parameters (`cogs_rate`, `shipping_cost`, `return_shipping_cost`, `handling_cost`, `restocking_cost_rate`, `salvage_value_percentage`) versioned as `product-econ-4.2`.

### Tests & Verification
* **`tests/integration/test_score_endpoint.py`**: Integration tests verifying HTTP 200 responses, schema compliance, latency (< 50ms), idempotency caching, cold-start handling, unit economic logic, and validation error handling.
* **`scripts/verify_phase4.py`**: Acceptance verification script validating schema compliance, P50/P95 latency targets, economic decision mapping, and cold-start fallback execution.

---

## Performance & Acceptance Verification

### 1. Latency Benchmark Results
Evaluated locally on repeated scoring requests (10 iterations):

| Metric | Target Requirement | Measured Performance | Status |
| :--- | :--- | :--- | :--- |
| **P50 Latency** | `< 50.0 ms` | **9.36 ms** | **PASSED [✔] (5x faster than target)** |
| **P95 Latency** | `< 50.0 ms` | **10.20 ms** | **PASSED [✔]** |
| **Average Latency** | `< 50.0 ms` | **9.21 ms** | **PASSED [✔]** |

### 2. Economic Decision Engine Risk Mapping

| Fraud Risk ($p$) | Configured Policy Threshold | Prescribed Action | Quantified Expected Loss |
| :--- | :--- | :--- | :--- |
| **Low Risk ($p=0.10$)** | $p \le 0.25$ | **APPROVE** | **$652.00** |
| **Medium Risk ($p=0.50$)** | $0.25 < p \le 0.75$ | **VERIFY** | **$202.50** |
| **High Risk ($p=0.90$)** | $p > 0.75$ | **BLOCK** | **$112.50** |

### 3. API Contract Schema Alignment
The response payload was verified to match the exact architectural specification:
```json
{
  "request_id": "ret_verify_12345",
  "risk": {
    "probability": 0.6667,
    "model_version": "rr-lgbm-1.0.0",
    "calibration_version": "cal-isotonic-1.0",
    "raw_margin": 0.146
  },
  "decision": {
    "action": "VERIFY",
    "expected_loss": 155.0,
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

---

## Biggest Challenges Faced (Chronological Order)

1. **Keeping Real-Time Latency Under 50ms Without In-Path Bottlenecks**
   * *Challenge*: Graph traversals and SHAP explanation calculations take hundreds of milliseconds to multiple seconds, making them incompatible with synchronous API SLA requirements (< 50ms).
   * *Solution*: Strictly eliminated graph expansions and tree SHAP calculations from the synchronous scoring critical path. Precomputed features are fetched in sub-millisecond time via memory-mapped lookup tables, and explanation status is marked `"PENDING"` for asynchronous downstream queue workers. This resulted in an average response time of ~9.2ms.

2. **Handling Unseen Requests & Cold-Start Synthesis**
   * *Challenge*: If a return request arrives for an order or user not present in precomputed offline feature parquets, the system must not fail or return HTTP 500.
   * *Solution*: Implemented automated cold-start fallback synthesis in `InMemoryFeatureStore._build_cold_start_features()`. When a transaction ID is missing, the store populates baseline values (first purchase flags, default category rates, user history counts = 0), allowing the model and economic engine to score novel transactions gracefully.

3. **Asymmetric Economic Loss Formulation**
   * *Challenge*: In return risk management, costs are asymmetric: approving fraud causes direct refund, shipping, and handling loss (offset by salvage value), whereas false positive blocking burns customer acquisition cost (CAC) multiplied by lifetime churn impact.
   * *Solution*: Designed `EconomicDecisionEngine` to quantify expected loss dynamically using both merchant profiles (`customer_acquisition_cost`, `churn_cost_multiplier`) and product category parameters (`cogs_rate`, `return_shipping_cost`, `restocking_cost_rate`, `salvage_value_percentage`).

4. **Idempotency Across Concurrent Return Submissions**
   * *Challenge*: Rapid duplicate submissions or retry spikes from merchant gateways could trigger multiple scoring evaluations and inconsistent responses.
   * *Solution*: Built an in-memory SHA-256 idempotency cache combining `request_id` and serialized payload hash, immediately returning the cached `ReturnScoreResponse` on duplicate submissions.

5. **Pydantic v2 Schema Deprecation Migration**
   * *Challenge*: Using `Field(..., example=...)` produced 28 `PydanticDeprecatedSince20` warnings under Pydantic 2.x.
   * *Solution*: Refactored all schema definitions to use `examples=[...]`, eliminating warnings and ensuring future compatibility with Pydantic v3.
