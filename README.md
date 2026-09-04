# 🛡️ Razorpay Return-Risk Intelligence Engine

An enterprise-grade, real-time Return Risk Scoring and Automated Economic Decisioning Platform built to combat e-commerce return abuse—including **Serial Returners**, **Organized Fraud Syndicates**, and **Wardrobing**—while preserving merchant profit margins and maintaining frictionless, instant refunds for trustworthy customers.

---

## ⚡ Quickstart — Run the Entire System in Seconds

### 🚀 Option 1: One-Command Docker Deployment (Recommended)
Every service (Scoring API, Dashboard BFF, Next.js Frontend, TreeSHAP Worker, Graph Processor, Redis, Prometheus, and Grafana) is fully containerized with pre-trained models and seed data.

```bash
docker compose up --build
```

**Access Services Immediately:**
* 🖥️ **Investigation Dashboard**: [http://localhost:3000](http://localhost:3000)
* ⚡ **Scoring API & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
* 🛠️ **Dashboard BFF & Swagger Docs**: [http://localhost:8001/docs](http://localhost:8001/docs)
* 📊 **Grafana Telemetry Monitoring**: [http://localhost:3001](http://localhost:3001) (`admin` / `admin`)
* 📈 **Prometheus Metrics**: [http://localhost:9090](http://localhost:9090)

---

### 💻 Option 2: Quick Local Execution (No Docker Required)

#### Prerequisites
- **Python 3.11+**
- **Node.js 18+** & npm
- (Optional) **Redis 7** (if not installed, in-memory fallbacks activate automatically)

#### Step 1: Install Dependencies
```bash
# Clone the repository
git clone https://github.com/adityaprataprai/AI-Risk-Manager--RazorPay-.git
cd AI-Risk-Manager--RazorPay-

# Setup Python virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install Python dependencies (pre-configured in pyproject.toml)
pip install -e ".[dev]"
pip install prometheus-client prometheus-fastapi-instrumentator locust

# Install Frontend dependencies
cd frontend
npm install
cd ..
```

#### Step 2: Launch All Services in One Command

**On Windows (PowerShell):**
```powershell
.\scripts\run_all.ps1
```

**On Linux / macOS (Bash):**
```bash
chmod +x scripts/run_all.sh
./scripts/run_all.sh
```

Then in a second terminal, launch the Next.js frontend:
```bash
cd frontend
npm run dev
```
Open **[http://localhost:3000](http://localhost:3000)** in your browser!

---

## 🏗️ System Architecture

```
                                  ┌─────────────────────────┐
                                  │   Merchant E-Commerce   │
                                  │   Checkout / Returns    │
                                  └────────────┬────────────┘
                                               │ POST /v1/risk/returns/score (<15ms)
                                               ▼
                              ┌─────────────────────────────────┐
                              │     FastAPI Scoring Service     │  <-- Port 8000
                              │       (Inference Engine)        │
                              └────┬───────────┬───────────┬────┘
                                   │           │           │
             Feature Resolution    │           │           │ Async SHAP Enqueue (<0.5ms)
                                   ▼           │           ▼
                   ┌───────────────────┐       │   ┌───────────────────┐
                   │   Redis 7 State   │       │   │  Redis Queue &    │
                   │ & Bipartite Graph │       │   │  TreeSHAP Worker  │
                   └───────────────────┘       │   └───────────────────┘
                                               │
                                               │ Action (APPROVE / VERIFY / BLOCK)
                                               ▼
                                   ┌───────────────────────┐
                                   │  Economic Decision &  │
                                   │  Policy Rule Engine   │
                                   └───────────────────────┘

        ========================================================================
        Investigation, Case Review & Analytics (Merchant & Risk Operations)
        ========================================================================

    ┌───────────────────────────┐             ┌───────────────────────────┐
    │   Next.js 14 Dashboard    │ ──────────> │    Dashboard BFF (FastAPI)│ <-- Port 8001
    │  (App Router, Port 3000)  │  HTTP Proxy │    (SQLite WAL / Port 8001)│
    └───────────────────────────┘             └─────────────┬─────────────┘
                                                            │
                  ┌─────────────────────────────────────────┘
                  │
                  ▼
    ┌─────────────┴─────────────┐     ┌───────────────────────────┐
    │  Prometheus Scraper       │ ──> │  Grafana Telemetry        │ <-- Port 3001
    │  (Port 9090)              │     │  (Provisioned Dashboards) │
    └───────────────────────────┘     └───────────────────────────┘
```

---

## 🌟 Key Engineering Capabilities

1. **Sub-15ms Synchronous Scoring (SLA < 50ms)**:
   - High-performance feature resolution across 53 point-in-time features.
   - Pre-loaded LightGBM booster with isotonic calibration producing calibrated posterior probabilities.
   - Idempotent request caching via cryptographic payload fingerprinting.

2. **Economic Decision Engine**:
   - Computes expected financial loss:
     $$\mathbb{E}[\text{Loss}] = P(\text{Abuse}) \times (\text{Order Amount} - \text{Salvage Value}) + \text{Shipping Cost}$$
   - Preserves merchant unit economics with automated action assignment:
     - `APPROVE`: Instant frictionless refund.
     - `VERIFY`: Routed to prioritized risk analyst review queue.
     - `BLOCK`: Direct denial of fraudulent return claim.

3. **Asynchronous TreeSHAP Explainability**:
   - Zero impact on synchronous scoring latency (<0.5ms enqueue overhead).
   - Dedicated background daemon computing TreeSHAP in raw margin space with exact additivity ($\Delta = 0.00$).
   - Categorizes attributions into 6 semantic buckets (`graph_abuse`, `velocity`, `return_behavior`, `transaction_value`, `sequence`, `evidence_quality`).
   - Generates human-interpretable, regulatory-compliant reason codes and concrete evidence strings.

4. **Real-Time Bipartite Graph Engine**:
   - Ingests entity relationship edges across customers, shared device fingerprints, physical shipping addresses, and payment tokens.
   - Materializes 1-hop and 2-hop linkage features in Redis to catch multi-account organized fraud syndicates.

5. **Investigation Workbench & Dashboard**:
   - **Next.js 14 App Router** frontend featuring a tailored dark-glassmorphism aesthetic.
   - **7 Operational Pages**:
     - **Executive Overview** (`/overview`): Decile probability distribution, approval rates, loss prevented, review queue size.
     - **Prioritized Review Queue** (`/review-queue`): Prioritized case review triage with search and status filtering.
     - **Case Workbench** (`/cases/{id}`): Detailed order economics, TreeSHAP attributions, behavioral event timeline, and manual decision dialogs (`APPROVE`, `REJECT`, `ESCALATE`).
     - **Identity Network Explorer** (`/networks`): Interactive SVG canvas visualizing multi-hop fraud syndicates.
     - **ROI & Typologies** (`/analytics`): Wardrobing, syndicates, and financial ROI savings (6.4x ROI).
     - **Policy Simulator** (`/policies`): Interactive sandbox simulating threshold tradeoffs between workload and fraud loss.
     - **System Telemetry** (`/health`): LightGBM champion metrics (AUROC 0.9348, AUPRC 0.6364) and subsystem status.

6. **Production-Ready Observability**:
   - Custom Prometheus metrics (`risk_score_requests_total`, `risk_score_latency_seconds`, `economic_decision_total`, `shap_queue_depth`, `graph_feature_age_seconds`).
   - Structured JSON logging with `X-Request-ID` correlation ID tracking across microservices.

---

## 📡 Live API Usage Examples

### 1. Score a Return Request (`POST /v1/risk/returns/score`)

```bash
curl -X POST "http://localhost:8000/v1/risk/returns/score" \
  -H "Content-Type: application/json" \
  -H "X-Request-ID: req_demo_1001" \
  -d '{
    "request_id": "ret_987654",
    "merchant_id": "m_fashion_01",
    "user_id": "usr_981",
    "transaction_id": "txn_12891",
    "product_id": "prod_7781",
    "timestamp": "2026-09-04T05:00:00Z",
    "refund_amount": 8420.0,
    "order_amount": 10500.0,
    "product_category": "electronics",
    "device_id": "dev_391",
    "address_id": "addr_120",
    "payment_id": "pay_883"
  }'
```

**Response (<15ms)**:
```json
{
  "request_id": "ret_987654",
  "risk": {
    "probability": 0.874,
    "model_version": "rr-lgbm-1.0.0",
    "calibration_version": "cal-isotonic-1.0",
    "raw_margin": 1.932
  },
  "decision": {
    "action": "BLOCK",
    "expected_loss": 7359.08,
    "policy_version": "policy-3.0"
  },
  "features": {
    "feature_version": "fv-2.1",
    "graph_version": "g0000",
    "graph_age_ms": 120
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

### 2. Fetch TreeSHAP Explanation (`GET /v1/risk/returns/{request_id}/explanation`)

```bash
curl -X GET "http://localhost:8000/v1/risk/returns/ret_987654/explanation"
```

### 3. Check Live Prometheus Metrics (`GET /metrics`)

```bash
curl -X GET "http://localhost:8000/metrics"
```

---

## 🧪 Comprehensive Verification & Test Suite

Run the full repository test suite (**51 passing tests** across unit, integration, and load test modules):

```bash
pytest tests/ -v
```

Execute individual phase acceptance verifications:
```bash
python scripts/verify_phase7.py   # Phase 7: Dashboard BFF verification
python scripts/verify_phase8.py   # Phase 8: Dashboard Frontend verification
python scripts/verify_phase9.py   # Phase 9: Observability & Deployment verification
```

---

## 📂 Project Repository Structure

```
├── config/                      # System configuration files
│   ├── simulation/              # Synthetic world simulation configs
│   ├── features/                # 53-feature registry schema
│   ├── economics/               # Merchant margin & salvage parameters
│   ├── policies/                # Automated risk decision rules
│   └── explanation/             # TreeSHAP reason code catalogue
├── data/                        # Local datasets & SQLite WAL database
│   ├── raw/                     # Orders, returns, users, relationships parquets
│   ├── features/                # Point-in-time train/val/test feature sets
│   └── dashboard.db             # Operational case review & audit log SQLite DB
├── deployment/                  # Production Docker & telemetry configuration
│   ├── Dockerfile.api           # Scoring API container
│   ├── Dockerfile.dashboard     # Dashboard BFF container
│   ├── Dockerfile.frontend      # Next.js 14 multi-stage container
│   ├── Dockerfile.shap_worker   # TreeSHAP worker container
│   ├── Dockerfile.graph_processor # Identity graph processor container
│   ├── prometheus.yml           # Prometheus scrape configuration
│   └── grafana/                 # Pre-provisioned dashboards & datasources
├── frontend/                    # Next.js 14 App Router investigation dashboard
│   ├── src/app/                 # 7 operational pages (overview, queue, cases, etc.)
│   ├── src/components/          # 7 high-performance dashboard UI components
│   ├── src/hooks/               # Real-time data polling & focus hooks
│   └── src/lib/                 # TypeScript contracts and API client
├── model_registry/              # Trained models, calibrators, and lineage metadata
│   └── return-risk/1.0.0/       # LightGBM booster, calibrator.pkl, schema
├── scripts/                     # Operational automation scripts
│   ├── generate_data.py         # Synthetic world data generator
│   ├── build_features.py        # Offline point-in-time feature pipeline
│   ├── train_model.py           # LightGBM training & isotonic calibration
│   ├── run_graph_processor.py   # Identity graph processor daemon
│   ├── run_shap_worker.py       # Asynchronous TreeSHAP worker daemon
│   ├── run_dashboard_bff.py     # Dashboard BFF server runner
│   ├── run_all.ps1              # Windows multi-service runner
│   ├── run_all.sh               # Unix/Linux multi-service runner
│   └── verify_phase[1-9].py     # Automated acceptance test scripts
├── src/                         # Core Python microservices source code
│   ├── common/                  # Logging, metrics, middleware, config utilities
│   ├── simulation/              # Event-driven synthetic e-commerce simulator
│   ├── features/                # Feature registry, offline & online builders
│   ├── models/                  # ML training, calibration, and evaluation
│   ├── inference/               # Real-time scoring API & economic engine
│   ├── explainability/          # TreeSHAP background worker & reason code engine
│   └── dashboard/               # BFF service & SQLite persistence layer
├── tests/                       # Complete Pytest test suite (51 tests)
│   ├── integration/             # End-to-end integration tests
│   └── load/                    # Locust concurrent load testing suite
├── docker-compose.yml           # Multi-service container orchestration
└── pyproject.toml               # Project metadata and dependencies
```

---

## 🏆 Project Completion Roadmap

- [x] **Phase 0: Common Infrastructure & Base Utilities**
- [x] **Phase 1: Synthetic Data Generation & Fraud Scenarios**
- [x] **Phase 2: Offline Feature Engineering & Temporal Splits**
- [x] **Phase 3: Model Training & Isotonic Probability Calibration**
- [x] **Phase 4: Real-Time Inference API & Economic Decision Engine**
- [x] **Phase 5: Online Redis State & Bipartite Graph Engine**
- [x] **Phase 6: Asynchronous TreeSHAP Explainability & Reason Codes**
- [x] **Phase 7: Dashboard Backend (BFF) & Operational Review Store**
- [x] **Phase 8: Next.js 14 Investigation Dashboard Frontend**
- [x] **Phase 9: Production Observability, Containerization & CI/CD**
