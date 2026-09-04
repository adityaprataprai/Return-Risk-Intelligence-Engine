# Phase 0: Project Setup & Common Infrastructure

## Objective

Initialize the repository with the correct folder structure, configuration files, common logging, validation, and observability utilities. This phase creates the foundation for all later phases.

## Scope

- Create directory tree as specified below.
- Set up Python project with `pyproject.toml`.
- Add `.env.example`, `.gitignore`, `README.md`, `Makefile`.
- Implement common utilities:
  - Config loader (reads YAML/ENV)
  - Logging formatter
  - Basic Pydantic base model
  - Idempotency helper (stub)
  - Observability stubs (metrics placeholder)
- Define initial database schemas (PostgreSQL) for later phases (optional, can be deferred to Phase 7).
- Validate that project can be imported and a simple health check script runs.

## Required Files / Directories

```
return-risk-intelligence-engine/
├── README.md
├── docker-compose.yml                 # placeholder
├── .env.example
├── .gitignore
├── Makefile
├── docs/
│   ├── ARCHITECTURE.md                # already exists
│   ├── TECHNICAL_SPECIFICATION.md     # already exists
│   └── PHASES_INDEX.md                # this file
├── config/
│   ├── simulation/
│   │   └── default.yaml               # placeholder for Phase 1
│   ├── features/
│   │   └── registry.yaml              # placeholder for Phase 2
│   ├── economics/
│   │   └── merchant_profiles.yaml     # initial empty
│   └── policies/
│       └── decision_policy.yaml       # initial empty
├── src/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── config.py                  # Config loader class
│   │   ├── logging.py                 # setup_logging()
│   │   ├── observability.py           # metrics stubs, no-op functions
│   │   ├── idempotency.py             # simple idempotency key generator
│   │   └── utils.py                   # time helpers, hash functions
│   └── app.py                         # FastAPI app stub with /health
├── tests/
│   ├── __init__.py
│   └── test_health.py
├── scripts/
│   └── dev_setup.py                   # verifies environment
├── pyproject.toml
└── .env.example
```

## Technical Requirements

### 1. `pyproject.toml`

Use `poetry` or `pip` with dependencies:

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.110"
uvicorn = "^0.29"
pydantic = "^2.6"
pyyaml = "^6.0"
python-dotenv = "^1.0"
polars = "^0.20"
duckdb = "^0.10"
lightgbm = "^4.3"
xgboost = "^2.0"
shap = "^0.45"
redis = "^5.0"
numpy = "^1.26"
pandas = "^2.2"
joblib = "^1.3"
scikit-learn = "^1.4"
pyarrow = "^15.0"
httpx = "^0.27"
pytest = "^8.0"
pytest-asyncio = "^0.23"
```

### 2. `src/common/config.py`

Implement a `Config` class that:
- Loads YAML files from `config/`.
- Overrides values from environment variables using `os.environ`.
- Supports nested access via dot notation.
- Example usage: `Config("simulation/default").get("population.num_customers")`.

### 3. `src/common/logging.py`

Provide `setup_logging(level=logging.INFO)` that configures a JSON formatter for structured logs.

### 4. `src/common/observability.py`

Define placeholder functions:
- `increment_counter(name, value=1)` (no-op for now, will integrate Prometheus later)
- `record_latency(name, seconds)` (no-op)
- `set_gauge(name, value)` (no-op)

### 5. `src/common/idempotency.py`

Implement:
```python
def generate_idempotency_key(request_id: str, payload_hash: str) -> str:
    return hashlib.sha256(f"{request_id}:{payload_hash}".encode()).hexdigest()
```

### 6. `src/app.py`

Create FastAPI app with:
- `GET /health` returning `{"status": "ok", "version": "0.1.0"}`.
- CORS middleware placeholder.
- Include logging startup.

### 7. `Makefile`

Targets:
- `make install` – install dependencies
- `make test` – run tests
- `make run-api` – start FastAPI dev server
- `make lint` – run ruff/black if configured

### 8. `.env.example`

```
REDIS_URL=redis://localhost:6379
POSTGRES_DSN=postgresql://risk:risk@localhost:5432/return_risk
MODEL_REGISTRY_DIR=./model_registry
SHAP_WORKER_CONCURRENCY=4
DASHBOARD_URL=http://localhost:3000
AUTH_ISSUER=https://auth.example.com
```

## Acceptance Criteria

- Repository structure matches the above.
- `python -m src.app` starts FastAPI without errors.
- `curl http://localhost:8000/health` returns status ok.
- All imports succeed in a clean virtual environment after `make install`.
- Unit test `tests/test_health.py` passes.
- Logs are structured (JSON) and contain timestamp, level, message.
