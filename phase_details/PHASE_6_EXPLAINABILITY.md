# Phase 6: Explainability (SHAP)

## Objective

Implement asynchronous SHAP explanation generation. The scoring API must not wait for SHAP; instead, it queues an explanation job. A worker process computes TreeSHAP in raw margin space, groups features into semantic reasons, builds evidence, and stores an immutable explanation record.

## Scope

- Implement explanation queue (simple in-memory or Redis list).
- Create SHAP worker that processes jobs.
- Implement reason-code engine, semantic grouping, evidence builder.
- Store explanations in a database or file (PostgreSQL/JSON).
- Expose explanation retrieval endpoint (can be part of Phase 7 BFF or separate).

## Deliverables

- `src/explainability/__init__.py`
- `src/explainability/shap_worker.py`
- `src/explainability/reason_codes.py`
- `src/explainability/grouping.py`
- `src/explainability/evidence_builder.py`
- `src/explainability/store.py` (explanation persistence)
- `scripts/run_shap_worker.py`
- `config/explanation/reason_codes.yaml` (optional)

## Technical Requirements

### 1. Asynchronous Flow

When scoring endpoint returns response, it also publishes a message to a queue (e.g., Redis list `explanation_queue`) containing:
- request_id
- prediction snapshot (features, raw margin, calibrated probability, versions)
- feature vector (as ordered list)
- model/calibration metadata.

### 2. SHAP Worker

- Subscribes to queue.
- Loads the correct LightGBM model and `shap.TreeExplainer`.
- Computes SHAP values in raw margin space (default for binary trees).
- Groups SHAP values into semantic groups defined in `src/explainability/grouping.py`:
  - Graph Abuse
  - Velocity
  - Return Behavior
  - Transaction/Value
  - Sequence
  - Evidence Quality
- Selects top groups and maps to reason codes.

### 3. Reason Code Engine

Deterministic mapping from feature/group to reason codes, e.g.:
- Group `Graph Abuse` → reason code `NETWORK_ABUSE`
- Group `Velocity` → `HIGH_RETURN_VELOCITY`
- Each reason code has a template and eligible features.
- Cold-start / evidence-quality features are never mapped to punitive reasons; they go to data confidence.

### 4. Evidence Builder

For each reason code, construct concrete evidence from the feature values available at decision time:
- e.g., `returns_24h = 5` → "5 returns in the last 24h"
- `shared_device_accounts = 6` → "Device linked to 6 accounts in prior 30 days"
- Include timestamps and source.

### 5. Explanation Store

Persist explanation record as JSON to a file or PostgreSQL table `explanations`. Use the schema from the architecture doc.  
Provide a `GET /v1/risk/returns/{request_id}/explanation` endpoint (can be in the same FastAPI app or separate service).

### 6. Worker Reliability

- Handle failures with retries (bounded).
- Idempotency: don't duplicate if same request processed again.

## Acceptance Criteria

- After scoring a high-risk request, an explanation record appears within 2 seconds (local).
- Explanation contains raw margin, SHAP values, grouped attributions, reason codes, evidence, and versions.
- Cold-start features are not shown as punitive reasons (test).
- SHAP values reconstruct model output within tolerance.
- Endpoint returns `PENDING` initially, then `READY` after worker completes.
- No impact on scoring latency.
