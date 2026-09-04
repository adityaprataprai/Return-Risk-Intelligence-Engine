# Project Phases — Razorpay Return-Risk Intelligence Engine

## Phase List

| Phase | Name | Focus | Depends on | Status |
|---|---|---|---|---|
| **0** | Project Setup & Common Infrastructure | Repo structure, config, logging, utilities | — | **Completed** |
| **1** | Synthetic Data Generation | Event-driven simulator, fraud scenarios, raw data | 0 | **Completed** |
| **2** | Offline Feature Engineering | 53 point-in-time features, training dataset | 1 | **Completed** |
| **3** | Model Training & Calibration | LightGBM champion booster, isotonic calibration | 2 | **Completed** |
| **4** | Inference API & Economic Engine | Sub-15ms FastAPI scoring, economic decisioning | 3 | **Completed** |
| **5** | Redis Online State & Graph Processor | Real-time features, bipartite graph materialization | 4 | **Completed** |
| **6** | Explainability (TreeSHAP) | Async SHAP worker, reason codes, raw margin additivity | 4 | **Completed** |
| **7** | Dashboard Backend (BFF) | 16 REST endpoints, case review, SQLite WAL | 4, 5, 6 | **Completed** |
| **8** | Dashboard Frontend | Next.js 14 App Router, investigation workbench | 7 | **Completed** |
| **9** | Observability, Deployment & Final Polish | Prometheus, Grafana, Docker Compose, Locust, CI/CD | All | **Completed** |

---

## Architecture & Technology Stack

- **Inference & Decision Engine**: Python 3.11, FastAPI, Pydantic v2, LightGBM, Scikit-learn, Polars
- **Online State & Graph Store**: Redis 7, In-Memory Bipartite Graph Engine
- **Explainability**: TreeSHAP, Custom Semantic Reason Code Engine
- **Investigation Dashboard**: Next.js 14 (App Router), React 18, TypeScript, Tailwind CSS, Lucide React
- **Persistence**: SQLite with Write-Ahead Logging (WAL) & connection pooling
- **Telemetry & Monitoring**: Prometheus, Grafana, `prometheus-fastapi-instrumentator`
- **Containerization & CI/CD**: Docker Compose, Multi-stage Dockerfiles, GitHub Actions, Locust