"""Pydantic schemas and contracts for Dashboard BFF API."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# 1. Overview KPIs & Risk Distribution
# -------------------------------------------------------------
class OverviewKPIsResponse(BaseModel):
    total_cases_evaluated: int = Field(..., description="Total return requests evaluated")
    total_fraud_blocked: int = Field(..., description="High-risk claims blocked automatically")
    total_manual_reviews: int = Field(..., description="Borderline claims routed to review queue")
    total_approved: int = Field(..., description="Low-risk claims authorized immediately")
    loss_prevented_amount: float = Field(..., description="Total financial loss prevented (currency)")
    total_refund_requested: float = Field(..., description="Gross refund volume requested")
    approval_rate: float = Field(..., description="Percentage of auto-approved claims")
    review_rate: float = Field(..., description="Percentage of manual review claims")
    block_rate: float = Field(..., description="Percentage of auto-blocked claims")
    avg_decision_latency_ms: float = Field(..., description="Average scoring latency in milliseconds")
    active_review_queue_count: int = Field(..., description="Pending review queue cases currently open")


class RiskDistributionBucket(BaseModel):
    range: str = Field(..., description="Probability range bucket (e.g., '0.0-0.1')")
    count: int = Field(..., description="Number of claims falling into bucket")
    percentage: float = Field(..., description="Percentage share of total volume")


class RiskDistributionResponse(BaseModel):
    buckets: List[RiskDistributionBucket]
    decision_breakdown: Dict[str, int]
    average_risk_score: float


# -------------------------------------------------------------
# 2. Review Queue
# -------------------------------------------------------------
class ReviewQueueItem(BaseModel):
    request_id: str
    user_id: str
    merchant_id: str
    transaction_id: str
    risk_score: float
    action: str
    priority: Literal["HIGH", "MEDIUM", "LOW"]
    status: str
    assignee: Optional[str] = None
    refund_amount: float
    order_amount: float
    created_at: str
    primary_reason: Optional[str] = None


class ReviewQueueResponse(BaseModel):
    total: int
    limit: int
    offset: int
    items: List[ReviewQueueItem]


# -------------------------------------------------------------
# 3. Case Detail & Action Submission
# -------------------------------------------------------------
class CaseDetailResponse(BaseModel):
    request_id: str
    user_id: str
    merchant_id: str
    transaction_id: str
    created_at: str
    status: str
    assignee: Optional[str] = None
    risk: Dict[str, Any]
    order: Dict[str, Any]
    explanation: Optional[Dict[str, Any]] = None
    timeline_summary: Optional[List[Dict[str, Any]]] = None
    analyst_actions: List[Dict[str, Any]] = Field(default_factory=list)


class AnalystActionRequest(BaseModel):
    action: Literal["APPROVE", "REJECT", "ESCALATE", "RESOLVE"] = Field(..., description="Action to execute")
    analyst_id: str = Field(..., description="Identifier of investigator")
    override_reason: Optional[str] = Field(default=None, description="Justification for decision or override")
    notes: Optional[str] = Field(default=None, description="Analyst investigative notes")


class AnalystActionResponse(BaseModel):
    success: bool
    case_id: str
    action_id: str
    status: str
    action: str
    recorded_at: str


# -------------------------------------------------------------
# 4. User Behavioral Timeline
# -------------------------------------------------------------
class TimelineEvent(BaseModel):
    event_id: str
    timestamp: str
    event_type: str
    title: str
    description: str
    amount: Optional[float] = None
    badge_type: str = Field(default="info", description="UI badge visual hint (info, warning, danger, success)")


class TimelineResponse(BaseModel):
    request_id: str
    user_id: str
    events: List[TimelineEvent]


# -------------------------------------------------------------
# 5. Identity Network Explorer Graph
# -------------------------------------------------------------
class NetworkNode(BaseModel):
    id: str
    label: str
    type: Literal["user", "device", "address", "payment"]
    risk_level: Literal["HIGH", "MEDIUM", "LOW", "CLEAN"]
    properties: Dict[str, Any] = Field(default_factory=dict)


class NetworkEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 1.0


class NetworkGraphResponse(BaseModel):
    request_id: str
    root_user_id: str
    nodes: List[NetworkNode]
    edges: List[NetworkEdge]
    summary: Dict[str, Any]


# -------------------------------------------------------------
# 6. Analytics (Fraud & Financial Impact)
# -------------------------------------------------------------
class FraudVectorItem(BaseModel):
    vector: str
    title: str
    count: int
    amount: float
    percentage: float


class FraudAnalyticsResponse(BaseModel):
    vectors: List[FraudVectorItem]
    trend_daily: List[Dict[str, Any]]
    total_flagged_count: int


class FinancialImpactResponse(BaseModel):
    gross_merchandise_value: float
    total_refund_requested: float
    fraud_loss_prevented: float
    return_shipping_saved: float
    handling_costs_preserved: float
    net_financial_savings: float
    roi_multiple: float


# -------------------------------------------------------------
# 7. Policies & Simulation
# -------------------------------------------------------------
class PolicyRule(BaseModel):
    rule_id: str
    condition: str
    action: str
    description: str


class PolicyConfig(BaseModel):
    policy_id: str
    version: str
    verify_threshold: float
    block_threshold: float
    vip_exemption_enabled: bool
    high_value_refund_trigger: float
    max_allowed_24h_returns: int
    rules: List[PolicyRule]
    created_at: str


class PolicySimulateRequest(BaseModel):
    verify_threshold: float = Field(..., ge=0.0, le=1.0, description="Hypothetical verification threshold")
    block_threshold: float = Field(..., ge=0.0, le=1.0, description="Hypothetical direct block threshold")


class PolicySimulateResponse(BaseModel):
    cases_evaluated: int
    current_distribution: Dict[str, int]
    simulated_distribution: Dict[str, int]
    simulated_expected_loss: float
    loss_saved_difference: float
    review_queue_workload_change_percent: float


# -------------------------------------------------------------
# 8. Observability & Health
# -------------------------------------------------------------
class ModelHealthResponse(BaseModel):
    model_name: str
    version: str
    status: str
    test_auroc: float
    test_auprc: float
    brier_score: float
    p50_latency_ms: float
    p95_latency_ms: float


class FeatureHealthResponse(BaseModel):
    feature_version: str
    feature_count: int
    redis_status: str
    graph_freshness_age_seconds: int
    missing_feature_rate: float


class SystemHealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, str]


class AuditLogEntry(BaseModel):
    event_id: str
    request_id: Optional[str]
    timestamp: str
    user: str
    action: str
    metadata: Dict[str, Any]


class AuditLogResponse(BaseModel):
    total: int
    items: List[AuditLogEntry]
