# Phase 7: Dashboard Backend (BFF)

## Objective

Build a backend-for-frontend (BFF) service that exposes REST APIs for the merchant/risk dashboard. It aggregates data from scoring service, explanation store, raw events, and analytics to support review queues, case details, graph exploration, and financial metrics.

## Scope

- Implement FastAPI app as a separate service (`src/dashboard/api.py`).
- Endpoints for overview KPIs, review queue, case details, action submission, timeline, network graph, analytics, policies, health, and audit.
- Connect to PostgreSQL for operational data (cases, analyst actions, policies) or use a simple SQLite/JSON fallback.
- Use Redis to fetch graph data for network explorer.

## Deliverables

- `src/dashboard/__init__.py`
- `src/dashboard/api.py`
- `src/dashboard/schemas.py`
- `src/dashboard/services.py` (business logic)
- `src/dashboard/db.py` (database models/access)
- `src/dashboard/config.py`

## Technical Requirements

### 1. Database Schema (PostgreSQL)

Tables:
- `cases` (request_id, user_id, merchant_id, transaction_id, risk_score, action, created_at, status, assignee, decision_metadata)
- `analyst_actions` (action_id, case_id, analyst_id, action, override_reason, created_at)
- `policies` (policy_id, version, config, created_at)
- `audit_log` (event_id, request_id, timestamp, user, action, metadata)

### 2. API Endpoints

List from architecture doc:
```
GET  /api/overview/kpis
GET  /api/overview/risk-distribution
GET  /api/review-queue
GET  /api/cases/{request_id}
POST /api/cases/{request_id}/action
GET  /api/cases/{request_id}/explanation
GET  /api/cases/{request_id}/timeline
GET  /api/networks/{request_id}
GET  /api/analytics/fraud
GET  /api/analytics/financial-impact
GET  /api/policies
POST /api/policies/simulate
GET  /api/model-health
GET  /api/feature-health
GET  /api/system-health
GET  /api/audit
```

### 3. Integration

- `GET /api/cases/{request_id}` must combine:
  - Risk score and decision from scoring service (call its API or read from its stored decisions).
  - Explanation from explanation store.
  - Raw events timeline from events Parquet or DB.
  - Graph data from Redis.
- `POST /api/cases/{request_id}/action` records analyst decision and stores override reason.

### 4. Authentication

For this phase, implement simple API key auth or disable auth (noted as TODO for Phase 9). Provide placeholder for RBAC.

## Acceptance Criteria

- All endpoints respond with valid JSON.
- Review queue returns cases sorted by risk/priority.
- Case detail includes risk, decision, explanation, timeline.
- Action submission persists to database.
- Analytics endpoints return aggregated metrics.
- Can run dashboard BFF via `uvicorn src.dashboard.api:app`.
