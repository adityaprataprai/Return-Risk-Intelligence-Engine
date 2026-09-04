"""FastAPI application router and entrypoint for Dashboard BFF service."""

from typing import Any, Dict, Optional
from fastapi import APIRouter, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from src.common.logging import get_logger, setup_logging
from .db import db_manager
from .schemas import (
    AnalystActionRequest,
    AnalystActionResponse,
    AuditLogResponse,
    CaseDetailResponse,
    FeatureHealthResponse,
    FinancialImpactResponse,
    FraudAnalyticsResponse,
    ModelHealthResponse,
    NetworkGraphResponse,
    OverviewKPIsResponse,
    PolicyConfig,
    PolicySimulateRequest,
    PolicySimulateResponse,
    ReviewQueueResponse,
    RiskDistributionResponse,
    SystemHealthResponse,
    TimelineResponse,
)
from .services import (
    ActionService,
    AnalyticsService,
    CaseService,
    HealthService,
    NetworkService,
    PolicyService,
    TimelineService,
)

logger = get_logger("dashboard.api")

# Services
case_service = CaseService()
action_service = ActionService()
timeline_service = TimelineService()
network_service = NetworkService()
analytics_service = AnalyticsService()
policy_service = PolicyService()
health_service = HealthService()

router = APIRouter(prefix="/api", tags=["Dashboard BFF"])


# -------------------------------------------------------------
# 1. Overview Endpoints
# -------------------------------------------------------------
@router.get("/overview/kpis", response_model=OverviewKPIsResponse, summary="Executive return risk KPIs")
async def get_overview_kpis() -> OverviewKPIsResponse:
    """Returns top-level KPIs including approval rate, blocked fraud, loss prevented, and queue counts."""
    return case_service.get_kpis()


@router.get("/overview/risk-distribution", response_model=RiskDistributionResponse, summary="Risk score histogram")
async def get_risk_distribution() -> RiskDistributionResponse:
    """Returns probability distribution buckets (0.0-0.1 .. 0.9-1.0) and action counts."""
    return case_service.get_risk_distribution()


# -------------------------------------------------------------
# 2. Review Queue & Cases
# -------------------------------------------------------------
@router.get("/review-queue", response_model=ReviewQueueResponse, summary="Prioritized analyst review queue")
async def get_review_queue(
    status: Optional[str] = Query("PENDING_REVIEW", description="Filter by status (PENDING_REVIEW, RESOLVED, ALL)"),
    priority: Optional[str] = Query(None, description="Filter by priority (HIGH, MEDIUM, LOW)"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    search: Optional[str] = Query(None, description="Search request_id, user_id, or transaction_id"),
) -> ReviewQueueResponse:
    """Returns paginated review queue cases ordered by risk score descending."""
    return case_service.get_review_queue(status=status, priority=priority, limit=limit, offset=offset, search=search)


@router.get("/cases/{request_id}", response_model=CaseDetailResponse, summary="Holistic case details")
async def get_case_detail(request_id: str) -> CaseDetailResponse:
    """Returns complete case profile combining scores, explanation, timeline, and analyst actions."""
    detail = case_service.get_case_detail(request_id)
    if not detail:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with request_id '{request_id}' not found.",
        )
    return detail


@router.post("/cases/{request_id}/action", response_model=AnalystActionResponse, summary="Submit analyst decision")
async def submit_case_action(request_id: str, payload: AnalystActionRequest) -> AnalystActionResponse:
    """Executes manual review action (APPROVE/REJECT/ESCALATE/RESOLVE) and logs audit trail."""
    resp = action_service.execute_action(request_id, payload)
    if not resp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case with request_id '{request_id}' not found.",
        )
    return resp


@router.get("/cases/{request_id}/explanation", summary="Explanation for a case")
async def get_case_explanation(request_id: str) -> Dict[str, Any]:
    """Retrieves TreeSHAP explanation for a case from ExplanationStore."""
    record = case_service.exp_store.get_explanation(request_id)
    if record:
        return record.model_dump(mode="json")

    # Fallback to case detail explanation
    case_detail = case_service.get_case_detail(request_id)
    if case_detail and case_detail.explanation:
        return case_detail.explanation

    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Explanation for request_id '{request_id}' not found.",
    )


@router.get("/cases/{request_id}/timeline", response_model=TimelineResponse, summary="Customer event timeline")
async def get_case_timeline(request_id: str) -> TimelineResponse:
    """Returns chronological customer interaction timeline leading up to the return claim."""
    timeline = timeline_service.get_timeline(request_id)
    if not timeline:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Timeline for request_id '{request_id}' not found.",
        )
    return timeline


# -------------------------------------------------------------
# 3. Identity Network Explorer
# -------------------------------------------------------------
@router.get("/networks/{request_id}", response_model=NetworkGraphResponse, summary="Identity graph network")
async def get_network_graph(request_id: str) -> NetworkGraphResponse:
    """Returns bipartite network graph (users, devices, addresses, payments) for a case."""
    graph = network_service.get_network_graph(request_id)
    if not graph:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Network graph for request_id '{request_id}' not found.",
        )
    return graph


# -------------------------------------------------------------
# 4. Analytics
# -------------------------------------------------------------
@router.get("/analytics/fraud", response_model=FraudAnalyticsResponse, summary="Fraud typology analytics")
async def get_fraud_analytics() -> FraudAnalyticsResponse:
    """Returns breakdown of fraud vectors (wardrobing, network abuse, velocity) and daily trends."""
    return analytics_service.get_fraud_analytics()


@router.get("/analytics/financial-impact", response_model=FinancialImpactResponse, summary="Financial impact & ROI")
async def get_financial_impact() -> FinancialImpactResponse:
    """Returns quantified financial savings, return shipping preserved, and ROI multiples."""
    return analytics_service.get_financial_impact()


# -------------------------------------------------------------
# 5. Policies & Simulation
# -------------------------------------------------------------
@router.get("/policies", response_model=PolicyConfig, summary="Active policy rulebook")
async def get_policies() -> PolicyConfig:
    """Returns current active decision policies, thresholds, and execution rules."""
    return policy_service.get_active_policy()


@router.post("/policies/simulate", response_model=PolicySimulateResponse, summary="Simulate threshold changes")
async def simulate_policy(payload: PolicySimulateRequest) -> PolicySimulateResponse:
    """Evaluates the hypothetical impact of changing risk thresholds on historical cases."""
    return policy_service.simulate_policy(payload)


# -------------------------------------------------------------
# 6. Observability, Health & Audit
# -------------------------------------------------------------
@router.get("/model-health", response_model=ModelHealthResponse, summary="Champion model health")
async def get_model_health() -> ModelHealthResponse:
    """Returns champion LightGBM model metrics (AUROC, AUPRC, Brier) and latency stats."""
    return health_service.get_model_health()


@router.get("/feature-health", response_model=FeatureHealthResponse, summary="Feature store health")
async def get_feature_health() -> FeatureHealthResponse:
    """Returns feature pipeline status, Redis connectivity, and graph freshness."""
    return health_service.get_feature_health()


@router.get("/system-health", response_model=SystemHealthResponse, summary="Overall system health")
async def get_system_health() -> SystemHealthResponse:
    """Aggregates health across API, Redis, database, and background workers."""
    return health_service.get_system_health()


@router.get("/audit", response_model=AuditLogResponse, summary="Audit log history")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user_id: Optional[str] = Query(None, description="Filter audit log by investigator username"),
) -> AuditLogResponse:
    """Returns chronological audit log of analyst decisions and policy overrides."""
    return health_service.get_audit_log(limit=limit, offset=offset, user_id=user_id)


# -------------------------------------------------------------
# FastAPI App Factory
# -------------------------------------------------------------
def create_app() -> FastAPI:
    """Factory function creating the Dashboard BFF application."""
    setup_logging()
    app = FastAPI(
        title="Razorpay Return-Risk Dashboard BFF",
        version="0.1.0",
        description="Backend-For-Frontend service for merchant risk workbench, case review, and network exploration.",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Correlation ID middleware
    from src.common.middleware import RequestIdMiddleware
    app.add_middleware(RequestIdMiddleware)

    @app.get("/health", tags=["Health"])
    async def health() -> Dict[str, str]:
        return {"status": "ok", "service": "dashboard-bff", "version": "0.1.0"}

    app.include_router(router)

    # Initialize Prometheus metrics & /metrics endpoint
    from src.common.metrics import setup_metrics
    setup_metrics(app, app_name="dashboard-bff")

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    from .config import BFF_HOST, BFF_PORT
    uvicorn.run("src.dashboard.api:app", host=BFF_HOST, port=BFF_PORT, reload=True)
