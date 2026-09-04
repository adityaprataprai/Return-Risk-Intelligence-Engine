"""Data models and schemas for Phase 6 Explainability pipeline."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ExplanationJob(BaseModel):
    """Payload queued by scoring API for asynchronous TreeSHAP computation."""

    request_id: str = Field(..., description="Unique correlated return request identifier")
    user_id: Optional[str] = Field(default=None, description="Customer account ID")
    merchant_id: Optional[str] = Field(default=None, description="Merchant identifier")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Timestamp when job was enqueued",
    )
    feature_vector: Dict[str, float] = Field(
        ..., description="Complete snapshot of 52 model features at decision time"
    )
    raw_margin: float = Field(..., description="Raw model logit/margin score from tree booster")
    calibrated_probability: float = Field(..., description="Calibrated fraud risk probability")
    decision_action: str = Field(..., description="Economic decision (APPROVE/VERIFY/BLOCK)")
    model_version: str = Field(..., description="Registered model version")
    calibration_version: str = Field(..., description="Calibrator version")
    feature_version: str = Field(default="fv-2.1", description="Feature schema version")
    graph_version: str = Field(default="g0000", description="Identity graph partition version")
    retries: int = Field(default=0, description="Current retry counter for transient worker errors")


class FeatureAttribution(BaseModel):
    """SHAP attribution for a single feature."""

    feature: str = Field(..., description="Feature name")
    value: float = Field(..., description="Observed feature value at decision time")
    shap_value: float = Field(..., description="TreeSHAP attribution in raw margin space")
    abs_shap: float = Field(..., description="Magnitude of attribution (|SHAP|)")
    direction: Literal["RISK_INCREASING", "RISK_DECREASING"] = Field(
        ..., description="Whether feature increases fraud logit or mitigates risk"
    )


class GroupAttribution(BaseModel):
    """Aggregated SHAP attribution for a semantic feature domain."""

    group_name: str = Field(..., description="Internal semantic group identifier")
    display_name: str = Field(..., description="Human-friendly domain title")
    description: str = Field(..., description="Semantic group definition")
    total_shap: float = Field(..., description="Net sum of SHAP attributions in this domain")
    abs_total_shap: float = Field(..., description="Absolute sum of SHAP magnitudes")
    rank: int = Field(..., description="Attribution rank (1 = highest risk driver)")
    top_features: List[FeatureAttribution] = Field(
        default_factory=list, description="Top contributing features in this group"
    )


class ReasonCodeEvidence(BaseModel):
    """Concrete reason code and evidence supporting risk decision."""

    code: str = Field(..., description="Deterministic reason code (e.g., RC_NETWORK_ABUSE)")
    title: str = Field(..., description="Human-readable reason code summary")
    severity: Literal["HIGH", "MEDIUM", "LOW", "INFO"] = Field(..., description="Severity tier")
    group: str = Field(..., description="Semantic domain bucket")
    evidence_text: str = Field(..., description="Concrete, templated evidence narrative")
    supporting_features: Dict[str, Any] = Field(
        default_factory=dict, description="Concrete feature values observed at scoring"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Observation timestamp",
    )
    source: str = Field(
        default="return_risk_engine", description="Lineage source of observation data"
    )


class DataConfidenceInfo(BaseModel):
    """Assessment of feature density, cold-start indicators, and data confidence."""

    confidence_level: Literal["HIGH", "MEDIUM", "LOW_COLD_START"] = Field(
        ..., description="Data confidence classification"
    )
    history_summary: str = Field(..., description="Descriptive summary of data maturity")
    cold_start_indicators: Dict[str, Any] = Field(
        default_factory=dict, description="Cold-start and evidence-quality feature readings"
    )


class ExplanationRecord(BaseModel):
    """Immutable, auditable explanation record for a scored return request."""

    request_id: str = Field(..., description="Correlated return request identifier")
    status: Literal["PENDING", "PROCESSING", "READY", "FAILED"] = Field(
        ..., description="Explanation generation lifecycle status"
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Enqueued timestamp",
    )
    completed_at: Optional[str] = Field(
        default=None, description="Timestamp when SHAP computation finished"
    )
    base_value: float = Field(
        default=0.0, description="Expected value / baseline log-odds of TreeExplainer"
    )
    raw_margin: float = Field(default=0.0, description="Booster raw margin (log-odds)")
    calibrated_probability: float = Field(
        default=0.0, description="Final calibrated fraud probability"
    )
    reconstructed_margin: float = Field(
        default=0.0, description="base_value + sum(shap_values) reconstruction"
    )
    margin_reconstruction_error: float = Field(
        default=0.0, description="Absolute difference (|reconstructed - raw_margin|)"
    )
    group_attributions: List[GroupAttribution] = Field(
        default_factory=list, description="Aggregated semantic group attributions"
    )
    top_features: List[FeatureAttribution] = Field(
        default_factory=list, description="Top overall individual feature attributions"
    )
    reason_codes: List[ReasonCodeEvidence] = Field(
        default_factory=list, description="Top deterministic reason codes with evidence"
    )
    data_confidence: DataConfidenceInfo = Field(
        default_factory=lambda: DataConfidenceInfo(
            confidence_level="HIGH",
            history_summary="Sufficient historical telemetry",
            cold_start_indicators={},
        ),
        description="Data confidence and cold-start profile",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Model, calibration, and feature version metadata"
    )
    error_message: Optional[str] = Field(
        default=None, description="Error details if explanation job failed"
    )
