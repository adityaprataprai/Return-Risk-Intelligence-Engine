# Phase 5: Redis Online State & Graph Processor

## Objective

Replace the in-memory feature store with Redis for low-latency online feature retrieval. Implement asynchronous graph processor that materialises graph metrics into Redis. Enable the scoring service to read features and graph metrics from Redis in O(1) time.

## Scope

- Implement online feature builder that processes events and updates Redis keys.
- Implement graph processor that computes graph metrics (connected components, shared entity counts) asynchronously.
- Update `ContextResolver` to use Redis for features and graph metrics.
- Add graph freshness metadata to response.

## Deliverables

- `src/features/online_builder.py`
- `src/features/graph_processor.py`
- `src/inference/redis_client.py` (real implementation)
- Updated `src/inference/context_resolver.py`
- `scripts/replay_events.py` – replays events from Parquet to populate Redis.
- `scripts/run_graph_processor.py` – background graph worker.

## Technical Requirements

### 1. Redis Key Design

```
risk:user:{user_id}:features:v2
risk:device:{device_id}:features:v2
risk:address:{address_id}:features:v2
risk:payment:{payment_id}:features:v2
risk:user:{user_id}:graph:v2
risk:merchant:{merchant_id}:economics:v1
risk:product:{product_id}:economics:v1
risk:category:{category}:economics:v1
```

Each key stores a JSON object with:
```json
{
  "feature_values": {...},
  "feature_timestamp": "2026-09-02T21:40:11Z",
  "version": "fv-2.1",
  "ttl_ms": 60000
}
```

### 2. Online Feature Builder

- Inputs: raw events (from Parquet or a live stream).
- For each event, update relevant Redis keys:
  - User keys: counts, sums, recency, etc.
  - Device/Address/Payment keys: distinct users, counts.
- Use Redis pipeline for batch updates.
- TTL set according to feature registry.

### 3. Graph Processor

- Runs as a background process consuming `relationships` events.
- Maintains a graph state (in memory or file) and recomputes metrics:
  - `linked_accounts_1hop`
  - `linked_accounts_2hop`
  - `shared_device_accounts`
  - `shared_address_accounts`
  - `shared_payment_accounts`
  - `high_return_neighbor_count`
  - `connected_component_size`
- After each update (or batch), write materialised metrics to `risk:user:{user_id}:graph:v2`.
- Include `graph_last_updated_at`, `graph_version`, `feature_age` in the stored object.

### 4. Context Resolver Update

Modify `ContextResolver`:
- Fetch user/device/address/payment features from Redis using IDs from request.
- Fetch graph features from Redis.
- Fetch economic profiles from Redis (or config fallback).
- Compute economic context from fetched profiles.
- If Redis unavailable, use fallback to config or degraded policy.

### 5. Event Replayer Script

`scripts/replay_events.py`:
- Reads `data/raw/events.parquet` sorted by timestamp.
- Emits events to online feature builder to simulate real-time ingestion.

### 6. Graph Freshness

Response metadata must include:
- `graph_version`
- `graph_age_ms` (difference between current time and `graph_last_updated_at`).

## Acceptance Criteria

- Redis contains user/device/address/payment keys populated by replayer.
- Graph metrics are present and consistent with offline computed graph features.
- Scoring endpoint retrieves features from Redis and returns with latency < 50ms.
- Graph age is reported.
- Integration test: replay events, then score a known fraud case and verify feature values match offline.
