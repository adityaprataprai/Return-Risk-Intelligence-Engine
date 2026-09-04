# Phase 9: Observability, Deployment & Final Polish

## Objective

Add production-ready observability, logging, monitoring, Docker deployment, and final integration tests. Ensure all services can run via docker-compose. Document deployment steps.

## Scope

- Integrate Prometheus metrics into FastAPI services (scoring, dashboard BFF).
- Add structured logging with request IDs.
- Create Dockerfiles for each service.
- Create docker-compose.yml orchestrating all services.
- Add health checks and readiness probes.
- Add load tests and basic CI pipeline.
- Final security review and README update.

## Deliverables

- `deployment/Dockerfile.api`
- `deployment/Dockerfile.dashboard`
- `deployment/Dockerfile.frontend`
- `deployment/Dockerfile.shap_worker`
- `deployment/Dockerfile.graph_processor`
- `docker-compose.yml`
- `scripts/run_all.sh`
- `tests/load/locustfile.py`
- `.github/workflows/ci.yml` (optional)
- Updated `README.md` with quickstart.

## Technical Requirements

### 1. Observability

- Use `prometheus-fastapi-instrumentator` to expose `/metrics` on both API services.
- Define custom metrics:
  - `risk_score_requests_total`
  - `risk_score_latency_seconds`
  - `economic_decision_total{action}`
  - `shap_queue_depth`
  - `graph_feature_age_seconds`
- Use structured logging with `request_id` injected via middleware.

### 2. Dockerfiles

- API service: Python 3.11 slim, copy src, install requirements, run `uvicorn src.app:app`.
- SHAP worker: same image but different entrypoint `python scripts/run_shap_worker.py`.
- Graph processor: same, runs `python scripts/run_graph_processor.py`.
- Dashboard BFF: separate Python image.
- Frontend: Next.js build, server with `next start`.

### 3. Docker Compose

Services:
- `redis` (Redis 7)
- `api` (scores requests)
- `shap-worker`
- `graph-processor`
- `dashboard-bff`
- `frontend`
- `postgres` (optional, for dashboard data)
- `prometheus`
- `grafana`

Ensure proper environment variables and network.

### 4. Health Checks

- Each service exposes `/health`.
- Compose healthcheck with `curl`.
- Readiness: API waits for Redis, etc.

### 5. Load Testing

Provide Locust file to test scoring endpoint under concurrency. Set target: p95 < 100ms.

### 6. CI Pipeline

GitHub Actions:
- Install dependencies
- Run unit tests
- Build Docker images
- Run integration tests with docker-compose

### 7. Final Documentation

Update README with:
- Architecture overview
- Quickstart with docker-compose
- How to generate data, train model, start services
- API examples
- Screenshots (optional)

## Acceptance Criteria

- `docker-compose up` starts all services without errors.
- Prometheus scrapes metrics from API and dashboard.
- Grafana can visualise metrics (basic dashboard).
- Load test shows API p95 < 100ms under 100 concurrent users.
- All tests pass from Phase 0–8.
- README is clear enough for a new developer to run.
