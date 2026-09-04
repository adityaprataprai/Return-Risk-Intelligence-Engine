# Phase 2: Offline Feature Engineering

## Objective

Implement the feature registry and offline feature builder that computes point-in-time features from raw events. The output will be a model-ready training dataset with strict temporal correctness.

## Scope

- Create feature registry definitions (config/features/registry.yaml).
- Build offline feature builder using Polars/DuckDB.
- Compute all features listed in Section 5 of the Feature Engineering Strategy.
- Ensure point-in-time correctness, cold-start handling, and fallback baselines.
- Save train/test/validation feature Parquet files.

## Deliverables

- `src/features/__init__.py`
- `src/features/registry.py` – loads registry YAML and validates features.
- `src/features/offline_builder.py` – computes features from raw data.
- `src/features/validation.py` – point-in-time leakage tests, range checks.
- `config/features/registry.yaml`
- `scripts/build_features.py`

## Technical Requirements

### 1. Feature Registry

The registry is a YAML file listing each feature with:
- name, entity, source_event, aggregation, window, available_at_rule, ttl, version, owner, fraud_mechanism.

Example:

```yaml
features:
  - name: returns_24h
    entity: user
    source_event: RETURN_REQUESTED
    aggregation: count
    window: 24h
    available_at_rule: event.timestamp
    ttl: 60s
    version: fv-2.1
    owner: risk_ml
    fraud_mechanism: serial_return_abuse
  # ... all features from the spec (see sections 5 and 19.7 of Feature Engineering Strategy)
```

Include **all** features listed in the V1 feature specification table plus cold-start features.

### 2. Offline Builder

Input: raw Parquet files from Phase 1.
Output: one row per return request (the prediction target) with all features as of that timestamp.

Steps:
1. Load users, products, orders, returns, events, relationships.
2. For each return request in `returns.parquet`:
   - Filter events with timestamp <= return_request_time.
   - Compute user-level aggregates (counts, sums, rates, recency).
   - Compute entity-level aggregates (device, address, payment).
   - Compute graph metrics from `relationships` (precompute connected components and neighbour counts using a time-aware snapshot).
   - Compute behavioural deviations using user baseline (with fallback to category/merchant if insufficient support).
   - Compute economic features from order/product financials.
   - Add cold-start flags.
3. Join all features into a single `features` table with columns matching the registry exactly.
4. Save as Parquet files:
   - `data/features/train_features.parquet` (World A most recent 70% temporally)
   - `data/features/validation_features.parquet` (World A next 15%)
   - `data/features/test_features.parquet` (World A oldest 15%)

### 3. Point-in-Time Correctness

- Every feature must have an `available_at` <= `return_request_time`.
- The builder must use only events that occurred before the decision timestamp.
- Graph metrics must be computed from relationships active at that time (i.e., `first_seen <= timestamp` and `last_seen >= timestamp` or `last_seen is null`).  
  Simulate async graph freshness by using a snapshot: the graph state as of the latest graph refresh before the return timestamp. For offline, assume async refresh latency = 0 for simplicity but include `graph_last_updated_at` = timestamp of last graph event before the decision.

### 4. Cold-Start Features

Add:
- `is_first_purchase`
- `account_age_hours`
- `account_age_under_24h`
- `has_prior_orders`
- `has_prior_returns`
- `user_history_count`
- `baseline_support_count`
- `used_category_fallback`

Fallback hierarchy for behavioural deviations:
1. User baseline if `user_history_count >= 5`
2. Category/merchant baseline if user insufficient
3. Global/merchant baseline

Set `used_category_fallback` / `baseline_support_count` accordingly.

### 5. Validation

Implement `src/features/validation.py` with tests:
- Schema check: all features present, correct types.
- Range checks: rates in [0,1], counts >=0.
- Point-in-time leakage test: reconstruct a small sample and verify no feature uses future events.
- Missingness report.

## Acceptance Criteria

- Feature dataset exists with expected number of rows (one per return request).
- No feature has `available_at > decision_timestamp` (checked by test).
- All registry features are present.
- Feature distributions are reasonable (e.g., return_rate_30d between 0 and 1).
- A trained LightGBM baseline (quick fit) achieves at least AUROC 0.70 on test set (indicates features are informative).
- `scripts/build_features.py` runs and produces outputs.
